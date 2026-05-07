from functools import lru_cache
from pathlib import Path

import ctranslate2
from faster_whisper import WhisperModel

from app.core.config import ASR_COMPUTE_TYPE, ASR_CPU_FALLBACK_MODEL, ASR_DEVICE, ASR_MODEL, MODEL_DIR
from app.core.errors import SaveAnyBackendError
from app.models.ai import SubtitleResult, SubtitleSource, TranscriptSegment


def transcribe_with_asr(audio_path: Path, platform: str) -> SubtitleResult:
    attempts = build_asr_attempts()
    last_error: Exception | None = None

    for model_name, device, compute_type in attempts:
        try:
            model = load_model(model_name, device, compute_type)
            segments_iter, info = model.transcribe(
                str(audio_path),
                beam_size=5,
                vad_filter=True,
            )
            transcript = [
                TranscriptSegment(
                    startTime=float(segment.start),
                    endTime=float(segment.end),
                    text=(segment.text or "").strip(),
                )
                for segment in segments_iter
                if (segment.text or "").strip()
            ]
            if not transcript:
                raise SaveAnyBackendError("TRANSCRIBE_EMPTY", "ASR 未识别出可用字幕。", 502)

            language = str(getattr(info, "language", "") or "unknown")
            return SubtitleResult(
                transcript=transcript,
                source=SubtitleSource(
                    platform=platform,
                    subtitleSource="asr_faster_whisper",
                    language=language,
                ),
            )
        except Exception as exc:  # pragma: no cover - fallback behavior matters more than exact exception type
            last_error = exc
            continue

    if isinstance(last_error, SaveAnyBackendError):
        raise last_error
    raise SaveAnyBackendError("TRANSCRIBE_FAILED", str(last_error) or "ASR 转写失败。", 502)


def build_asr_attempts() -> list[tuple[str, str, str]]:
    attempts: list[tuple[str, str, str]] = []
    preferred_gpu = ASR_DEVICE in {"cuda", "auto"}
    if cuda_device_count() > 0 and preferred_gpu:
        attempts.append((ASR_MODEL, "cuda", ASR_COMPUTE_TYPE))
    attempts.append((ASR_MODEL, "cpu", "int8"))
    if ASR_CPU_FALLBACK_MODEL != ASR_MODEL:
        attempts.append((ASR_CPU_FALLBACK_MODEL, "cpu", "int8"))
    return attempts


@lru_cache(maxsize=6)
def load_model(model_name: str, device: str, compute_type: str) -> WhisperModel:
    try:
        return WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            download_root=str(MODEL_DIR),
        )
    except Exception as exc:  # pragma: no cover - depends on host runtime
        raise SaveAnyBackendError(
            "ASR_MODEL_LOAD_FAILED",
            f"无法加载 ASR 模型 {model_name} ({device}/{compute_type})。",
            500,
        ) from exc


def cuda_device_count() -> int:
    try:
        return int(ctranslate2.get_cuda_device_count())
    except Exception:
        return 0


def asr_runtime_info() -> dict:
    preferred_device = ASR_DEVICE
    if ASR_DEVICE == "auto":
        preferred_device = "cuda" if cuda_device_count() > 0 else "cpu"
    return {
        "model": ASR_MODEL,
        "preferredDevice": preferred_device,
        "configuredDevice": ASR_DEVICE,
        "preferredComputeType": ASR_COMPUTE_TYPE,
        "cpuFallbackModel": ASR_CPU_FALLBACK_MODEL,
        "cudaDeviceCount": cuda_device_count(),
        "modelRoot": str(MODEL_DIR),
    }
