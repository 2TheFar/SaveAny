from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models.media import QualityValue

TaskStatus = Literal["pending", "running", "success", "failed", "expired"]
TaskType = Literal["download", "thumbnail_cache", "subtitle_extract", "audio_extract", "transcribe", "summarize", "batch_download"]


class DownloadTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    quality: QualityValue = "best"


class TaskCreateResponse(BaseModel):
    taskId: str
    status: TaskStatus


class TaskSnapshot(BaseModel):
    taskId: str
    type: TaskType
    status: TaskStatus
    progress: int = 0
    fileName: str | None = None
    fileUrl: str | None = None
    error: str | None = None
    code: str | None = None
    createdAt: float
    updatedAt: float
    expiresAt: float
    ownerId: str | None = None
    entitlement: str | None = None
    result: dict | None = None

