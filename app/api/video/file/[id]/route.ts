import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { Readable } from "node:stream";
import { toApiError } from "@/lib/errors";
import { resolveDownloadFile } from "@/lib/yt-dlp";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await context.params;
    const { fileName, filePath } = await resolveDownloadFile(id);
    const fileStat = await stat(filePath);
    const stream = Readable.toWeb(createReadStream(filePath)) as ReadableStream;

    return new Response(stream, {
      headers: {
        "Cache-Control": "no-store",
        "Content-Disposition": `attachment; filename*=UTF-8''${encodeURIComponent(fileName)}`,
        "Content-Length": String(fileStat.size),
        "Content-Type": "application/octet-stream"
      }
    });
  } catch (error) {
    const apiError = toApiError(error, "下载文件不存在或已过期。");
    return Response.json({ error: apiError.error, code: apiError.code }, { status: 404 });
  }
}
