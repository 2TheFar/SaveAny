import { NextResponse } from "next/server";
import { absolutizeBackendUrl, getBackendBaseUrl, getBackendJson, postBackendJson } from "@/lib/backend-client";
import { toApiError } from "@/lib/errors";
import { assertValidUrl, detectPlatform } from "@/lib/platform";
import { assertQuality, downloadVideo } from "@/lib/yt-dlp";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type TaskCreatePayload = {
  taskId: string;
  status: string;
};

type TaskSnapshotPayload = {
  taskId: string;
  status: "pending" | "running" | "success" | "failed" | "expired";
  fileName?: string | null;
  fileUrl?: string | null;
  error?: string | null;
  code?: string | null;
};

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const quality = assertQuality(body.quality);
    const safeUrl = assertValidUrl(body.url);
    const isBilibili = detectPlatform(safeUrl).platform === "bilibili";

    if (getBackendBaseUrl()) {
      try {
        const download = await runBackendDownload(safeUrl, quality);
        return NextResponse.json(
          { download },
          {
            headers: {
              "Cache-Control": "no-store"
            }
          }
        );
      } catch (backendError) {
        if (isBilibili) {
          throw backendError;
        }
        console.warn("FastAPI download failed, falling back to Next downloader.", backendError);
      }
    }

    if (isBilibili) {
      throw new Error("B 站下载需要 FastAPI 后端与 BBDown，本地后端不可用时不会回退到 yt-dlp。");
    }

    const download = await downloadVideo(safeUrl, quality);
    return NextResponse.json(
      { download },
      {
        headers: {
          "Cache-Control": "no-store"
        }
      }
    );
  } catch (error) {
    const apiError = toApiError(error, "下载失败，请确认链接可公开访问。");
    return NextResponse.json({ error: apiError.error, code: apiError.code }, { status: apiError.status });
  }
}

async function runBackendDownload(url: string, quality: ReturnType<typeof assertQuality>) {
  const created = await postBackendJson<TaskCreatePayload>("/api/tasks/download", { url, quality }, 15_000);
  const deadline = Date.now() + 10 * 60_000;

  while (Date.now() < deadline) {
    const task = await getBackendJson<TaskSnapshotPayload>(`/api/tasks/${created.taskId}`, 15_000);
    if (task.status === "success" && task.fileName && task.fileUrl) {
      return {
        id: task.taskId,
        fileName: task.fileName,
        fileUrl: absolutizeBackendUrl(task.fileUrl) || task.fileUrl
      };
    }

    if (task.status === "failed" || task.status === "expired") {
      throw new Error(task.error || "后端下载任务失败。");
    }

    await delay(1_000);
  }

  throw new Error("后端下载任务超时，请稍后重试。");
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
