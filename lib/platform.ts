import { SaveAnyError } from "@/lib/errors";

export type Platform = "youtube" | "bilibili" | "douyin" | "tiktok" | "vimeo" | "x" | "instagram" | "unknown";

export type PlatformInfo = {
  platform: Platform;
  normalizedUrl: string;
  hostname: string;
};

export function assertValidUrl(value: unknown): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new SaveAnyError("INVALID_URL", "请先粘贴一个公开视频链接。");
  }

  let parsed: URL;
  try {
    parsed = new URL(value.trim());
  } catch {
    throw new SaveAnyError("INVALID_URL", "链接格式不正确，请检查后重试。");
  }

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new SaveAnyError("INVALID_URL", "仅支持 http 或 https 开头的视频链接。");
  }

  return parsed.toString();
}

export function detectPlatform(inputUrl: string): PlatformInfo {
  const url = new URL(inputUrl);
  const hostname = url.hostname.replace(/^www\./, "").toLowerCase();

  return {
    platform: hostnameToPlatform(hostname),
    normalizedUrl: url.toString(),
    hostname
  };
}

function hostnameToPlatform(hostname: string): Platform {
  if (hostname.includes("youtube.com") || hostname === "youtu.be") {
    return "youtube";
  }

  if (hostname.includes("bilibili.com") || hostname === "b23.tv") {
    return "bilibili";
  }

  if (hostname.includes("douyin.com")) {
    return "douyin";
  }

  if (hostname.includes("tiktok.com")) {
    return "tiktok";
  }

  if (hostname.includes("vimeo.com")) {
    return "vimeo";
  }

  if (hostname === "x.com" || hostname === "twitter.com") {
    return "x";
  }

  if (hostname.includes("instagram.com")) {
    return "instagram";
  }

  return "unknown";
}
