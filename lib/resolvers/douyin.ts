import { randomUUID } from "node:crypto";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { SaveAnyError } from "@/lib/errors";
import { browserUserAgent, downloadUrlToFileWithFallback, fetchTextWithFallback } from "@/lib/network";
import { buildQualityOptions, pickRecommendedQuality } from "@/lib/resolvers/quality";
import type { MediaFormat, QualityValue, ResolvedMediaInfo } from "@/lib/resolvers/types";
import { cacheRemoteImage, placeholderThumbnailUrl } from "@/lib/thumbnail-cache";

const cacheRoot = path.join(process.cwd(), ".saveany-cache");

type DouyinVideoDetail = {
  awemeId?: string;
  desc?: string;
  authorInfo?: {
    nickname?: string;
  };
  video?: {
    duration?: number;
    cover?: string;
    coverUrlList?: string[];
    originCover?: string;
    originCoverUrlList?: string[];
    bitRateList?: DouyinBitrate[];
    playAddr?: Array<{ src?: string }>;
    playApi?: string;
  };
};

type DouyinBitrate = {
  gearName?: string;
  qualityType?: number;
  width?: number;
  height?: number;
  bitRate?: number;
  dataSize?: number;
  videoFormat?: string;
  format?: string;
  playAddr?: Array<{ src?: string }>;
  playApi?: string;
};

export function canUseDouyinResolver(url: string) {
  const parsed = new URL(url);
  const hostname = parsed.hostname.replace(/^www\./, "").toLowerCase();
  return hostname.includes("douyin.com");
}

export async function resolveWithDouyin(url: string): Promise<ResolvedMediaInfo> {
  const videoId = extractDouyinVideoId(url);
  const pages = buildCandidatePages(url, videoId);

  let detail: DouyinVideoDetail | undefined;
  let sourcePage = url;

  for (const page of pages) {
    const html = await fetchTextWithFallback(page, {
      referer: "https://www.douyin.com/",
      timeoutMs: 30_000,
      headers: {
        Accept: "text/html,application/json,*/*"
      }
    }).catch(() => "");

    if (!html) {
      continue;
    }

    detail = extractVideoDetailFromPaceData(html, videoId) ?? extractVideoDetailFromLegacyHtml(html, videoId);
    if (detail?.video) {
      sourcePage = page;
      break;
    }
  }

  if (!detail?.video) {
    throw new SaveAnyError(
      "RESOLVER_FAILED",
      "抖音公开解析失败：当前链接可能失效、需要登录，或页面签名策略已变化。"
    );
  }

  const formats = normalizeDouyinFormats(detail);
  if (!formats.length) {
    throw new SaveAnyError("NO_FORMAT", "已识别抖音视频，但没有找到可下载的公开视频地址。");
  }

  const thumbnail = firstString([
    detail.video.cover,
    ...(detail.video.coverUrlList ?? []),
    detail.video.originCover,
    ...(detail.video.originCoverUrlList ?? [])
  ]);
  const thumbnailUrl = thumbnail
    ? await cacheRemoteImage(thumbnail, sourcePage).catch(() => placeholderThumbnailUrl)
    : placeholderThumbnailUrl;
  const availableQualities = buildDouyinQualityOptions(formats);

  return {
    title: detail.desc || `douyin_${detail.awemeId ?? videoId ?? "video"}`,
    uploader: detail.authorInfo?.nickname,
    thumbnail,
    thumbnailUrl,
    duration: typeof detail.video.duration === "number" ? Math.round(detail.video.duration / 1000) : undefined,
    webpageUrl: sourcePage,
    platform: "douyin",
    resolverUsed: "DouyinResolver",
    requiresCookie: false,
    availableQualities,
    recommendedQuality: pickRecommendedQuality(availableQualities),
    formats
  };
}

export async function downloadWithDouyin(url: string, quality: QualityValue) {
  if (quality === "audio") {
    throw new SaveAnyError("NO_FORMAT", "抖音专用解析当前先支持视频下载，暂不导出仅音频。");
  }

  const info = await resolveWithDouyin(url);
  const format = selectDouyinFormat(info.formats, quality);
  if (!format?.url) {
    throw new SaveAnyError("NO_FORMAT", "没有找到匹配当前清晰度的抖音视频地址。");
  }

  const id = randomUUID();
  const jobDir = path.join(cacheRoot, id);
  await mkdir(jobDir, { recursive: true });

  const fileName = `${safeFileName(info.title)}.${format.ext ?? "mp4"}`;
  const filePath = path.join(jobDir, fileName);
  await downloadUrlToFileWithFallback(format.url, filePath, {
    referer: "https://www.douyin.com/",
    timeoutMs: 5 * 60_000,
    headers: {
      Accept: "video/*,*/*",
      "User-Agent": browserUserAgent
    }
  });

  return {
    id,
    fileName,
    fileUrl: `/api/video/file/${id}`
  };
}

function buildCandidatePages(url: string, videoId?: string) {
  const pages = new Set<string>([url]);

  if (videoId) {
    pages.add(`https://www.douyin.com/jingxuan?modal_id=${videoId}`);
    pages.add(`https://www.iesdouyin.com/share/video/${videoId}/`);
  }

  return [...pages];
}

