import time
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException

from app.core.config import DOWNLOAD_DIR, MAX_CACHE_AGE_SECONDS
from app.core.errors import SaveAnyBackendError
from app.models.ai import ChatRequest, ChatResponse, SubtitleResult, SubtitleTaskRequest, SummaryResult, SummaryTaskRequest
from app.models.task import DownloadTaskRequest, TaskSnapshot
from app.services.ai_cache_service import read_cached_json, write_cached_json
from app.services.deepseek_service import chat_with_deepseek, summarize_with_deepseek
from app.services.download_service import download_media
from app.services.subtitle_service import extract_subtitles

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


def create_subtitle_task(request: SubtitleTaskRequest, background_tasks: BackgroundTasks) -> TaskSnapshot:
    now = time.time()
    task_id = str(uuid4())
    task = TaskSnapshot(
        taskId=task_id,
        type="subtitle_extract",
        status="pending",
        progress=0,
        createdAt=now,
        updatedAt=now,
        expiresAt=now + MAX_CACHE_AGE_SECONDS,
    )
    TASKS[task_id] = task
    background_tasks.add_task(run_subtitle_task, task_id, request)
    return task


def create_summary_task(request: SummaryTaskRequest, background_tasks: BackgroundTasks) -> TaskSnapshot:
    now = time.time()
    task_id = str(uuid4())
    task = TaskSnapshot(
        taskId=task_id,
        type="summarize",
        status="pending",
        progress=0,
        createdAt=now,
        updatedAt=now,
        expiresAt=now + MAX_CACHE_AGE_SECONDS,
    )
    TASKS[task_id] = task
    background_tasks.add_task(run_summary_task, task_id, request)
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


def run_subtitle_task(task_id: str, request: SubtitleTaskRequest) -> None:
    task = TASKS[task_id]
    update_task(task, status="running", progress=15)

    try:
        result = extract_subtitles(request.url, request.languagePriority)
    except SaveAnyBackendError as exc:
        update_task(task, status="failed", progress=100, error=exc.message, code=exc.code)
        return
    except Exception as exc:
        update_task(task, status="failed", progress=100, error=str(exc) or "字幕提取失败。", code="RESOLVER_FAILED")
        return

    update_task(task, status="success", progress=100, result=result.model_dump())


def run_summary_task(task_id: str, request: SummaryTaskRequest) -> None:
    task = TASKS[task_id]
    update_task(task, status="running", progress=20)

    try:
        subtitles = load_subtitle_result(request.subtitleTaskId, request.url)
        cached = read_cached_json(request.url, "summary.json")
        result = SummaryResult.model_validate(cached) if cached else summarize_with_deepseek(subtitles)
        payload = result.model_dump()
        payload["sourceUrl"] = request.url
        write_cached_json(request.url, "summary.json", payload)
    except SaveAnyBackendError as exc:
        update_task(task, status="failed", progress=100, error=exc.message, code=exc.code)
        return
    except Exception as exc:
        update_task(task, status="failed", progress=100, error=str(exc) or "视频总结失败。", code="AI_PROVIDER_FAILED")
        return

    update_task(task, status="success", progress=100, result=payload)


def chat_for_summary_task(task_id: str, request: ChatRequest) -> ChatResponse:
    task = get_task(task_id)
    if task.type != "summarize" or task.status != "success" or not task.result:
        raise SaveAnyBackendError("CHAT_CONTEXT_NOT_READY", "请等待视频总结完成后再提问。", 409)

    summary = SummaryResult.model_validate(task.result)
    source_url = task.result.get("sourceUrl")
    if not isinstance(source_url, str):
        raise SaveAnyBackendError("CHAT_CONTEXT_NOT_READY", "问答上下文不完整，请重新生成总结。", 409)

    subtitles = load_subtitle_result("", source_url)
    history = [item.model_dump() for item in request.history]
    return chat_with_deepseek(request.question, history, summary, subtitles)


def load_subtitle_result(task_id: str, url: str) -> SubtitleResult:
    if task_id:
        subtitle_task = get_task(task_id)
        if subtitle_task.status != "success" or not subtitle_task.result:
            raise SaveAnyBackendError("CHAT_CONTEXT_NOT_READY", "请等待字幕提取完成后再继续。", 409)
        return SubtitleResult.model_validate(subtitle_task.result)

    cached = read_cached_json(url, "subtitles.json")
    if cached:
        return SubtitleResult.model_validate(cached)
    raise SaveAnyBackendError("SUBTITLE_NOT_FOUND", "该视频暂无可用字幕。", 404)


def update_task(task: TaskSnapshot, **values) -> None:
    for key, value in values.items():
        setattr(task, key, value)
    task.updatedAt = time.time()
