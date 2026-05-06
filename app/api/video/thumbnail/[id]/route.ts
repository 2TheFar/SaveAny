import { Readable } from "node:stream";
import { resolveThumbnail } from "@/lib/thumbnail-cache";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_request: Request, context: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await context.params;
    const thumbnail = await resolveThumbnail(id);
    const stream = Readable.toWeb(thumbnail.stream) as ReadableStream;

    return new Response(stream, {
      headers: {
        "Cache-Control": "public, max-age=21600",
        "Content-Length": String(thumbnail.size),
        "Content-Type": thumbnail.contentType
      }
    });
  } catch {
    return new Response(null, { status: 404 });
  }
}
