from fastapi import APIRouter, BackgroundTasks

from app.models.ai import ChatRequest, ChatResponse
from app.models.task import DownloadTaskRequest, SubtitleCreateRequest, SummaryCreateRequest, TaskCreateResponse, TaskSnapshot
from app.services.task_service import (
    chat_for_summary_task,
    create_download_task,
    create_subtitle_task,
    create_summary_task,
    get_task,
)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/download", response_model=TaskCreateResponse)
def create_download(request: DownloadTaskRequest, background_tasks: BackgroundTasks):
    task = create_download_task(request, background_tasks)
    return TaskCreateResponse(taskId=task.taskId, status=task.status)


@router.post("/subtitles", response_model=TaskCreateResponse)
def create_subtitles(request: SubtitleCreateRequest, background_tasks: BackgroundTasks):
    task = create_subtitle_task(request, background_tasks)
    return TaskCreateResponse(taskId=task.taskId, status=task.status)


@router.post("/summarize", response_model=TaskCreateResponse)
def create_summary(request: SummaryCreateRequest, background_tasks: BackgroundTasks):
    task = create_summary_task(request, background_tasks)
    return TaskCreateResponse(taskId=task.taskId, status=task.status)


@router.get("/{task_id}", response_model=TaskSnapshot)
def task_status(task_id: str):
    return get_task(task_id)


@router.post("/{task_id}/chat", response_model=ChatResponse)
def task_chat(task_id: str, request: ChatRequest):
    return chat_for_summary_task(task_id, request)
