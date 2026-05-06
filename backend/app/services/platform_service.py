from urllib.parse import urlparse

from app.core.errors import SaveAnyBackendError


def assert_valid_url(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SaveAnyBackendError("INVALID_URL", "请先粘贴一个视频链接。")

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SaveAnyBackendError("INVALID_URL", "链接格式不正确，请检查后重试。")

    return value.strip()


def detect_platform(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    host = hostname.lower().removeprefix("www.")

    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "bilibili.com" in host or "b23.tv" in host:
        return "bilibili"
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "douyin"
    if "tiktok.com" in host:
        return "tiktok"
    if "vimeo.com" in host:
        return "vimeo"
    if host in {"x.com", "twitter.com"}:
        return "x"
    if "instagram.com" in host:
        return "instagram"
    return "unknown"
