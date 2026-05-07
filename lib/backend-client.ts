import { SaveAnyError, type SaveAnyErrorCode } from "@/lib/errors";

type BackendErrorPayload = {
  error?: string;
  code?: SaveAnyErrorCode;
  detail?: {
    error?: string;
    code?: SaveAnyErrorCode;
  };
};

export function getBackendBaseUrl() {
  const configured = process.env.SAVEANY_BACKEND_URL?.replace(/\/+$/, "");
  if (configured) {
    return configured;
  }

  if (process.env.NODE_ENV !== "production") {
    return "http://127.0.0.1:8000";
  }

  return null;
}

export function absolutizeBackendUrl(value: string | null | undefined) {
  if (!value || /^https?:\/\//i.test(value)) {
    return value;
  }

  const baseUrl = getBackendBaseUrl();
  if (!baseUrl || !value.startsWith("/")) {
    return value;
  }

  return `${baseUrl}${value}`;
}

export async function postBackendJson<T>(path: string, body: unknown, timeoutMs = 45_000): Promise<T> {
  const response = await fetchBackend(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs)
  });

  return response.json() as Promise<T>;
}

export async function getBackendJson<T>(path: string, timeoutMs = 15_000): Promise<T> {
  const response = await fetchBackend(path, {
    method: "GET",
    signal: AbortSignal.timeout(timeoutMs)
  });

  return response.json() as Promise<T>;
}

async function fetchBackend(path: string, init: RequestInit) {
  const baseUrl = getBackendBaseUrl();
  if (!baseUrl) {
    throw new SaveAnyError("DEPENDENCY_MISSING", "未配置 FastAPI 后端地址。", 500);
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    cache: "no-store"
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as BackendErrorPayload;
    const detail = payload.detail || {};
    throw new SaveAnyError(
      detail.code || payload.code || "RESOLVER_FAILED",
      detail.error || payload.error || `后端请求失败：${response.status}`,
      response.status
    );
  }

  return response;
}
