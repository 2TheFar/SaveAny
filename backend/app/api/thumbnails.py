from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from app.services.thumbnail_service import resolve_thumbnail

router = APIRouter(prefix="/api/thumbnails", tags=["thumbnails"])


@router.get("/{thumbnail_id}")
def thumbnail(thumbnail_id: str):
    if thumbnail_id == "placeholder":
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">'
            '<rect width="960" height="540" rx="32" fill="#eaf1fa"/>'
            '<rect x="332" y="166" width="296" height="208" rx="42" fill="#1677ff"/>'
            '<path d="M455 220v100l86-50-86-50Z" fill="white"/>'
            '<text x="480" y="430" text-anchor="middle" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#496279">SaveAny Preview</text>'
            "</svg>"
        )
        return Response(svg, media_type="image/svg+xml")

    path, content_type = resolve_thumbnail(thumbnail_id)
    return FileResponse(path, media_type=content_type)