function extractDouyinVideoId(url: string) {
  const parsed = new URL(url);

  for (const key of ["modal_id", "item_ids", "group_id", "aweme_id"]) {
    const value = parsed.searchParams.get(key);
    const match = value?.match(/\d{8,24}/);
    if (match) {
      return match[0];
    }
  }

  const pathMatch = parsed.pathname.match(/\/(?:video|note)\/(\d{8,24})/) ?? parsed.pathname.match(/\/(\d{8,24})(?:\/|$)/);
  if (pathMatch) {
    return pathMatch[1];
  }

  const fallback = url.match(/(?<!\d)(\d{8,24})(?!\d)/);
  return fallback?.[1];
}

function extractVideoDetailFromPaceData(html: string, videoId?: string) {
  const payloads = html.matchAll(/self\.__pace_f\.push\(\[1,("(?:\\.|[^"\\])*")\]\)<\/script>/g);

  for (const match of payloads) {
    const raw = safeJsonParse<string>(match[1]);
    if (!raw) {
      continue;
    }

    const text = raw.startsWith("%") ? safeDecodeURIComponent(raw) : raw;
    if (!text.includes("videoDetail") && !text.includes("awemeId")) {
      continue;
    }

    const parsed = safeJsonParse<unknown>(text);
    const details = collectVideoDetails(parsed);
    const exact = videoId ? details.find((item) => item.awemeId === videoId) : undefined;
    const usable = exact ?? details.find((item) => item.video?.bitRateList?.length || item.video?.playAddr?.length);
    if (usable) {
      return usable;
    }
  }
}

function extractVideoDetailFromLegacyHtml(html: string, videoId?: string): DouyinVideoDetail | undefined {
  const body = html.replace(/\\u002F/g, "/");
  const videoUri = body.match(/"video":\{"play_addr":\{"uri":"([a-z0-9]+)"/i)?.[1];
  if (!videoUri) {
    return undefined;
  }

  return {
    awemeId: videoId,
    desc: body.match(/"desc":\s*"([^"]+)"/)?.[1],
    authorInfo: {
      nickname: body.match(/"nickname":\s*"([^"]+)"/)?.[1]
    },
    video: {
      playApi: `https://www.iesdouyin.com/aweme/v1/play/?video_id=${videoUri}&ratio=1080p&line=0`,
      bitRateList: [
        {
          gearName: "1080p",
          height: 1080,
          videoFormat: "mp4",
          playApi: `https://www.iesdouyin.com/aweme/v1/play/?video_id=${videoUri}&ratio=1080p&line=0`
        }
      ]
    }
  };
}

function collectVideoDetails(value: unknown, output: DouyinVideoDetail[] = [], seen = new Set<object>()) {
  if (!value || typeof value !== "object") {
    return output;
  }

  if (seen.has(value)) {
    return output;
  }
  seen.add(value);

  const record = value as Record<string, unknown>;
  if (record.videoDetail && typeof record.videoDetail === "object") {
    output.push(record.videoDetail as DouyinVideoDetail);
  }

  if (record.awemeId && record.video && typeof record.video === "object") {
    output.push(record as DouyinVideoDetail);
  }

  for (const child of Object.values(record)) {
    collectVideoDetails(child, output, seen);
  }

  return output;
}

function normalizeDouyinFormats(detail: DouyinVideoDetail): MediaFormat[] {
  const bitrates = detail.video?.bitRateList ?? [];
  const formats: MediaFormat[] = [];

  bitrates.forEach((item, index) => {
    const url = firstString([...(item.playAddr?.map((addr) => addr.src) ?? []), item.playApi]);
    if (!url) {
      return;
    }

    formats.push({
      id: String(item.gearName ?? item.qualityType ?? index),
      ext: item.videoFormat === "dash" || item.format === "dash" ? "mp4" : item.videoFormat ?? "mp4",
      resolution: item.height ? `${item.height}p` : undefined,
      note: item.gearName,
      height: item.height,
      vcodec: "unknown",
      acodec: "unknown",
      url
    });
  });

  if (formats.length) {
    return formats.sort((a, b) => (b.height ?? 0) - (a.height ?? 0));
  }

  const playUrl = firstString([...(detail.video?.playAddr?.map((addr) => addr.src) ?? []), detail.video?.playApi]);
  return playUrl
    ? [
        {
          id: "play",
          ext: "mp4",
          resolution: detail.video?.duration ? "video" : undefined,
          vcodec: "unknown",
          acodec: "unknown",
          url: playUrl
        }
      ]
    : [];
}

function buildDouyinQualityOptions(formats: MediaFormat[]) {
  return buildQualityOptions(formats).map((option) =>
    option.value === "audio"
      ? {
          ...option,
          available: false,
          hint: "抖音专用解析当前先支持视频"
        }
      : option
  );
}

function selectDouyinFormat(formats: MediaFormat[], quality: QualityValue) {
  const candidates = formats
    .filter((format) => Boolean(format.url))
    .sort((a, b) => (b.height ?? 0) - (a.height ?? 0));

  if (quality === "1080p") {
    return candidates.find((format) => (format.height ?? 0) <= 1080) ?? candidates[0];
  }

  if (quality === "720p") {
    return candidates.find((format) => (format.height ?? 0) <= 720) ?? candidates[candidates.length - 1];
  }

  return candidates[0];
}

function firstString(values: Array<string | undefined | null>) {
  return values.find((value): value is string => typeof value === "string" && value.length > 0);
}

function safeDecodeURIComponent(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function safeJsonParse<T>(value: string): T | undefined {
  try {
    return JSON.parse(value) as T;
  } catch {
    return undefined;
  }
}

function safeFileName(value: string) {
  const normalized = value
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);

  return normalized || "douyin_video";
}
