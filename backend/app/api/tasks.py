from fastapi import APIRouter, BackgroundTasks

from app.models.task import DownloadTaskRequest, TaskCreateResponse, TaskSnapshot
from app.services.task_service import create_download_task, get_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/download", response_model=TaskCreateResponse)
def create_download(request: DownloadTaskRequest, background_tasks: BackgroundTasks):
    task = create_download_task(request, background_tasks)
    return TaskCreateResponse(taskId=task.taskId, status=task.status)


@router.get("/{task_id}", response_model=TaskSnapshot)
def task_status(task_id: str):
    return get_task(task_id)

