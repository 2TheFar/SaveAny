import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.core.config import BROWSER_USER_AGENT
from app.core.errors import SaveAnyBackendError
from app.models.media import QualityValue
from app.services.ai_cache_service import cache_dir_for_url
from app.services.douyin_resolver import select_douyin_format
from app.services.platform_service import assert_valid_url
from app.services.resolver_service import resolve_media_info
from app.services.yt_dlp_resolver import map_yt_dlp_error


def prepare_audio_for_transcription(url: str) -> Path:
    safe_url = assert_valid_url(url)
    cache_dir = cache_dir_for_url(safe_url)
    source_path = cache_dir / "transcribe-source"
    audio_path = cache_dir / "transcribe-audio.wav"
    if audio_path.exists() and audio_path.stat().st_size > 0:
        return audio_path

    media_info = resolve_media_info(safe_url)

    if media_info.platform == "douyin":
        selected = select_douyin_format(media_info.formats, "best")
        source_file = download_direct_media(
            selected.url or "",
            cache_dir,
            source_path.with_suffix(ext_from_url(selected.url or "")),
            media_info.webpageUrl,
        )
    else:
        source_file = download_audio_source_with_yt_dlp(safe_url, source_path)

    transcode_for_asr(source_file, audio_path)
    return audio_path


def download_audio_source_with_yt_dlp(url: str, output_stem: Path) -> Path:
    output_template = str(output_stem.with_name(f"{output_stem.name}.%(ext)s"))
    try:
        subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "--restrict-filenames",
                "--no-warnings",
                "-f",
                best_audio_selector(),
                "-o",
                output_template,
                url,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15 * 60,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SaveAnyBackendError("DEPENDENCY_MISSING", "服务器未安装 yt-dlp，无法提取音频。", 500) from exc
    except subprocess.CalledProcessError as exc:
        raise map_yt_dlp_error((exc.stderr or "") + (exc.stdout or "")) from exc
    except subprocess.TimeoutExpired as exc:
        raise SaveAnyBackendError("DOWNLOAD_TIMEOUT", "音频提取超时，请稍后重试。") from exc

    candidates = sorted(output_stem.parent.glob(f"{output_stem.name}.*"))
    if not candidates:
        raise SaveAnyBackendError("DOWNLOAD_FAILED", "音频下载完成但没有找到源文件。")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def transcode_for_asr(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10 * 60,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SaveAnyBackendError("DEPENDENCY_MISSING", "服务器未安装 ffmpeg，无法转写音频。", 500) from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or "") + (exc.stdout or "")
        raise SaveAnyBackendError("AUDIO_EXTRACT_FAILED", message.strip() or "音频转码失败。", 500) from exc
    except subprocess.TimeoutExpired as exc:
        raise SaveAnyBackendError("AUDIO_EXTRACT_FAILED", "音频转码超时，请稍后重试。", 500) from exc


def download_direct_media(source_url: str, target_dir: Path, target_path: Path, referer: str | None) -> Path:
    if not source_url:
        raise SaveAnyBackendError("NO_FORMAT", "没有找到可下载的媒体地址。")

    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer or "https://www.douyin.com/",
    }
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        with requests.get(source_url, headers=headers, timeout=(10, 180), stream=True) as response:
            response.raise_for_status()
            with target_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        file.write(chunk)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        code = "HOTLINK_BLOCKED" if status in {403, 503} else "DOWNLOAD_FAILED"
        raise SaveAnyBackendError(code, f"媒体下载失败，平台返回 {status or '未知状态'}。") from exc
    except requests.RequestException as exc:
        raise SaveAnyBackendError("DOWNLOAD_FAILED", "媒体下载失败，请稍后重试。") from exc

    if not target_path.exists() or target_path.stat().st_size <= 0:
        raise SaveAnyBackendError("DOWNLOAD_FAILED", "媒体下载后为空文件。")
    return target_path


def best_audio_selector() -> QualityValue | str:
    return "bestaudio[ext=m4a]/bestaudio[acodec!=none]/bestaudio/best"


def ext_from_url(source_url: str) -> str:
    path = urlparse(source_url).path.lower()
    for suffix in (".mp4", ".webm", ".m4a", ".mp3", ".aac", ".wav", ".mov"):
        if path.endswith(suffix):
            return suffix
    return ".mp4"
