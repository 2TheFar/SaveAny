import json
import re
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import parse_qs, quote, unquote_to_bytes, urlparse

import requests

from app.core.config import BROWSER_USER_AGENT
from app.core.errors import SaveAnyBackendError
from app.models.ai import SubtitleResult, SubtitleSource, TranscriptSegment
from app.services.ai_cache_service import read_cached_json, write_cached_json
from app.services.asr_service import transcribe_with_asr
from app.services.audio_service import prepare_audio_for_transcription
from app.services.platform_service import assert_valid_url, detect_platform


def extract_subtitles(url: str, language_priority: list[str]) -> SubtitleResult:
    safe_url = assert_valid_url(url)
    cached = read_cached_json(safe_url, "subtitles.json")
    if cached:
        try:
            return SubtitleResult.model_validate(cached)
        except Exception:
            pass

    result = try_platform_subtitles(safe_url, language_priority)
    if result is None:
        result = try_asr_fallback(safe_url)

    write_cached_json(safe_url, "subtitles.json", result.model_dump())
    return result


def try_platform_subtitles(url: str, language_priority: list[str]) -> SubtitleResult | None:
    platform = detect_platform(url)
    if platform == "bilibili":
        return extract_bilibili_platform_subtitles(url, language_priority)
    if platform == "youtube":
        return extract_youtube_platform_subtitles(url, language_priority)
    if platform == "douyin":
        return None
    return None


def try_asr_fallback(url: str) -> SubtitleResult:
    audio_path = prepare_audio_for_transcription(url)
    return transcribe_with_asr(audio_path, detect_platform(url))


def extract_bilibili_platform_subtitles(url: str, language_priority: list[str]) -> SubtitleResult | None:
    metadata = fetch_bilibili_metadata(url)
    candidates = fetch_bilibili_candidates(metadata, url)
    if candidates:
        chosen = pick_bilibili_candidate(candidates, language_priority)
        transcript = fetch_bilibili_subtitle_json(chosen["subtitle_url"], metadata["referer"])
        if transcript:
            return SubtitleResult(
                transcript=transcript,
                source=SubtitleSource(
                    platform="bilibili",
                    subtitleSource=chosen["source"],
                    language=chosen["language"],
                ),
            )

    try:
        transcript = fetch_bilibili_web_subtitles(metadata)
    except SaveAnyBackendError as exc:
        if exc.code != "SUBTITLE_NOT_FOUND":
            raise
        return None

    if transcript:
        return SubtitleResult(
            transcript=transcript,
            source=SubtitleSource(
                platform="bilibili",
                subtitleSource="bilibili_ai_caption",
                language="zh",
            ),
        )
    return None


def extract_youtube_platform_subtitles(url: str, language_priority: list[str]) -> SubtitleResult | None:
    html = fetch_text(url, referer=url)
    player_response = parse_youtube_player_response(html)
    captions = ((player_response.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {})
    tracks = captions.get("captionTracks") or []
    if not isinstance(tracks, list) or not tracks:
        return None

    chosen = pick_youtube_track(tracks, language_priority)
    if not chosen:
        return None

    transcript = fetch_youtube_caption_xml(str(chosen.get("baseUrl") or ""))
    if not transcript:
        return None

    return SubtitleResult(
        transcript=transcript,
        source=SubtitleSource(
            platform="youtube",
            subtitleSource="youtube_caption",
            language=str(chosen.get("languageCode") or "unknown"),
        ),
    )


def fetch_bilibili_metadata(url: str) -> dict[str, int | str]:
    parsed = urlparse(url)
    bvid_match = re.search(r"BV[a-zA-Z0-9]+", url)
    if not bvid_match:
        raise SaveAnyBackendError("INVALID_URL", "Bilibili 链接缺少 BV 号。")

    bvid = bvid_match.group(0)
    page_index = max(1, int(parse_qs(parsed.query).get("p", ["1"])[0]))

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
    if not isinstance(pages, list) or not pages:
        raise SaveAnyBackendError("RESOLVER_FAILED", "Bilibili 视频信息缺少分 P 数据。")

    page_offset = min(page_index - 1, len(pages) - 1)
    page = pages[page_offset] if isinstance(pages[page_offset], dict) else {}
    aid = data.get("aid") if isinstance(data, dict) else None
    cid = page.get("cid")
    duration = page.get("duration") if isinstance(page, dict) else 0
    if not isinstance(aid, int) or not isinstance(cid, int):
        raise SaveAnyBackendError("RESOLVER_FAILED", "Bilibili 视频信息缺少字幕参数。")

    referer = f"https://www.bilibili.com/video/{bvid}/"
    if page_index > 1:
        referer = f"{referer}?p={page_index}"

    return {
        "aid": aid,
        "cid": cid,
        "duration": int(duration or 0),
        "bvid": bvid,
        "referer": referer,
    }


def fetch_bilibili_candidates(metadata: dict[str, int | str], referer: str) -> list[dict[str, str]]:
    url = (
        "https://api.bilibili.com/x/player/wbi/v2"
        f"?cid={metadata['cid']}&aid={metadata['aid']}&bvid={metadata['bvid']}"
    )
    try:
        response = requests.get(url, headers=bilibili_headers(referer), timeout=20)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, json.JSONDecodeError):
        return []

    subtitles = (((payload.get("data") or {}).get("subtitle") or {}).get("subtitles") or [])
    if not isinstance(subtitles, list):
        return []

    candidates: list[dict[str, str]] = []
    for item in subtitles:
        if not isinstance(item, dict):
            continue
        subtitle_url = normalize_bilibili_subtitle_url(item.get("subtitle_url"))
        if not subtitle_url:
            continue
        language = str(item.get("lan") or item.get("lan_doc") or "unknown")
        candidates.append(
            {
                "subtitle_url": subtitle_url,
                "language": language.lower(),
                "source": classify_bilibili_subtitle_source(item),
            }
        )
    return candidates


