from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SubtitleTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    languagePriority: list[str] = Field(default_factory=lambda: ["zh", "en"])


class TranscriptSegment(BaseModel):
    startTime: float
    endTime: float | None = None
    text: str


class SubtitleSource(BaseModel):
    platform: str
    subtitleSource: Literal["yt_dlp", "bilibili_web"]
    language: str


class SubtitleResult(BaseModel):
    transcript: list[TranscriptSegment]
    source: SubtitleSource


class SummaryTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    subtitleTaskId: str
    language: Literal["zh-CN"] = "zh-CN"


class SummaryChapter(BaseModel):
    title: str
    startTime: float
    endTime: float | None = None
    summary: str


class SummarySource(BaseModel):
    platform: str
    subtitleSource: str
    language: str


class SummaryResult(BaseModel):
    summary: str
    keyPoints: list[str]
    chapters: list[SummaryChapter]
    keywords: list[str]
    mindMapMarkdown: str
    source: SummarySource


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    history: list[ChatMessage] = Field(default_factory=list)


class ChatReference(BaseModel):
    startTime: float
    endTime: float | None = None


class ChatResponse(BaseModel):
    answer: str
    references: list[ChatReference]
