import { NextResponse } from "next/server";
import { postBackendJson } from "@/lib/backend-client";
import { toApiError } from "@/lib/errors";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  try {
    const { id } = await context.params;
    const body = await request.json().catch(() => ({}));
    const payload = await postBackendJson(`/api/tasks/${encodeURIComponent(id)}/chat`, body, 60_000);
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const apiError = toApiError(error, "视频问答失败。");
    return NextResponse.json({ error: apiError.error, code: apiError.code }, { status: apiError.status });
  }
}
