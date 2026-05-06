import type { MediaFormat, QualityOption, QualityValue } from "@/lib/resolvers/types";

export const defaultQualityHints: Record<QualityValue, { label: string; hint: string }> = {
  best: { label: "最佳", hint: "自动选择当前可用最高质量" },
  "1080p": { label: "1080p", hint: "当前链接可用时展示" },
  "720p": { label: "720p", hint: "速度和体积更均衡" },
  audio: { label: "仅音频", hint: "导出 MP3 音频" }
};

export function buildQualityOptions(formats: MediaFormat[]): QualityOption[] {
  const heights = formats
    .map((format) => format.height)
    .filter((height): height is number => typeof height === "number" && height > 0);

  const hasAudio = formats.some((format) => format.vcodec === "none" || format.resolution === "audio only");
  const maxHeight = heights.length ? Math.max(...heights) : undefined;

  return [
    {
      value: "best",
      ...defaultQualityHints.best,
      available: formats.length > 0,
      hint: maxHeight ? `当前最高约 ${maxHeight}p` : defaultQualityHints.best.hint
    },
    {
      value: "1080p",
      ...defaultQualityHints["1080p"],
      available: heights.some((height) => height >= 1080)
    },
    {
      value: "720p",
      ...defaultQualityHints["720p"],
      available: heights.some((height) => height >= 720)
    },
    {
      value: "audio",
      ...defaultQualityHints.audio,
      available: hasAudio || formats.length > 0
    }
  ];
}

export function pickRecommendedQuality(options: QualityOption[]): QualityValue {
  return options.find((option) => option.value === "1080p" && option.available)?.value
    ?? options.find((option) => option.value === "720p" && option.available)?.value
    ?? options.find((option) => option.value === "best" && option.available)?.value
    ?? "best";
}
