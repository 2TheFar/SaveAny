export type SaveAnyErrorCode =
  | "INVALID_URL"
  | "UNSUPPORTED_PLATFORM"
  | "UNSUPPORTED_BY_YTDLP"
  | "NEEDS_LOGIN"
  | "NO_FORMAT"
  | "HOTLINK_BLOCKED"
  | "RATE_LIMITED"
  | "RESOLVER_FAILED"
  | "DOWNLOAD_FAILED"
  | "DOWNLOAD_TIMEOUT"
  | "DEPENDENCY_MISSING"
  | "TASK_NOT_FOUND"
  | "FILE_NOT_FOUND"
  | "SUBTITLE_NOT_FOUND"
  | "AI_PROVIDER_NOT_CONFIGURED"
  | "AI_PROVIDER_FAILED"
  | "AI_RESPONSE_INVALID"
  | "AI_CONTEXT_TOO_LONG"
  | "CHAT_CONTEXT_NOT_READY";

export class SaveAnyError extends Error {
  code: SaveAnyErrorCode;
  status: number;

  constructor(code: SaveAnyErrorCode, message: string, status = 400) {
    super(message);
    this.name = "SaveAnyError";
    this.code = code;
    this.status = status;
  }
}

export function toApiError(error: unknown, fallback = "操作失败，请稍后重试。") {
  if (error instanceof SaveAnyError) {
    return {
      error: error.message,
      code: error.code,
      status: error.status
    };
  }

  if (error instanceof Error && error.message) {
    return {
      error: error.message,
      code: "RESOLVER_FAILED" satisfies SaveAnyErrorCode,
      status: 400
    };
  }

  return {
    error: fallback,
    code: "RESOLVER_FAILED" satisfies SaveAnyErrorCode,
    status: 400
  };
}
