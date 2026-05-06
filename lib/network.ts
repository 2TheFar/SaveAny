import { execFile } from "node:child_process";
import { stat, unlink, writeFile } from "node:fs/promises";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export const browserUserAgent =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";

type RequestOptions = {
  referer?: string;
  timeoutMs?: number;
  headers?: Record<string, string>;
};

type DownloadOptions = RequestOptions & {
  maxBytes?: number;
};

export async function fetchTextWithFallback(url: string, options: RequestOptions = {}) {
  try {
    const response = await fetchWithTimeout(url, options);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    return await response.text();
  } catch {
    const { stdout } = await execFileAsync(
      curlCommand(),
      [
        "-L",
        "--silent",
        "--show-error",
        "--max-time",
        String(Math.ceil((options.timeoutMs ?? 25_000) / 1000)),
        "-A",
        browserUserAgent,
        ...(options.referer ? ["-e", options.referer] : []),
        ...headersToCurlArgs(options.headers),
        url
      ],
      {
        maxBuffer: 12 * 1024 * 1024,
        windowsHide: true
      }
    );
    return stdout;
  }
}

export async function downloadUrlToFileWithFallback(
  url: string,
  targetPath: string,
  options: DownloadOptions = {}
) {
  try {
    const response = await fetchWithTimeout(url, options);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const buffer = Buffer.from(await response.arrayBuffer());
    if (options.maxBytes && buffer.byteLength > options.maxBytes) {
      throw new Error("Downloaded file is too large");
    }

    await writeFile(targetPath, buffer);
    return {
      contentType: response.headers.get("content-type") || inferContentType(url),
      size: buffer.byteLength
    };
  } catch {
    await execFileAsync(
      curlCommand(),
      [
        "-L",
        "--fail",
        "--silent",
        "--show-error",
        "--max-time",
        String(Math.ceil((options.timeoutMs ?? 120_000) / 1000)),
        "-A",
        browserUserAgent,
        ...(options.referer ? ["-e", options.referer] : []),
        ...headersToCurlArgs(options.headers),
        "-o",
        targetPath,
        url
      ],
      {
        maxBuffer: 1024 * 1024,
        windowsHide: true
      }
    );

    const fileStat = await stat(targetPath);
    if (options.maxBytes && fileStat.size > options.maxBytes) {
      await unlink(targetPath).catch(() => undefined);
      throw new Error("Downloaded file is too large");
    }

    return {
      contentType: inferContentType(url),
      size: fileStat.size
    };
  }
}

async function fetchWithTimeout(url: string, options: RequestOptions) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? 25_000);

  try {
    return await fetch(url, {
      headers: {
        "User-Agent": browserUserAgent,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        ...(options.referer ? { Referer: options.referer } : {}),
        ...options.headers
      },
      signal: controller.signal
    });
  } finally {
    clearTimeout(timer);
  }
}

function headersToCurlArgs(headers?: Record<string, string>) {
  if (!headers) {
    return [];
  }

  return Object.entries(headers).flatMap(([key, value]) => ["-H", `${key}: ${value}`]);
}

function curlCommand() {
  return process.platform === "win32" ? "curl.exe" : "curl";
}

function inferContentType(url: string) {
  const path = new URL(url).pathname.toLowerCase();
  if (path.endsWith(".png")) return "image/png";
  if (path.endsWith(".webp")) return "image/webp";
  if (path.endsWith(".gif")) return "image/gif";
  if (path.endsWith(".mp3") || path.endsWith(".m4a")) return "audio/mpeg";
  if (path.endsWith(".mp4")) return "video/mp4";
  if (path.endsWith(".webm")) return "video/webm";
  return "application/octet-stream";
}
