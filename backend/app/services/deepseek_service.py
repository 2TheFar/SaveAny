import json
import os
import time
from typing import Any

import requests

from app.core import config as _config  # Ensure backend/.env is loaded before reading env vars.
from app.core.errors import SaveAnyBackendError
from app.models.ai import ChatReference, ChatResponse, SubtitleResult, SummaryResult

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"


def summarize_with_deepseek(subtitles: SubtitleResult) -> SummaryResult:
    payload = call_deepseek_json(
        [
            {
                "role": "system",
                "content": (
                    "你是 SaveAny 的视频学习助手。请基于字幕生成中文学习笔记，并只返回 JSON。"
                    "不要编造字幕中没有的信息。mindMapMarkdown 必须是适合 Markmap 的 Markdown 层级结构。"
                ),
            },
            {
                "role": "user",
                "content": build_summary_prompt(subtitles),
            },
        ],
        max_tokens=4096,
    )
    payload["source"] = subtitles.source.model_dump()
    try:
        return SummaryResult.model_validate(payload)
    except Exception as exc:
        raise SaveAnyBackendError("AI_RESPONSE_INVALID", "AI 返回的总结结构无法解析。", 502) from exc


def chat_with_deepseek(question: str, history: list[dict[str, str]], summary: SummaryResult, subtitles: SubtitleResult) -> ChatResponse:
    payload = call_deepseek_json(
        [
            {
                "role": "system",
                "content": (
                    "你是 SaveAny 的视频问答助手。只能根据给定字幕和摘要回答。"
                    "请只返回 JSON，references 只包含相关字幕的 startTime/endTime。"
                ),
            },
            {
                "role": "user",
                "content": build_chat_prompt(question, history, summary, subtitles),
            },
        ],
        max_tokens=2048,
    )
    try:
        return ChatResponse.model_validate(payload)
    except Exception as exc:
        raise SaveAnyBackendError("AI_RESPONSE_INVALID", "AI 返回的问答结构无法解析。", 502) from exc


def call_deepseek_json(messages: list[dict[str, str]], max_tokens: int) -> dict[str, Any]:
    response = post_deepseek(
        {
            "model": DEEPSEEK_MODEL,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "stream": False,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
    )

    try:
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise SaveAnyBackendError("AI_RESPONSE_INVALID", "DeepSeek 返回内容不是有效 JSON。", 502) from exc


def ping_deepseek() -> dict[str, Any]:
    started_at = time.perf_counter()
    response = post_deepseek(
        {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "Reply with pong."},
                {"role": "user", "content": "ping"},
            ],
            "stream": False,
            "temperature": 0,
            "max_tokens": 16,
        },
        timeout=(10, 60),
    )

    try:
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise SaveAnyBackendError("AI_RESPONSE_INVALID", "DeepSeek 连通性检测返回结构无效。", 502) from exc

    return {
        "ok": True,
        "model": DEEPSEEK_MODEL,
        "latencyMs": round((time.perf_counter() - started_at) * 1000, 2),
        "message": content,
        "error": None,
    }


def post_deepseek(payload: dict[str, Any], timeout: tuple[int, int] = (10, 120)) -> requests.Response:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SaveAnyBackendError("AI_PROVIDER_NOT_CONFIGURED", "请先配置 DeepSeek API Key。", 503)

    try:
        response = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        return response
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        raise SaveAnyBackendError("AI_PROVIDER_FAILED", f"DeepSeek API 调用失败：{status}。", 502) from exc
    except requests.RequestException as exc:
        raise SaveAnyBackendError("AI_PROVIDER_FAILED", "DeepSeek API 暂时不可用，请稍后重试。", 502) from exc


def build_summary_prompt(subtitles: SubtitleResult) -> str:
    transcript = compact_transcript(subtitles, max_chars=26000)
    return f"""
请根据下面的视频字幕生成学习笔记 JSON。

输出 JSON 结构必须为：
{{
  "summary": "200字以内整体摘要",
  "keyPoints": ["核心要点"],
  "chapters": [
    {{"title": "章节标题", "startTime": 0, "endTime": 120, "summary": "章节摘要"}}
  ],
  "keywords": ["关键词"],
  "mindMapMarkdown": "# 视频主题\\n## 分支\\n- 要点"
}}

要求：
- 所有内容使用简体中文。
- chapters 必须尽量覆盖完整视频，并使用字幕时间戳。
- mindMapMarkdown 必须从 # 一级标题开始，适合 Markmap 展示。
- 如果字幕信息不足，请如实简化，不要编造。

字幕：
{transcript}
""".strip()


def build_chat_prompt(
    question: str,
    history: list[dict[str, str]],
    summary: SummaryResult,
    subtitles: SubtitleResult,
) -> str:
    transcript = compact_transcript(subtitles, max_chars=20000)
    history_text = "\n".join(f"{item.get('role')}: {item.get('content')}" for item in history[-6:])
    return f"""
请基于视频学习笔记和字幕回答用户问题。

输出 JSON 结构必须为：
{{
  "answer": "回答内容",
  "references": [
    {{"startTime": 0, "endTime": 12}}
  ]
}}

学习笔记摘要：
{summary.summary}

核心要点：
{json.dumps(summary.keyPoints, ensure_ascii=False)}

最近对话：
{history_text or "无"}

用户问题：
{question}

字幕：
{transcript}
""".strip()


def compact_transcript(subtitles: SubtitleResult, max_chars: int) -> str:
    lines: list[str] = []
    total = 0
    for segment in subtitles.transcript:
        end = "" if segment.endTime is None else f"-{segment.endTime:.1f}"
        line = f"[{segment.startTime:.1f}{end}] {segment.text}"
        total += len(line)
        if total > max_chars:
            lines.append("[已截断，后续字幕因上下文长度限制未发送]")
            break
        lines.append(line)
    return "\n".join(lines)
