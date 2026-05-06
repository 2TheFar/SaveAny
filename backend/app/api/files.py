from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.services.file_service import resolve_file

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{file_id}")
def download_file(file_id: str):
    file_path, file_name = resolve_file(file_id)
    return FileResponse(file_path, filename=file_name, media_type="application/octet-stream")

