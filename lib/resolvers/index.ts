import { SaveAnyError } from "@/lib/errors";
import { assertValidUrl, detectPlatform } from "@/lib/platform";
import { resolveWithDouyin } from "@/lib/resolvers/douyin";
import { resolveWithYtDlp } from "@/lib/resolvers/yt-dlp";
import type { ResolvedMediaInfo } from "@/lib/resolvers/types";

export async function resolveMediaInfo(value: unknown): Promise<ResolvedMediaInfo> {
  const url = assertValidUrl(value);
  const platformInfo = detectPlatform(url);

  if (platformInfo.platform === "douyin") {
    return resolveWithDouyin(platformInfo.normalizedUrl);
  }

  return resolveWithYtDlp(platformInfo.normalizedUrl);
}

export function assertResolverUrl(value: unknown): string {
  return assertValidUrl(value);
}

export function assertKnownPlatformForDownload(url: string) {
  const platformInfo = detectPlatform(url);

  if (platformInfo.platform === "douyin") {
    throw new SaveAnyError("UNSUPPORTED_BY_YTDLP", "抖音链接需要专用解析器，当前暂不进入通用下载流程。");
  }

  return platformInfo;
}
