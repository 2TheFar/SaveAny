import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.config import AI_DIR


def cache_dir_for_url(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    path = AI_DIR / digest
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_cached_json(url: str, name: str) -> dict[str, Any] | None:
    path = cache_dir_for_url(url) / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cached_json(url: str, name: str, value: dict[str, Any]) -> None:
    path = cache_dir_for_url(url) / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
