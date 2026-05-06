import shutil
import subprocess
import time

from app.core.config import DOWNLOAD_DIR, THUMBNAIL_DIR


def run_system_check() -> dict:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

    return {
        "ok": True,
        "checkedAt": time.time(),
        "dependencies": {
            "ytDlp": check_command("yt-dlp", "--version"),
            "ffmpeg": check_command("ffmpeg", "-version"),
        },
        "storage": {
            "downloadDir": check_writable_directory(DOWNLOAD_DIR),
            "thumbnailDir": check_writable_directory(THUMBNAIL_DIR),
        },
        "features": {
            "mediaInfo": True,
            "downloadTasks": True,
            "douyinResolver": True,
            "futureTaskTypes": ["subtitle_extract", "audio_extract", "transcribe", "summarize", "batch_download"],
        },
    }


def check_command(command: str, *args: str) -> dict:
    if not shutil.which(command):
        return {"ok": False, "version": None, "error": f"{command} not found"}

    try:
        result = subprocess.run(
            [command, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "version": None, "error": str(exc)}

    first_line = (result.stdout or result.stderr or "").splitlines()[0:1]
    return {"ok": result.returncode == 0, "version": first_line[0] if first_line else None, "error": None}


def check_writable_directory(path) -> dict:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"ok": True, "path": str(path), "error": None}
    except Exception as exc:
        return {"ok": False, "path": str(path), "error": str(exc)}
