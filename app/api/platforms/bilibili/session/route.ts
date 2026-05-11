import { NextResponse } from "next/server";
import { deleteBackendJson, getBackendJson } from "@/lib/backend-client";
import { toApiError } from "@/lib/errors";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const payload = await getBackendJson("/api/platforms/bilibili/session", 15_000);
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const apiError = toApiError(error, "B 站登录状态查询失败。");
    return NextResponse.json({ error: apiError.error, code: apiError.code }, { status: apiError.status });
  }
}

export async function DELETE() {
  try {
    const payload = await deleteBackendJson("/api/platforms/bilibili/session", 15_000);
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const apiError = toApiError(error, "B 站登录态清除失败。");
    return NextResponse.json({ error: apiError.error, code: apiError.code }, { status: apiError.status });
  }
}
