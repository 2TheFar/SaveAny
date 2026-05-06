import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.core.config import BROWSER_USER_AGENT
from app.core.errors import SaveAnyBackendError
from app.models.media import QualityValue
from app.services.douyin_resolver import select_douyin_format
from app.services.resolver_service import resolve_media_info
from app.services.yt_dlp_resolver import map_yt_dlp_error, yt_dlp_quality_args


def download_media(url: str, quality: QualityValue, target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    info = resolve_media_info(url)

    if info.platform == "douyin":
        selected = select_douyin_format(info.formats, quality)
        return download_direct_url(selected.url or "", target_dir, info.title, info.webpageUrl)

    return download_with_yt_dlp(url, quality, target_dir)


def download_with_yt_dlp(url: str, quality: QualityValue, target_dir: Path) -> Path:
    output_template = str(target_dir / "%(title).120B-%(id)s.%(ext)s")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--restrict-filenames",
        "--newline",
        "--no-warnings",
        *yt_dlp_quality_args(quality),
        "-o",
        output_template,
        url,
    ]

    before = snapshot_files(target_dir)
    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20 * 60,
            check=True,
        )
    except FileNotFoundError as exc:
        raise SaveAnyBackendError("DEPENDENCY_MISSING", "服务器未安装 yt-dlp，无法下载视频。", 500) from exc
    except subprocess.CalledProcessError as exc:
        raise map_yt_dlp_error((exc.stderr or "") + (exc.stdout or "")) from exc
    except subprocess.TimeoutExpired as exc:
        raise SaveAnyBackendError("DOWNLOAD_TIMEOUT", "下载超时，请稍后重试。") from exc

    created = [path for path in target_dir.iterdir() if path.is_file() and path.name not in before]
    if not created:
        created = [path for path in target_dir.iterdir() if path.is_file()]
    if not created:
        raise SaveAnyBackendError("DOWNLOAD_FAILED", "下载完成但没有找到生成的文件。")

    return max(created, key=lambda path: path.stat().st_mtime)


def download_direct_url(source_url: str, target_dir: Path, title: str, referer: str | None) -> Path:
    if not source_url:
        raise SaveAnyBackendError("NO_FORMAT", "没有找到可下载的视频地址。")

    suffix = ext_from_url(source_url)
    file_name = f"{safe_file_stem(title)}{suffix}"
    target_path = target_dir / file_name
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer or "https://www.douyin.com/",
    }

    try:
        with requests.get(source_url, headers=headers, timeout=(10, 120), stream=True) as response:
            response.raise_for_status()
            with target_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        file.write(chunk)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        code = "HOTLINK_BLOCKED" if status in {403, 503} else "DOWNLOAD_FAILED"
        raise SaveAnyBackendError(code, f"直链下载失败，平台返回 {status or '未知状态'}。") from exc
    except requests.RequestException as exc:
        raise SaveAnyBackendError("DOWNLOAD_FAILED", "直链下载失败，请稍后重试。") from exc

    if target_path.stat().st_size <= 0:
        raise SaveAnyBackendError("DOWNLOAD_FAILED", "下载文件为空。")

    return target_path


def snapshot_files(target_dir: Path) -> set[str]:
    if not target_dir.exists():
        return set()
    return {path.name for path in target_dir.iterdir() if path.is_file()}


def safe_file_stem(value: str) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value, flags=re.U).strip("._")
    return (normalized or "saveany_video")[:120]


def ext_from_url(source_url: str) -> str:
    path = urlparse(source_url).path.lower()
    for suffix in (".mp4", ".webm", ".mov", ".m4v"):
        if path.endswith(suffix):
            return suffix
    return ".mp4"
