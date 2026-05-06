from pathlib import Path
from uuid import uuid4

import requests

from app.core.config import BROWSER_USER_AGENT, THUMBNAIL_DIR

MAX_IMAGE_BYTES = 4 * 1024 * 1024


def cache_thumbnail(source_url: str | None, referer: str | None = None) -> str:
    if not source_url:
        return "/api/thumbnails/placeholder"

    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    thumbnail_id = str(uuid4())
    target_dir = THUMBNAIL_DIR / thumbnail_id
    target_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer

    response = requests.get(source_url, headers=headers, timeout=(8, 15), stream=True)
    response.raise_for_status()

    content_type = response.headers.get("content-type") or "image/jpeg"
    suffix = extension_from_content_type(content_type, source_url)
    target_path = target_dir / f"thumbnail{suffix}"
    meta_path = target_dir / "meta.txt"
    written = 0

    with target_path.open("wb") as file:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            written += len(chunk)
            if written > MAX_IMAGE_BYTES:
                raise ValueError("Thumbnail is too large")
            file.write(chunk)

    meta_path.write_text(f"{content_type}\n{target_path.name}", encoding="utf-8")
    return f"/api/thumbnails/{thumbnail_id}"


def resolve_thumbnail(thumbnail_id: str) -> tuple[Path, str]:
    if thumbnail_id == "placeholder":
        raise FileNotFoundError("placeholder is not implemented as file yet")

    meta_path = THUMBNAIL_DIR / thumbnail_id / "meta.txt"
    lines = meta_path.read_text(encoding="utf-8").splitlines()
    content_type = lines[0] if lines else "image/jpeg"
    file_name = lines[1] if len(lines) > 1 else "thumbnail.jpg"
    return THUMBNAIL_DIR / thumbnail_id / file_name, content_type


def extension_from_content_type(content_type: str, source_url: str) -> str:
    normalized = content_type.lower()
    if "png" in normalized or source_url.lower().endswith(".png"):
        return ".png"
    if "webp" in normalized or source_url.lower().endswith(".webp"):
        return ".webp"
    if "gif" in normalized or source_url.lower().endswith(".gif"):
        return ".gif"
    return ".jpg"

