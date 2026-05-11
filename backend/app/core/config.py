import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
DOWNLOAD_DIR = STORAGE_DIR / "downloads"
THUMBNAIL_DIR = STORAGE_DIR / "thumbnails"
AI_DIR = STORAGE_DIR / "ai"
MODEL_DIR = STORAGE_DIR / "models"
CREDENTIAL_DIR = STORAGE_DIR / "credentials"
BILIBILI_DIR = STORAGE_DIR / "bilibili"
MAX_CACHE_AGE_SECONDS = 6 * 60 * 60
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)


def load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()

ASR_MODEL = os.environ.get("SAVEANY_ASR_MODEL", "small")
ASR_DEVICE = os.environ.get("SAVEANY_ASR_DEVICE", "cuda")
ASR_COMPUTE_TYPE = os.environ.get("SAVEANY_ASR_COMPUTE_TYPE", "int8_float16")
ASR_CPU_FALLBACK_MODEL = "base"
SAVEANY_BBDOWN_PATH = os.environ.get("SAVEANY_BBDOWN_PATH", "BBDown")
SAVEANY_BBDOWN_ENCODING_PRIORITY = os.environ.get("SAVEANY_BBDOWN_ENCODING_PRIORITY", "avc,hevc,av1")
SAVEANY_BBDOWN_WORK_DIR = Path(os.environ.get("SAVEANY_BBDOWN_WORK_DIR", str(BILIBILI_DIR)))
SAVEANY_BILIBILI_AUTH_FILE = Path(
    os.environ.get("SAVEANY_BILIBILI_AUTH_FILE", str(CREDENTIAL_DIR / "bilibili_session.json"))
)


def resolve_bbdown_executable() -> str | None:
    configured = SAVEANY_BBDOWN_PATH
    resolved = shutil.which(configured)
    if resolved:
        return resolved

    configured_path = Path(configured)
    if configured_path.exists():
        return str(configured_path)

    if configured_path.name == configured:
        home_tool = Path.home() / ".dotnet" / "tools" / "BBDown.exe"
        if home_tool.exists():
            return str(home_tool)

    return None
