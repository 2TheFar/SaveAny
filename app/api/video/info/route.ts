import { NextResponse } from "next/server";
import { absolutizeBackendUrl, getBackendBaseUrl, postBackendJson } from "@/lib/backend-client";
import { toApiError } from "@/lib/errors";
import { resolveMediaInfo } from "@/lib/resolvers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type BackendInfoPayload = {
  info: {
    thumbnailUrl?: string | null;
  };
};

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));

    if (getBackendBaseUrl()) {
      try {
        const payload = await postBackendJson<BackendInfoPayload>("/api/media/info", { url: body.url });
        return NextResponse.json(
          {
            info: {
              ...payload.info,
              thumbnailUrl: absolutizeBackendUrl(payload.info.thumbnailUrl)
            }
          },
          {
            headers: {
              "Cache-Control": "no-store"
            }
          }
        );
      } catch (backendError) {
        console.warn("FastAPI media info failed, falling back to Next resolver.", backendError);
      }
    }

    const info = await resolveMediaInfo(body.url);
    return NextResponse.json(
      { info },
      {
        headers: {
          "Cache-Control": "no-store"
        }
      }
    );
  } catch (error) {
    const apiError = toApiError(error, "解析失败，请换一个公开视频链接。");
    return NextResponse.json({ error: apiError.error, code: apiError.code }, { status: apiError.status });
  }
}