def classify_bilibili_subtitle_source(item: dict) -> str:
    for key in ("is_ai", "ai_generated", "ai_status", "ai_type"):
        value = item.get(key)
        if isinstance(value, bool) and value:
            return "bilibili_ai_caption"
        if isinstance(value, int) and value > 0:
            return "bilibili_ai_caption"
    text = json.dumps(item, ensure_ascii=False).lower()
    if "ai" in text:
        return "bilibili_ai_caption"
    return "bilibili_auto_caption"


def pick_bilibili_candidate(candidates: list[dict[str, str]], language_priority: list[str]) -> dict[str, str]:
    def score(candidate: dict[str, str]) -> tuple[int, int]:
        source = candidate["source"]
        source_rank = 0 if source == "bilibili_ai_caption" else 1
        language_rank = 100
        for index, language in enumerate(language_priority or ["zh", "en"]):
            if candidate["language"].startswith(language.lower()):
                language_rank = index
                break
        if candidate["language"].startswith("zh") and language_rank == 100:
            language_rank = 50
        if candidate["language"].startswith("en") and language_rank == 100:
            language_rank = 60
        return (language_rank, source_rank)

    return sorted(candidates, key=score)[0]


def fetch_bilibili_subtitle_json(subtitle_url: str, referer: str) -> list[TranscriptSegment]:
    try:
        response = requests.get(subtitle_url, headers=bilibili_headers(referer), timeout=20)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, json.JSONDecodeError):
        return []
    return parse_bilibili_subtitle_json(data)


def fetch_bilibili_web_subtitles(metadata: dict[str, int | str]) -> list[TranscriptSegment]:
    context_ext = quote(json.dumps({"video_type": 1}, separators=(",", ":")))
    url = (
        "https://api.bilibili.com/x/v2/subtitle/web/view"
        f"?oid={metadata['cid']}&pid={metadata['aid']}&duration={metadata['duration']}"
        f"&context_ext={context_ext}&type=1&preferred_language=zh-CN"
    )
    last_error: requests.RequestException | None = None
    for _ in range(3):
        try:
            response = requests.get(url, headers=bilibili_headers(str(metadata["referer"])), timeout=20)
            response.raise_for_status()
            if response.content and response.content != b"\n\x00":
                subtitle_url = extract_bilibili_subtitle_url(response.content)
                if subtitle_url:
                    transcript = fetch_bilibili_subtitle_json(subtitle_url, str(metadata["referer"]))
                    if transcript:
                        return transcript
        except requests.RequestException as exc:
            last_error = exc
    if last_error:
        raise SaveAnyBackendError("RESOLVER_FAILED", "Bilibili 字幕列表接口暂时不可用。") from last_error
    raise subtitle_not_found()


def normalize_bilibili_subtitle_url(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    if value.startswith("/"):
        return f"https://api.bilibili.com{value}"
    return value


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
        text = normalize_text(str(item.get("content") or ""))
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


def parse_youtube_player_response(html: str) -> dict:
    match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\})\s*;", html)
    if not match:
        raise SaveAnyBackendError("RESOLVER_FAILED", "YouTube 页面中未找到字幕元信息。")
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise SaveAnyBackendError("RESOLVER_FAILED", "YouTube 页面字幕元信息无法解析。") from exc


def pick_youtube_track(tracks: list[dict], language_priority: list[str]) -> dict | None:
    candidates = [track for track in tracks if isinstance(track, dict) and track.get("baseUrl")]
    if not candidates:
        return None

    def score(track: dict) -> tuple[int, int]:
        language = str(track.get("languageCode") or "").lower()
        kind = str(track.get("kind") or "")
        language_rank = 100
        for index, preferred in enumerate(language_priority or ["zh", "en"]):
            if language.startswith(preferred.lower()):
                language_rank = index
                break
        if language.startswith("zh") and language_rank == 100:
            language_rank = 50
        if language.startswith("en") and language_rank == 100:
            language_rank = 60
        asr_rank = 1 if kind == "asr" else 0
        return (language_rank, asr_rank)

    return sorted(candidates, key=score)[0]


def fetch_youtube_caption_xml(base_url: str) -> list[TranscriptSegment]:
    if not base_url:
        return []
    try:
        response = requests.get(base_url, headers=generic_headers("https://www.youtube.com/"), timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        return []

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError:
        return []

    transcript: list[TranscriptSegment] = []
    for element in root.findall(".//text"):
        start = element.attrib.get("start")
        duration = element.attrib.get("dur")
        text = normalize_text(unescape("".join(element.itertext())))
        if not start or not text:
            continue
        start_time = float(start)
        end_time = start_time + float(duration or 0)
        transcript.append(
            TranscriptSegment(
                startTime=start_time,
                endTime=end_time,
                text=text,
            )
        )
    return transcript


def fetch_text(url: str, referer: str | None = None) -> str:
    response = requests.get(url, headers=generic_headers(referer), timeout=20)
    response.raise_for_status()
    return response.text


def generic_headers(referer: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def bilibili_headers(referer: str) -> dict[str, str]:
    headers = generic_headers(referer)
    headers["Accept"] = "*/*"
    return headers


def normalize_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def subtitle_not_found() -> SaveAnyBackendError:
    return SaveAnyBackendError("SUBTITLE_NOT_FOUND", "该视频暂无可用字幕。", 404)
