import { NextResponse } from "next/server";
import { getBackendJson } from "@/lib/backend-client";
import { toApiError } from "@/lib/errors";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{ id: string }>;
};

export async function GET(_request: Request, context: RouteContext) {
  try {
    const { id } = await context.params;
    const payload = await getBackendJson(`/api/tasks/${encodeURIComponent(id)}`, 15_000);
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const apiError = toApiError(error, "任务状态查询失败。");
    return NextResponse.json({ error: apiError.error, code: apiError.code }, { status: apiError.status });
  }
}
