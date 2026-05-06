import json
import subprocess

from app.core.errors import SaveAnyBackendError
from app.models.media import MediaFormat, ResolvedMediaInfo
from app.services.platform_service import detect_platform
from app.services.quality_service import build_quality_options, pick_recommended_quality
from app.services.thumbnail_service import cache_thumbnail

QUALITY_ARGS = {
    "best": ["-f", "bestvideo*+bestaudio/best"],
    "1080p": ["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best[height<=1080]"],
    "720p": ["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]"],
    "audio": ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "192K"],
}


def resolve_with_yt_dlp(url: str) -> ResolvedMediaInfo:
    try:
        result = subprocess.run(
            ["yt-dlp", "-j", "--no-playlist", "--no-warnings", "--skip-download", url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SaveAnyBackendError("DEPENDENCY_MISSING", "服务器未安装 yt-dlp，无法解析视频。", 500) from exc
    except subprocess.CalledProcessError as exc:
        raise map_yt_dlp_error((exc.stderr or "") + (exc.stdout or "")) from exc
    except subprocess.TimeoutExpired as exc:
        raise SaveAnyBackendError("RATE_LIMITED", "解析超时，请稍后重试。") from exc

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SaveAnyBackendError("RESOLVER_FAILED", "yt-dlp 返回内容无法解析。") from exc

    formats = normalize_formats(raw.get("formats"))
    options = build_quality_options(formats)
    thumbnail = raw.get("thumbnail") if isinstance(raw.get("thumbnail"), str) else None

    try:
        thumbnail_url = cache_thumbnail(thumbnail, raw.get("webpage_url") or url)
    except Exception:
        thumbnail_url = "/api/thumbnails/placeholder"

    return ResolvedMediaInfo(
        title=str(raw.get("title") or "未命名视频"),
        uploader=raw.get("uploader") if isinstance(raw.get("uploader"), str) else None,
        thumbnail=thumbnail,
        thumbnailUrl=thumbnail_url,
        duration=raw.get("duration") if isinstance(raw.get("duration"), int) else None,
        webpageUrl=raw.get("webpage_url") if isinstance(raw.get("webpage_url"), str) else url,
        platform=detect_platform(url),
        resolverUsed="YtDlpResolver",
        requiresCookie=False,
        availableQualities=options,
        recommendedQuality=pick_recommended_quality(options),
        formats=formats,
    )


def normalize_formats(value: object) -> list[MediaFormat]:
    if not isinstance(value, list):
        return []

    formats: list[MediaFormat] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        formats.append(
            MediaFormat(
                id=str(item.get("format_id") or ""),
                ext=item.get("ext") if isinstance(item.get("ext"), str) else None,
                resolution=item.get("resolution") if isinstance(item.get("resolution"), str) else None,
                note=item.get("format_note") if isinstance(item.get("format_note"), str) else None,
                height=item.get("height") if isinstance(item.get("height"), int) else None,
                acodec=item.get("acodec") if isinstance(item.get("acodec"), str) else None,
                vcodec=item.get("vcodec") if isinstance(item.get("vcodec"), str) else None,
            )
        )
    return formats


def yt_dlp_quality_args(quality: str) -> list[str]:
    return QUALITY_ARGS.get(quality, QUALITY_ARGS["best"])


def map_yt_dlp_error(message: str) -> SaveAnyBackendError:
    if "Unsupported URL" in message:
        return SaveAnyBackendError("UNSUPPORTED_BY_YTDLP", "当前链接不被 yt-dlp 直接支持，需要平台专用解析器处理。")
    if "cookies" in message or "login" in message or "Sign in" in message:
        return SaveAnyBackendError("NEEDS_LOGIN", "该内容可能需要平台登录态，SaveAny 公网模式默认不接收用户 Cookie。")
    if "403" in message:
        return SaveAnyBackendError("HOTLINK_BLOCKED", "平台拒绝了资源请求，可能存在防盗链或权限限制。")
    if "429" in message or "rate" in message.lower():
        return SaveAnyBackendError("RATE_LIMITED", "平台请求过于频繁，请稍后重试。")
    return SaveAnyBackendError("RESOLVER_FAILED", "解析失败，请确认链接是公开可访问的视频。")
