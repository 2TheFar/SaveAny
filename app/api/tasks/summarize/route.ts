import { NextResponse } from "next/server";
import { postBackendJson } from "@/lib/backend-client";
import { toApiError } from "@/lib/errors";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const payload = await postBackendJson("/api/tasks/summarize", body, 15_000);
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const apiError = toApiError(error, "总结任务创建失败。");
    return NextResponse.json({ error: apiError.error, code: apiError.code }, { status: apiError.status });
  }
}
