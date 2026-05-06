from pathlib import Path

from fastapi import HTTPException

from app.core.config import DOWNLOAD_DIR


def resolve_file(file_id: str) -> tuple[Path, str]:
    if not file_id or any(char in file_id for char in ("/", "\\", "..")):
        raise HTTPException(status_code=404, detail={"error": "文件不存在。", "code": "FILE_NOT_FOUND"})

    task_dir = (DOWNLOAD_DIR / file_id).resolve()
    root = DOWNLOAD_DIR.resolve()
    if root not in task_dir.parents and task_dir != root:
        raise HTTPException(status_code=404, detail={"error": "文件不存在。", "code": "FILE_NOT_FOUND"})

    if not task_dir.exists() or not task_dir.is_dir():
        raise HTTPException(status_code=404, detail={"error": "文件不存在或已过期。", "code": "FILE_NOT_FOUND"})

    candidates = [path for path in task_dir.iterdir() if path.is_file() and path.name != "meta.json"]
    if not candidates:
        raise HTTPException(status_code=404, detail={"error": "文件不存在或已过期。", "code": "FILE_NOT_FOUND"})

    file_path = max(candidates, key=lambda path: path.stat().st_mtime)
    return file_path, file_path.name
