import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.errors import SaveAnyBackendError
from app.services.deepseek_service import ping_deepseek, summarize_with_deepseek
from app.services.platform_service import detect_platform
from app.services.subtitle_service import extract_subtitles
from app.services.system_check_service import run_system_check

TEST_URLS = [
    "https://www.bilibili.com/video/BV1fEdwBVEqJ/?spm_id_from=333.1365.list.card_archive.click",
    "https://www.bilibili.com/video/BV1wGdwBEEQf/?spm_id_from=333.1365.list.card_archive.click",
    "https://www.bilibili.com/video/BV1Ck9EYvEzk/?p=8&spm_id_from=333.1365.top_right_bar_window_history.content.click&vd_source=678b327a2c9d2de9fd219b4ae4c738da",
    "https://www.douyin.com/jingxuan",
    "https://www.youtube.com/watch?v=Z5xczbxykpo",
]


def main() -> int:
    started_at = time.time()
    report_lines: list[str] = []
    report_lines.append("# SaveAny 字幕链路重构执行报告")
    report_lines.append("")
    report_lines.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(started_at))}")
    report_lines.append("- 执行范围：平台字幕优先、ASR 兜底、DeepSeek 连通性、总结回归")
    report_lines.append("")

    system_info = run_system_check()
    report_lines.append("## 依赖环境")
    report_lines.append("")
    report_lines.append("```json")
    report_lines.append(json_dump(system_info))
    report_lines.append("```")
    report_lines.append("")

    report_lines.append("## DeepSeek 连通性")
    report_lines.append("")
    try:
        deepseek_result = ping_deepseek()
        report_lines.append("```json")
        report_lines.append(json_dump(deepseek_result))
        report_lines.append("```")
    except Exception as exc:
        report_lines.append("```json")
        report_lines.append(json_dump(error_payload(exc)))
        report_lines.append("```")
    report_lines.append("")

    report_lines.append("## 自动测试结果")
    report_lines.append("")
    report_lines.append("| URL | Platform | Attempt Path | Final Source | Segments | ASR | Summary | DeepSeek | Elapsed(s) |")
    report_lines.append("| --- | --- | --- | --- | ---: | --- | --- | --- | ---: |")

    details: list[str] = []
    for url in TEST_URLS:
        row, detail = run_case(url)
        report_lines.append(row)
        details.extend(detail)

    report_lines.append("")
    report_lines.append("## 失败案例与原因")
    report_lines.append("")
    if details:
        report_lines.extend(details)
    else:
        report_lines.append("- 无")
    report_lines.append("")
    report_lines.append("## 后续风险与建议")
    report_lines.append("")
    report_lines.append("- Bilibili AI/自动字幕字段在不同接口上的暴露并不稳定，因此实现中保留了多路平台字幕探测与 ASR 兜底。")
    report_lines.append("- Douyin 当前实现默认直接走 ASR，不依赖创作端自动字幕能力。")
    report_lines.append("- DeepSeek 连通性测试依赖运行脚本时的环境变量或 `backend/.env` 注入。")
    report_lines.append("- `faster-whisper small` 为默认模型，若 CPU fallback 过慢，可通过 `.env` 下调模型。")
    report_lines.append("")

    report_path = ROOT_DIR / "docs" / "REPORT_SUBTITLE_PIPELINE_2026-05-07.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"REPORT_WRITTEN {report_path}")
    return 0


def run_case(url: str) -> tuple[str, list[str]]:
    started = time.perf_counter()
    platform = detect_platform(url)
    details: list[str] = []
    subtitle_result = None
    subtitle_error = None
    summary_error = None
    deepseek_ok = "no"

    try:
        subtitle_result = extract_subtitles(url, ["zh", "en"])
    except Exception as exc:
        subtitle_error = exc

    if subtitle_result is not None:
        try:
            summarize_with_deepseek(subtitle_result)
            deepseek_ok = "yes"
            summary_state = "success"
        except Exception as exc:
            summary_error = exc
            summary_state = f"failed:{error_code(exc)}"
    else:
        summary_state = "skipped"

    final_source = subtitle_result.source.subtitleSource if subtitle_result else f"failed:{error_code(subtitle_error)}"
    segments = len(subtitle_result.transcript) if subtitle_result else 0
    asr_used = "yes" if subtitle_result and subtitle_result.source.subtitleSource == "asr_faster_whisper" else "no"
    attempt_path = infer_attempt_path(platform, final_source)
    elapsed = round(time.perf_counter() - started, 2)

    if subtitle_error:
        details.append(f"- `{url}` 字幕失败：{format_error(subtitle_error)}")
    if summary_error:
        details.append(f"- `{url}` 总结失败：{format_error(summary_error)}")

    row = (
        f"| {url} | {platform} | {attempt_path} | {final_source} | {segments} | "
        f"{asr_used} | {summary_state} | {deepseek_ok} | {elapsed} |"
    )
    return row, details


def infer_attempt_path(platform: str, final_source: str) -> str:
    if platform == "douyin":
        return "platform_none->asr"
    if final_source == "asr_faster_whisper":
        return "platform_api->asr"
    return "platform_api"


def error_payload(exc: Exception) -> dict:
    return {
        "ok": False,
        "error": format_error(exc),
        "code": error_code(exc),
    }


def error_code(exc: Exception | None) -> str:
    if isinstance(exc, SaveAnyBackendError):
        return exc.code
    return type(exc).__name__ if exc else "unknown"


def format_error(exc: Exception) -> str:
    if isinstance(exc, SaveAnyBackendError):
        return f"{exc.code}: {exc.message}"
    return str(exc) or type(exc).__name__


def json_dump(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
