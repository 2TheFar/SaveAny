from app.models.media import ResolvedMediaInfo
from app.services.douyin_resolver import resolve_with_douyin
from app.services.platform_service import assert_valid_url, detect_platform
from app.services.yt_dlp_resolver import resolve_with_yt_dlp


def resolve_media_info(url: str) -> ResolvedMediaInfo:
    safe_url = assert_valid_url(url)
    platform = detect_platform(safe_url)

    if platform == "douyin":
        return resolve_with_douyin(safe_url)

    return resolve_with_yt_dlp(safe_url)
