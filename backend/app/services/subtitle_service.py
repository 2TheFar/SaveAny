import json
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, unquote_to_bytes

import requests

from app.core.config import BROWSER_USER_AGENT
from app.core.errors import SaveAnyBackendError
from app.models.ai import SubtitleResult, SubtitleSource, TranscriptSegment
from app.services.ai_cache_service import cache_dir_for_url, read_cached_json, write_cached_json
from app.services.platform_service import assert_valid_url, detect_platform
from app.services.yt_dlp_resolver import map_yt_dlp_error


def extract_subtitles(url: str, language_priority: list[str]) -> SubtitleResult:
    safe_url = assert_valid_url(url)
    cached = read_cached_json(safe_url, "subtitles.json")
    if cached:
        return SubtitleResult.model_validate(cached)

    if detect_platform(safe_url) == "bilibili":
        try:
            result = extract_bilibili_website_subtitles(safe_url)
            write_cached_json(safe_url, "subtitles.json", result.model_dump())
            return result
        except SaveAnyBackendError as exc:
            if exc.code != "SUBTITLE_NOT_FOUND":
                raise

    target_dir = cache_dir_for_url(safe_url)
    clear_subtitle_files(target_dir)
    languages = build_subtitle_languages(language_priority)
    output_template = str(target_dir / "subtitle.%(ext)s")
    command = [
        "yt-dlp",
        "--skip-download",
        "--no-playlist",
        "--no-warnings",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        languages,
        "--sub-format",
        "json3/vtt/best",
        "-o",
        output_template,
        safe_url,
    ]

    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SaveAnyBackendError("DEPENDENCY_MISSING", "服务器未安装 yt-dlp，无法提取字幕。", 500) from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "") + (exc.stdout or "")
        if "There are no subtitles" in message or "No subtitles" in message:
            raise subtitle_not_found() from exc
        raise map_yt_dlp_error(message) from exc
    except subprocess.TimeoutExpired as exc:
        raise SaveAnyBackendError("RATE_LIMITED", "字幕提取超时，请稍后重试。") from exc

    subtitle_file = pick_subtitle_file(target_dir, language_priority)
    if not subtitle_file:
        raise subtitle_not_found()

    transcript = parse_subtitle_file(subtitle_file)
    if not transcript:
        raise subtitle_not_found()

    language = detect_language_from_name(subtitle_file.name, language_priority)
    result = SubtitleResult(
        transcript=transcript,
        source=SubtitleSource(platform=detect_platform(safe_url), subtitleSource="yt_dlp", language=language),
    )
    write_cached_json(safe_url, "subtitles.json", result.model_dump())
    return result


def build_subtitle_languages(language_priority: list[str]) -> str:
    normalized = [item.lower() for item in language_priority if item]
    if not normalized:
        normalized = ["zh", "en"]
    patterns: list[str] = []
    for language in normalized:
        if language.startswith("zh"):
            patterns.extend(["zh.*", "zh-Hans", "zh-Hant", "zh-CN", "zh"])
        elif language.startswith("en"):
            patterns.extend(["en.*", "en"])
        else:
            patterns.extend([f"{language}.*", language])
    return ",".join(dict.fromkeys(patterns))


