import { NextResponse } from "next/server";
import { postBackendJson } from "@/lib/backend-client";
import { toApiError } from "@/lib/errors";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST() {
  try {
    const payload = await postBackendJson("/api/platforms/bilibili/login", {}, 30_000);
    return NextResponse.json(payload, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const apiError = toApiError(error, "B 站登录二维码创建失败，请稍后重试。");
    return NextResponse.json({ error: apiError.error, code: apiError.code }, { status: apiError.status });
  }
}

