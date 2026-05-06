from fastapi import APIRouter

from app.models.media import MediaInfoRequest, MediaInfoResponse
from app.services.resolver_service import resolve_media_info

router = APIRouter(prefix="/api/media", tags=["media"])


@router.post("/info", response_model=MediaInfoResponse)
def media_info(request: MediaInfoRequest):
    return MediaInfoResponse(info=resolve_media_info(request.url))

