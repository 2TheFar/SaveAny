import os
import re
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app.core.config import SAVEANY_BBDOWN_ENCODING_PRIORITY, SAVEANY_BBDOWN_WORK_DIR, resolve_bbdown_executable
from app.core.errors import SaveAnyBackendError
from app.models.media import MediaFormat, QualityOption, QualityValue, ResolvedMediaInfo
from app.services.bilibili_auth_service import get_bilibili_cookie, has_bilibili_session, redact_sensitive_text
from app.services.yt_dlp_resolver import resolve_with_yt_dlp

BBDOWN_FILE_PATTERN = "<videoTitle>_<dfn>_Bilibili"
BBDOWN_QUALITY_PRIORITIES: dict[QualityValue, str] = {
    "best": "8K 超高清,杜比视界,HDR 真彩,4K 超清,1080P 高帧率,1080P 高码率,1080P 高清,720P 高帧率,720P 高清",
    "1080p": "1080P 高帧率,1080P 高码率,1080P 高清",
    "720p": "720P 高帧率,720P 高清",
    "audio": "1080P 高清,720P 高清",
}


def resolve_with_bilibili(url: str) -> ResolvedMediaInfo:
    logged_in = has_bilibili_session()
    try:
        info = resolve_with_yt_dlp(url)
    except SaveAnyBackendError:
        options = build_bilibili_quality_options([], logged_in)
        return ResolvedMediaInfo(
            title=f"Bilibili {extract_bilibili_id(url) or 'video'}",
            uploader=None,
            thumbnail=None,
            thumbnailUrl="/api/thumbnails/placeholder",
            duration=None,
            webpageUrl=url,
            platform="bilibili",
            resolverUsed="BilibiliResolver(BBDown)",
            requiresCookie=not logged_in,
            availableQualities=options,
            recommendedQuality="best",
            formats=[],
        )

    options = build_bilibili_quality_options(info.formats, logged_in)
    return ResolvedMediaInfo(
        title=info.title,
        uploader=info.uploader,
        thumbnail=info.thumbnail,
        thumbnailUrl=info.thumbnailUrl,
        duration=info.duration,
        webpageUrl=info.webpageUrl,
        platform="bilibili",
        resolverUsed="BilibiliResolver(BBDown)",
        requiresCookie=not logged_in,
        availableQualities=options,
        recommendedQuality="best",
        formats=info.formats,
    )


def extract_bilibili_id(url: str) -> str | None:
    match = re.search(r"/video/([^/?#]+)", url)
    return match.group(1) if match else None


