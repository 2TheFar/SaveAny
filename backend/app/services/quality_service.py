from app.models.media import MediaFormat, QualityOption, QualityValue

LABELS: dict[QualityValue, tuple[str, str]] = {
    "best": ("最佳", "自动选择当前可用最高质量"),
    "1080p": ("1080p", "当前链接可用时展示"),
    "720p": ("720p", "速度和体积更均衡"),
    "audio": ("仅音频", "导出 MP3 音频"),
}


def build_quality_options(formats: list[MediaFormat], disable_audio: bool = False) -> list[QualityOption]:
    heights = [item.height for item in formats if item.height and item.height > 0]
    max_height = max(heights) if heights else None
    has_audio = any(item.vcodec == "none" or item.resolution == "audio only" for item in formats)

    best_label, best_hint = LABELS["best"]
    return [
        QualityOption(
            value="best",
            label=best_label,
            hint=f"当前最高约 {max_height}p" if max_height else best_hint,
            available=bool(formats),
        ),
        QualityOption(
            value="1080p",
            label=LABELS["1080p"][0],
            hint=LABELS["1080p"][1],
            available=any(height >= 1080 for height in heights),
        ),
        QualityOption(
            value="720p",
            label=LABELS["720p"][0],
            hint=LABELS["720p"][1],
            available=any(height >= 720 for height in heights),
        ),
        QualityOption(
            value="audio",
            label=LABELS["audio"][0],
            hint="当前解析器先支持视频" if disable_audio else LABELS["audio"][1],
            available=False if disable_audio else has_audio or bool(formats),
        ),
    ]


def pick_recommended_quality(options: list[QualityOption]) -> QualityValue:
    for value in ("1080p", "720p", "best"):
        match = next((item for item in options if item.value == value and item.available), None)
        if match:
            return match.value
    return "best"
