import { randomUUID } from "node:crypto";
import { createReadStream } from "node:fs";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { Readable } from "node:stream";
import { downloadUrlToFileWithFallback } from "@/lib/network";

const thumbnailRoot = path.join(process.cwd(), ".saveany-cache", "thumbnails");
const maxImageBytes = 4 * 1024 * 1024;

export const placeholderThumbnailUrl = "/api/video/thumbnail/placeholder";

type ThumbnailMeta = {
  contentType: string;
  fileName: string;
  sourceUrl: string;
};

export async function cacheRemoteImage(sourceUrl: string, referer?: string): Promise<string> {
  const parsed = new URL(sourceUrl);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Unsupported thumbnail protocol");
  }

  await mkdir(thumbnailRoot, { recursive: true });
  const id = randomUUID();
  const targetDir = path.join(thumbnailRoot, id);
  await mkdir(targetDir, { recursive: true });

  const tmpPath = path.join(targetDir, "thumbnail.tmp");
  const result = await downloadUrlToFileWithFallback(parsed.toString(), tmpPath, {
    referer,
    timeoutMs: 12_000,
    maxBytes: maxImageBytes
  });

  const contentType = result.contentType || "image/jpeg";
  if (!contentType.startsWith("image/") && contentType !== "application/octet-stream") {
    throw new Error("Thumbnail response is not an image");
  }

  const fileName = `thumbnail${extensionFromContentType(contentType, parsed.pathname)}`;
  const filePath = path.join(targetDir, fileName);
  await writeFile(filePath, await readFile(tmpPath));
  await writeFile(
    path.join(targetDir, "meta.json"),
    JSON.stringify({ contentType: normalizeImageContentType(contentType), fileName, sourceUrl } satisfies ThumbnailMeta),
    "utf8"
  );

  return `/api/video/thumbnail/${id}`;
}

export async function resolveThumbnail(id: string) {
  if (id === "placeholder") {
    const svg = Buffer.from(
      `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540"><rect width="960" height="540" rx="32" fill="#eaf1fa"/><rect x="332" y="166" width="296" height="208" rx="42" fill="#1677ff"/><path d="M455 220v100l86-50-86-50Z" fill="white"/><text x="480" y="430" text-anchor="middle" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#496279">SaveAny Preview</text></svg>`
    );

    return {
      contentType: "image/svg+xml; charset=utf-8",
      filePath: "",
      size: svg.byteLength,
      stream: Readable.from(svg)
    };
  }

  if (!/^[0-9a-f-]{36}$/i.test(id)) {
    throw new Error("Thumbnail not found");
  }

  const metaPath = path.join(thumbnailRoot, id, "meta.json");
  const meta = JSON.parse(await readFile(metaPath, "utf8")) as ThumbnailMeta;
  const filePath = path.join(thumbnailRoot, id, meta.fileName);
  const fileStat = await stat(filePath);

  return {
    contentType: meta.contentType,
    filePath,
    size: fileStat.size,
    stream: createReadStream(filePath)
  };
}

function extensionFromContentType(contentType: string, pathname = "") {
  if (contentType.includes("png")) {
    return ".png";
  }

  if (contentType.includes("webp")) {
    return ".webp";
  }

  if (contentType.includes("gif")) {
    return ".gif";
  }

  const lowerPath = pathname.toLowerCase();
  if (lowerPath.endsWith(".png")) return ".png";
  if (lowerPath.endsWith(".webp")) return ".webp";
  if (lowerPath.endsWith(".gif")) return ".gif";

  return ".jpg";
}

function normalizeImageContentType(contentType: string) {
  return contentType === "application/octet-stream" ? "image/jpeg" : contentType;
}