def download_with_bilibili(url: str, quality: QualityValue, target_dir: Path, title: str | None = None) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    SAVEANY_BBDOWN_WORK_DIR.mkdir(parents=True, exist_ok=True)

    bbdown_path = resolve_bbdown_executable()
    if not bbdown_path:
        raise SaveAnyBackendError("DEPENDENCY_MISSING", "服务器未安装 BBDown，无法下载 B 站最高画质。", 500)

    command = build_bbdown_command(url, quality, target_dir, bbdown_path)
    before = snapshot_media_files(target_dir)
    try:
        subprocess.run(
            command,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30 * 60,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SaveAnyBackendError("DEPENDENCY_MISSING", "服务器未安装 BBDown，无法下载 B 站最高画质。", 500) from exc
    except subprocess.CalledProcessError as exc:
        output = redact_sensitive_text((exc.stderr or "") + (exc.stdout or ""))
        raise map_bbdown_error(output) from exc
    except subprocess.TimeoutExpired as exc:
        raise SaveAnyBackendError("DOWNLOAD_TIMEOUT", "B 站下载超时，请稍后重试。") from exc

    created = [path for path in snapshot_media_files(target_dir) if path not in before]
    candidates = created or list(snapshot_media_files(target_dir))
    if not candidates:
        raise SaveAnyBackendError("DOWNLOAD_FAILED", "B 站下载完成但没有找到生成的视频文件。")

    downloaded = max(candidates, key=lambda path: path.stat().st_mtime)
    return normalize_bilibili_download_file(
        downloaded,
        target_dir,
        title or extract_bilibili_id(url) or "bilibili_video",
        quality,
    )


def build_bbdown_command(
    url: str,
    quality: QualityValue,
    target_dir: Path,
    bbdown_path: str | None = None,
) -> list[str]:
    command = [
        bbdown_path or resolve_bbdown_executable() or "BBDown",
        url,
        "-p",
        select_bilibili_page(url),
        "-q",
        bbdown_quality_priority(quality),
        "-e",
        SAVEANY_BBDOWN_ENCODING_PRIORITY,
        "--work-dir",
        str(target_dir),
        "--skip-subtitle",
        "--skip-cover",
        "--skip-ai",
        "-F",
        BBDOWN_FILE_PATTERN,
    ]

    if quality == "audio":
        command.append("--audio-only")

    cookie = get_bilibili_cookie()
    if cookie:
        command.extend(["-c", cookie])

    return command


def bbdown_quality_priority(quality: str) -> str:
    return BBDOWN_QUALITY_PRIORITIES.get(quality, BBDOWN_QUALITY_PRIORITIES["best"])


def select_bilibili_page(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    value = query.get("p", ["1"])[0]
    match = re.search(r"\d+", value)
    if not match:
        return "1"
    return str(max(1, int(match.group(0))))


def build_bilibili_quality_options(_formats: list[MediaFormat], logged_in: bool) -> list[QualityOption]:
    return [
        QualityOption(
            value="best",
            label="最高画质",
            hint="按账号权限优先 8K/HDR/4K" if logged_in else "公开视频最高可用，登录可解锁更高画质",
            available=True,
        ),
        QualityOption(
            value="1080p",
            label="1080p",
            hint="限制到 1080P 系列，登录后按账号权限拉取",
            available=True,
        ),
        QualityOption(
            value="720p",
            label="720p",
            hint="限制到 720P 系列，登录后按账号权限拉取",
            available=True,
        ),
        QualityOption(
            value="audio",
            label="仅音频",
            hint="导出账号权限内可用音频",
            available=True,
        ),
    ]


def snapshot_media_files(target_dir: Path) -> set[Path]:
    if not target_dir.exists():
        return set()
    media_suffixes = {".mp4", ".mkv", ".flv", ".webm", ".m4a", ".mp3"}
    ignored_suffixes = {".part", ".tmp", ".temp", ".m4s"}
    output: set[Path] = set()
    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in ignored_suffixes:
            continue
        if suffix in media_suffixes:
            output.add(path)
    return output


def normalize_bilibili_download_file(source: Path, target_dir: Path, title: str, quality: str = "best") -> Path:
    suffix = source.suffix.lower() or ".mp4"
    stem = safe_file_stem(source.stem)
    if stem == "bilibili_video" or "_" not in stem:
        stem = safe_file_stem(f"{title}_{display_quality_label(quality)}_Bilibili")
    target = target_dir / f"{stem}{suffix}"
    if source.resolve() == target.resolve():
        return target

    if target.exists():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, target)
    cleanup_empty_parents(source.parent, target_dir)
    return target


def cleanup_empty_parents(path: Path, stop: Path) -> None:
    stop = stop.resolve()
    current = path.resolve()
    while current != stop and stop in current.parents:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def safe_file_stem(value: str) -> str:
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value, flags=re.U).strip(" ._")
    if not normalized or normalized == "_":
        return "bilibili_video"
    return normalized[:120]


def display_quality_label(quality: str) -> str:
    labels = {
        "best": "最高画质",
        "1080p": "1080p",
        "720p": "720p",
        "audio": "仅音频",
    }
    return labels.get(quality, "最高画质")


def map_bbdown_error(message: str) -> SaveAnyBackendError:
    lowered = message.lower()
    if "login" in lowered or "cookie" in lowered or "sessdata" in lowered or "权限" in message or "会员" in message:
        return SaveAnyBackendError("NEEDS_LOGIN", "B 站更高清晰度需要登录或会员权限，请扫码登录有权限的账号后重试。", 401)
    if "ffmpeg" in lowered:
        return SaveAnyBackendError("DEPENDENCY_MISSING", "BBDown 需要 ffmpeg 合并音视频，请先安装 ffmpeg。", 500)
    if "403" in message or "412" in message:
        return SaveAnyBackendError("HOTLINK_BLOCKED", "B 站拒绝了资源请求，可能是权限、风控或防盗链限制。")
    if "not found" in lowered or "unsupported" in lowered:
        return SaveAnyBackendError("UNSUPPORTED_PLATFORM", "BBDown 暂不支持当前 B 站链接。")
    return SaveAnyBackendError("DOWNLOAD_FAILED", message.strip() or "B 站下载失败，请稍后重试。")
