import time
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException

from app.core.config import DOWNLOAD_DIR, MAX_CACHE_AGE_SECONDS
from app.core.errors import SaveAnyBackendError
from app.models.task import DownloadTaskRequest, TaskSnapshot
from app.services.download_service import download_media

TASKS: dict[str, TaskSnapshot] = {}


def create_download_task(request: DownloadTaskRequest, background_tasks: BackgroundTasks) -> TaskSnapshot:
    now = time.time()
    task_id = str(uuid4())
    task = TaskSnapshot(
        taskId=task_id,
        type="download",
        status="pending",
        progress=0,
        createdAt=now,
        updatedAt=now,
        expiresAt=now + MAX_CACHE_AGE_SECONDS,
    )
    TASKS[task_id] = task
    background_tasks.add_task(run_download_task, task_id, request)
    return task


def get_task(task_id: str) -> TaskSnapshot:
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "任务不存在或已过期。", "code": "TASK_NOT_FOUND"})
    if task.expiresAt < time.time():
        task.status = "expired"
    return task


def run_download_task(task_id: str, request: DownloadTaskRequest) -> None:
    task = TASKS[task_id]
    update_task(task, status="running", progress=10)

    try:
        file_path = download_media(request.url, request.quality, DOWNLOAD_DIR / task_id)
    except SaveAnyBackendError as exc:
        update_task(task, status="failed", progress=100, error=exc.message, code=exc.code)
        return
    except Exception as exc:
        update_task(task, status="failed", progress=100, error=str(exc) or "下载失败，请稍后重试。", code="DOWNLOAD_FAILED")
        return

    update_task(
        task,
        status="success",
        progress=100,
        fileName=file_path.name,
        fileUrl=f"/api/files/{task_id}",
        result={"size": file_path.stat().st_size},
    )


def update_task(task: TaskSnapshot, **values) -> None:
    for key, value in values.items():
        setattr(task, key, value)
    task.updatedAt = time.time()
