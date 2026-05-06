import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { SaveAnyError } from "@/lib/errors";
import { detectPlatform } from "@/lib/platform";
import { cacheRemoteImage, placeholderThumbnailUrl } from "@/lib/thumbnail-cache";
import { buildQualityOptions, pickRecommendedQuality } from "@/lib/resolvers/quality";
import type { MediaFormat, QualityValue, ResolvedMediaInfo } from "@/lib/resolvers/types";

const execFileAsync = promisify(execFile);

const qualityArgs: Record<QualityValue, string[]> = {
  best: ["-f", "bestvideo*+bestaudio/best"],
  "1080p": ["-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]"],
  "720p": ["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]"],
  audio: ["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "--audio-quality", "192K"]
};

export async function resolveWithYtDlp(url: string): Promise<ResolvedMediaInfo> {
  let stdout = "";

  try {
    const result = await execFileAsync(
      "yt-dlp",
      ["-j", "--no-playlist", "--no-warnings", "--skip-download", url],
      {
        timeout: 45_000,
        maxBuffer: 20 * 1024 * 1024,
        windowsHide: true
      }
    );
    stdout = result.stdout;
  } catch (error) {
    throw mapYtDlpError(error);
  }

  const raw = JSON.parse(stdout);
  const platform = detectPlatform(url).platform;
  const formats = normalizeFormats(raw.formats);
  const availableQualities = buildQualityOptions(formats);
  const thumbnail = typeof raw.thumbnail === "string" ? raw.thumbnail : undefined;
  const thumbnailUrl = thumbnail
    ? await cacheRemoteImage(thumbnail, raw.webpage_url ?? url).catch(() => placeholderThumbnailUrl)
    : placeholderThumbnailUrl;

  return {
    title: String(raw.title ?? "未命名视频"),
    uploader: typeof raw.uploader === "string" ? raw.uploader : undefined,
    thumbnail,
    thumbnailUrl,
    duration: typeof raw.duration === "number" ? raw.duration : undefined,
    webpageUrl: typeof raw.webpage_url === "string" ? raw.webpage_url : url,
    platform,
    resolverUsed: "YtDlpResolver",
    requiresCookie: false,
    availableQualities,
    recommendedQuality: pickRecommendedQuality(availableQualities),
    formats
  };
}

export function buildYtDlpDownloadArgs(quality: QualityValue) {
  return qualityArgs[quality] ?? qualityArgs.best;
}

function normalizeFormats(formats: unknown): MediaFormat[] {
  if (!Array.isArray(formats)) {
    return [];
  }

  return formats.map((format: Record<string, unknown>) => ({
    id: String(format.format_id ?? ""),
    ext: typeof format.ext === "string" ? format.ext : undefined,
    resolution: typeof format.resolution === "string" ? format.resolution : undefined,
    note: typeof format.format_note === "string" ? format.format_note : undefined,
    height: typeof format.height === "number" ? format.height : undefined,
    acodec: typeof format.acodec === "string" ? format.acodec : undefined,
    vcodec: typeof format.vcodec === "string" ? format.vcodec : undefined
  }));
}

function mapYtDlpError(error: unknown): SaveAnyError {
  const message = error instanceof Error ? error.message : String(error);

  if (message.includes("Unsupported URL")) {
    return new SaveAnyError("UNSUPPORTED_BY_YTDLP", "当前链接不被 yt-dlp 直接支持，需要平台专用解析器处理。");
  }

  if (message.includes("cookies") || message.includes("login") || message.includes("Sign in")) {
    return new SaveAnyError("NEEDS_LOGIN", "该内容可能需要平台登录态，SaveAny 公网模式默认不接收用户 Cookie。");
  }

  if (message.includes("403")) {
    return new SaveAnyError("HOTLINK_BLOCKED", "平台拒绝了资源请求，可能存在防盗链或权限限制。");
  }

  if (message.includes("429") || message.includes("rate")) {
    return new SaveAnyError("RATE_LIMITED", "平台请求过于频繁，请稍后重试。");
  }

  if (message.includes("yt-dlp") && message.includes("ENOENT")) {
    return new SaveAnyError("DEPENDENCY_MISSING", "服务器未安装 yt-dlp，无法解析视频。", 500);
  }

  return new SaveAnyError("RESOLVER_FAILED", "解析失败，请确认链接是公开可访问的视频。");
}
