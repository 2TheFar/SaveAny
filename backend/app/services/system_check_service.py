import importlib.util
import os
import shutil
import subprocess
import time
from pathlib import Path

from app.core.config import (
    ASR_COMPUTE_TYPE,
    ASR_DEVICE,
    ASR_MODEL,
    DOWNLOAD_DIR,
    MODEL_DIR,
    SAVEANY_BBDOWN_PATH,
    SAVEANY_BBDOWN_WORK_DIR,
    SAVEANY_BILIBILI_AUTH_FILE,
    THUMBNAIL_DIR,
    resolve_bbdown_executable,
)
from app.services.asr_service import asr_runtime_info


def run_system_check() -> dict:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    runtime_info = asr_runtime_info()

    return {
        "ok": True,
        "checkedAt": time.time(),
        "dependencies": {
            "ytDlp": check_command("yt-dlp", "--version"),
            "bbdown": check_bbdown(),
            "ffmpeg": check_command("ffmpeg", "-version"),
            "qrcode": check_python_module("qrcode"),
            "fasterWhisper": check_python_module("faster_whisper"),
        },
        "storage": {
            "downloadDir": check_writable_directory(DOWNLOAD_DIR),
            "thumbnailDir": check_writable_directory(THUMBNAIL_DIR),
            "modelDir": check_writable_directory(MODEL_DIR),
            "bbdownWorkDir": check_writable_directory(SAVEANY_BBDOWN_WORK_DIR),
        },
        "runtime": {
            "cuda": {
                "ok": runtime_info["cudaDeviceCount"] > 0,
                "deviceCount": runtime_info["cudaDeviceCount"],
            },
            "asr": {
                "model": runtime_info["model"],
                "preferredDevice": runtime_info["preferredDevice"],
                "configuredDevice": runtime_info["configuredDevice"],
                "preferredComputeType": runtime_info["preferredComputeType"],
                "defaultModelPresent": model_hint_exists(ASR_MODEL),
            },
        },
        "env": {
            "deepseekApiKey": {"ok": bool(os.environ.get("DEEPSEEK_API_KEY"))},
            "bilibiliAuthFile": {"ok": SAVEANY_BILIBILI_AUTH_FILE.exists(), "path": str(SAVEANY_BILIBILI_AUTH_FILE)},
        },
        "features": {
            "mediaInfo": True,
            "downloadTasks": True,
            "douyinResolver": True,
            "bilibiliResolver": True,
            "bilibiliQrLogin": True,
            "asrFallback": True,
            "deepseekConnectivity": True,
            "futureTaskTypes": ["subtitle_extract", "audio_extract", "transcribe", "summarize", "batch_download"],
        },
    }


def check_command(command: str, *args: str) -> dict:
    resolved = shutil.which(command)
    if not resolved and not Path(command).exists():
        return {"ok": False, "version": None, "path": None, "error": f"{command} not found"}
    executable = resolved or command

    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "version": None, "path": executable, "error": str(exc)}

    first_line = (result.stdout or result.stderr or "").splitlines()[0:1]
    return {"ok": result.returncode == 0, "version": first_line[0] if first_line else None, "path": executable, "error": None}


def check_bbdown() -> dict:
    executable = resolve_bbdown_executable()
    if not executable:
        return {"ok": False, "version": None, "path": None, "error": f"{SAVEANY_BBDOWN_PATH} not found"}

    try:
        result = subprocess.run(
            [executable, "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "version": None, "path": executable, "error": str(exc)}

    output = result.stdout or result.stderr or ""
    first_line = output.splitlines()[0:1]
    ok = result.returncode == 0 and "BBDown" in output
    return {
        "ok": ok,
        "version": first_line[0] if first_line else None,
        "path": executable,
        "error": None if ok else output.strip()[:300] or "BBDown help check failed",
    }


def check_writable_directory(path) -> dict:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"ok": True, "path": str(path), "error": None}
    except Exception as exc:
        return {"ok": False, "path": str(path), "error": str(exc)}


def check_python_module(module_name: str) -> dict:
    spec = importlib.util.find_spec(module_name)
    return {"ok": spec is not None, "module": module_name, "error": None if spec else f"{module_name} not installed"}


def model_hint_exists(model_name: str) -> bool:
    normalized = model_name.lower().replace("/", "-")
    try:
        for path in Path(MODEL_DIR).iterdir():
            if normalized in path.name.lower():
                return True
    except OSError:
        return False
    return False
