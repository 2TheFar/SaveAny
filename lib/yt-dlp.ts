import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readdir, rm, stat } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";
import { SaveAnyError } from "@/lib/errors";
import { assertValidUrl, detectPlatform } from "@/lib/platform";
import { downloadWithDouyin } from "@/lib/resolvers/douyin";
import { buildYtDlpDownloadArgs } from "@/lib/resolvers/yt-dlp";
import type { QualityValue } from "@/lib/resolvers/types";

const execFileAsync = promisify(execFile);

export type VideoQuality = "best" | "1080p" | "720p" | "audio";

export type VideoInfo = {
  title: string;
  uploader?: string;
  thumbnail?: string;
  duration?: number;
  webpageUrl: string;
  formats: Array<{
    id: string;
    ext?: string;
    resolution?: string;
    note?: string;
  }>;
};

export type DownloadResult = {
  id: string;
  fileName: string;
  fileUrl: string;
};

const cacheRoot = path.join(process.cwd(), ".saveany-cache");
const maxCacheAgeMs = 6 * 60 * 60 * 1000;

export function assertQuality(value: unknown): VideoQuality {
  if (value === "best" || value === "1080p" || value === "720p" || value === "audio") {
    return value;
  }

  return "best";
}

export async function getVideoInfo(url: string): Promise<VideoInfo> {
  const { stdout } = await execFileAsync(
    "yt-dlp",
    ["-j", "--no-playlist", "--no-warnings", "--skip-download", url],
    {
      timeout: 45_000,
      maxBuffer: 20 * 1024 * 1024,
      windowsHide: true
    }
  );

  const raw = JSON.parse(stdout);
  const formats = Array.isArray(raw.formats)
    ? raw.formats.slice(-16).map((format: Record<string, unknown>) => ({
        id: String(format.format_id ?? ""),
        ext: typeof format.ext === "string" ? format.ext : undefined,
        resolution: typeof format.resolution === "string" ? format.resolution : undefined,
        note: typeof format.format_note === "string" ? format.format_note : undefined
      }))
    : [];

  return {
    title: String(raw.title ?? "未命名视频"),
    uploader: typeof raw.uploader === "string" ? raw.uploader : undefined,
    thumbnail: typeof raw.thumbnail === "string" ? raw.thumbnail : undefined,
    duration: typeof raw.duration === "number" ? raw.duration : undefined,
    webpageUrl: typeof raw.webpage_url === "string" ? raw.webpage_url : url,
    formats
  };
}

export async function downloadVideo(url: string, quality: VideoQuality): Promise<DownloadResult> {
  await cleanupOldDownloads();
  const safeUrl = assertValidUrl(url);
  if (detectPlatform(safeUrl).platform === "douyin") {
    return downloadWithDouyin(safeUrl, quality as QualityValue);
  }

  const id = randomUUID();
  const jobDir = path.join(cacheRoot, id);
  await mkdir(jobDir, { recursive: true });

  await execFileAsync(
    "yt-dlp",
    [
      "--no-playlist",
      "--restrict-filenames",
      "--no-warnings",
      "-P",
      jobDir,
      "-o",
      "%(title).120B.%(ext)s",
      ...buildYtDlpDownloadArgs(quality as QualityValue),
      safeUrl
    ],
    {
      timeout: 5 * 60_000,
      maxBuffer: 30 * 1024 * 1024,
      windowsHide: true
    }
  );

  const fileName = await findDownloadFile(jobDir);

  return {
    id,
    fileName,
    fileUrl: `/api/video/file/${id}`
  };
}

export async function resolveDownloadFile(id: string) {
  await cleanupOldDownloads();

  if (!/^[0-9a-f-]{36}$/i.test(id)) {
    throw new Error("下载文件不存在。");
  }

  const jobDir = path.join(cacheRoot, id);
  const fileName = await findDownloadFile(jobDir);
  const filePath = path.join(jobDir, fileName);

  return { fileName, filePath };
}

async function cleanupOldDownloads() {
  await mkdir(cacheRoot, { recursive: true });
  const entries = await readdir(cacheRoot);
  const now = Date.now();

  await Promise.all(
    entries.map(async (entry) => {
      if (!/^[0-9a-f-]{36}$/i.test(entry)) {
        return;
      }

      const jobDir = path.join(cacheRoot, entry);
      const fileStat = await stat(jobDir).catch(() => null);
      if (fileStat && fileStat.isDirectory() && now - fileStat.mtimeMs > maxCacheAgeMs) {
        await rm(jobDir, { recursive: true, force: true });
      }
    })
  );
}

async function findDownloadFile(jobDir: string): Promise<string> {
  const entries = await readdir(jobDir);
  const candidates = [];

  for (const entry of entries) {
    if (entry.endsWith(".part") || entry.endsWith(".ytdl") || entry.endsWith(".temp")) {
      continue;
    }

    const filePath = path.join(jobDir, entry);
    const fileStat = await stat(filePath);
    if (fileStat.isFile()) {
      candidates.push({ entry, mtimeMs: fileStat.mtimeMs, size: fileStat.size });
    }
  }

  candidates.sort((a, b) => b.mtimeMs - a.mtimeMs || b.size - a.size);

  if (!candidates[0]) {
    throw new Error("下载已结束，但没有找到可用文件。");
  }

  return candidates[0].entry;
}

export function apiError(error: unknown, fallback = "操作失败，请稍后重试。") {
  if (error instanceof SaveAnyError) {
    return error.message;
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}
