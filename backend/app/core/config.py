from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
DOWNLOAD_DIR = STORAGE_DIR / "downloads"
THUMBNAIL_DIR = STORAGE_DIR / "thumbnails"
MAX_CACHE_AGE_SECONDS = 6 * 60 * 60
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)

