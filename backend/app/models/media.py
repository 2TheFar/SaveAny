from typing import Literal

from pydantic import BaseModel, ConfigDict

QualityValue = Literal["best", "1080p", "720p", "audio"]
PlatformValue = Literal["youtube", "bilibili", "douyin", "tiktok", "vimeo", "x", "instagram", "unknown"]


class MediaInfoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str


class QualityOption(BaseModel):
    value: QualityValue
    label: str
    hint: str
    format: str | None = None
    available: bool


class MediaFormat(BaseModel):
    id: str
    ext: str | None = None
    resolution: str | None = None
    note: str | None = None
    height: int | None = None
    acodec: str | None = None
    vcodec: str | None = None
    url: str | None = None


class ResolvedMediaInfo(BaseModel):
    title: str
    uploader: str | None = None
    thumbnail: str | None = None
    thumbnailUrl: str | None = None
    duration: int | None = None
    webpageUrl: str
    platform: PlatformValue
    resolverUsed: str
    requiresCookie: bool
    availableQualities: list[QualityOption]
    recommendedQuality: QualityValue
    formats: list[MediaFormat]


class MediaInfoResponse(BaseModel):
    info: ResolvedMediaInfo