def extract_bilibili_website_subtitles(url: str) -> SubtitleResult:
    metadata = fetch_bilibili_metadata(url)
    payload = fetch_bilibili_subtitle_payload(metadata)
    subtitle_url = extract_bilibili_subtitle_url(payload)
    if not subtitle_url:
        raise subtitle_not_found()

    try:
        response = requests.get(subtitle_url, headers=bilibili_headers(bilibili_referer(str(metadata["bvid"]))), timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        raise SaveAnyBackendError("RESOLVER_FAILED", f"Bilibili 字幕接口返回 {status or '未知状态'}。") from exc
    except (requests.RequestException, json.JSONDecodeError) as exc:
        raise SaveAnyBackendError("RESOLVER_FAILED", "Bilibili 字幕接口暂时不可用。") from exc

    transcript = parse_bilibili_subtitle_json(data)
    if not transcript:
        raise subtitle_not_found()

    return SubtitleResult(
        transcript=transcript,
        source=SubtitleSource(platform="bilibili", subtitleSource="bilibili_web", language="zh"),
    )


def fetch_bilibili_metadata(url: str) -> dict[str, int | str]:
    bvid_match = re.search(r"BV[a-zA-Z0-9]+", url)
    if not bvid_match:
        raise SaveAnyBackendError("INVALID_URL", "Bilibili 链接缺少 BV 号。")

    bvid = bvid_match.group(0)
    try:
        response = requests.get(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            headers=bilibili_headers(url),
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, json.JSONDecodeError) as exc:
        raise SaveAnyBackendError("RESOLVER_FAILED", "Bilibili 视频信息接口暂时不可用。") from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    pages = data.get("pages") if isinstance(data, dict) else None
    first_page = pages[0] if isinstance(pages, list) and pages else {}
    aid = data.get("aid") if isinstance(data, dict) else None
    cid = first_page.get("cid") if isinstance(first_page, dict) else None
    duration = first_page.get("duration") if isinstance(first_page, dict) else data.get("duration")
    if not isinstance(aid, int) or not isinstance(cid, int):
        raise SaveAnyBackendError("RESOLVER_FAILED", "Bilibili 视频信息缺少字幕参数。")

    return {"aid": aid, "cid": cid, "duration": int(duration or 0), "bvid": bvid}


def fetch_bilibili_subtitle_payload(metadata: dict[str, int | str]) -> bytes:
    context_ext = quote(json.dumps({"video_type": 1}, separators=(",", ":")))
    url = (
        "https://api.bilibili.com/x/v2/subtitle/web/view"
        f"?oid={metadata['cid']}&pid={metadata['aid']}&duration={metadata['duration']}"
        f"&context_ext={context_ext}&type=1&preferred_language=zh-CN"
    )
    last_error: requests.RequestException | None = None
    for _ in range(3):
        try:
            response = requests.get(url, headers=bilibili_headers(bilibili_referer(str(metadata["bvid"]))), timeout=20)
            response.raise_for_status()
            if response.content and response.content != b"\n\x00":
                return response.content
        except requests.RequestException as exc:
            last_error = exc
    if last_error:
        raise SaveAnyBackendError("RESOLVER_FAILED", "Bilibili 字幕列表接口暂时不可用。") from last_error
    raise subtitle_not_found()


def extract_bilibili_subtitle_url(payload: bytes) -> str | None:
    marker = b"//subtitle.bilibili.com/"
    start = payload.find(marker)
    if start < 0:
        return None

    path_start = start + len(marker)
    query_start = payload.find(b"?auth_key=", path_start)
    if query_start < 0:
        return None
    query_end = payload.find(b"\x01", query_start)
    if query_end < 0:
        query_end = len(payload)

    encoded_path = payload[path_start:query_start].decode("latin1", errors="ignore")
    query = payload[query_start + 1 : query_end].decode("latin1", errors="ignore")
    real_path = decode_bilibili_ai_subtitle_path(encoded_path)
    if not real_path:
        return None
    return f"https://i0.hdslb.com{real_path}?{query}"


def decode_bilibili_ai_subtitle_path(encoded_path: str) -> str:
    maps = [
        ('nP](wOFRvU.+<fjS{jn-!$D|Dz&",zT`', "=CFxYRn{.y|uVyO$uh&sikph?N.ilF/`"),
        ('Bn"q~|albg@]Go~ACgyDvKnd+)_D}^&J?', "Cu~L!xs~f^&r@'vh=q]q{eeng*sEg^kp#J"),
    ]
    decoded = unquote_to_bytes(encoded_path).decode("latin1", errors="ignore")
    for prefix, key in maps:
        value = xor_text(decoded, f"{key}bilibili")
        if value.startswith(prefix):
            return value.removeprefix(prefix)
    return ""


def xor_text(value: str, key: str) -> str:
    return "".join(chr(ord(char) ^ ord(key[index % len(key)])) for index, char in enumerate(value))


def parse_bilibili_subtitle_json(data: object) -> list[TranscriptSegment]:
    body = data.get("body") if isinstance(data, dict) else None
    if not isinstance(body, list):
        return []

    transcript: list[TranscriptSegment] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        start = item.get("from")
        end = item.get("to")
        text = normalize_subtitle_text(str(item.get("content") or ""))
        if not isinstance(start, (int, float)) or not text:
            continue
        transcript.append(
            TranscriptSegment(
                startTime=float(start),
                endTime=float(end) if isinstance(end, (int, float)) else None,
                text=text,
            )
        )
    return transcript


def bilibili_headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": BROWSER_USER_AGENT,
        "Referer": referer,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def bilibili_referer(bvid: str) -> str:
    return f"https://www.bilibili.com/video/{bvid}/"


def clear_subtitle_files(target_dir: Path) -> None:
    for path in target_dir.glob("subtitle.*"):
        if path.suffix.lower() in {".vtt", ".json3", ".json"}:
            path.unlink(missing_ok=True)


def pick_subtitle_file(target_dir: Path, language_priority: list[str]) -> Path | None:
    candidates = [path for path in target_dir.glob("subtitle.*") if path.suffix.lower() in {".json3", ".json", ".vtt"}]
    if not candidates:
        return None

    def score(path: Path) -> tuple[int, int]:
        name = path.name.lower()
        language_score = 100
        for index, language in enumerate(language_priority or ["zh", "en"]):
            if language.lower() in name:
                language_score = index
                break
        format_score = 0 if path.suffix.lower() in {".json3", ".json"} else 1
        return (language_score, format_score)

    return sorted(candidates, key=score)[0]


def parse_subtitle_file(path: Path) -> list[TranscriptSegment]:
    if path.suffix.lower() in {".json3", ".json"}:
        return parse_json3(path)
    return parse_vtt(path)


def parse_json3(path: Path) -> list[TranscriptSegment]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        return []

    segments: list[TranscriptSegment] = []
    for item in events:
        if not isinstance(item, dict) or not isinstance(item.get("segs"), list):
            continue
        text = "".join(str(seg.get("utf8") or "") for seg in item["segs"] if isinstance(seg, dict)).strip()
        text = normalize_subtitle_text(text)
        if not text:
            continue
        start_ms = item.get("tStartMs")
        duration_ms = item.get("dDurationMs")
        if not isinstance(start_ms, int):
            continue
        end_time = (start_ms + duration_ms) / 1000 if isinstance(duration_ms, int) else None
        segments.append(TranscriptSegment(startTime=start_ms / 1000, endTime=end_time, text=text))
    return merge_short_segments(segments)


def parse_vtt(path: Path) -> list[TranscriptSegment]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    segments: list[TranscriptSegment] = []
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n"))
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timing_line = next((line for line in lines if "-->" in line), "")
        if not timing_line:
            continue
        start_raw, end_raw = [part.strip().split()[0] for part in timing_line.split("-->", 1)]
        text_lines = [line for line in lines[lines.index(timing_line) + 1 :] if not line.startswith(("NOTE", "STYLE"))]
        text = normalize_subtitle_text(" ".join(text_lines))
        if not text:
            continue
        segments.append(
            TranscriptSegment(startTime=parse_vtt_time(start_raw), endTime=parse_vtt_time(end_raw), text=text)
        )
    return merge_short_segments(segments)


def parse_vtt_time(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def normalize_subtitle_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def merge_short_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    merged: list[TranscriptSegment] = []
    for segment in segments:
        if merged and segment.startTime == merged[-1].startTime and segment.text == merged[-1].text:
            continue
        merged.append(segment)
    return merged


def detect_language_from_name(name: str, language_priority: list[str]) -> str:
    lower_name = name.lower()
    for language in language_priority or ["zh", "en"]:
        if language.lower() in lower_name:
            return language
    if "zh" in lower_name:
        return "zh"
    if "en" in lower_name:
        return "en"
    return "unknown"


def subtitle_not_found() -> SaveAnyBackendError:
    return SaveAnyBackendError("SUBTITLE_NOT_FOUND", "该视频暂无可用字幕。", 404)
