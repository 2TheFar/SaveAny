from fastapi import HTTPException


class SaveAnyBackendError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def as_http_error(error: Exception) -> HTTPException:
    if isinstance(error, SaveAnyBackendError):
        return HTTPException(
            status_code=error.status_code,
            detail={"error": error.message, "code": error.code},
        )

    return HTTPException(
        status_code=400,
        detail={"error": str(error) or "操作失败，请稍后重试。", "code": "RESOLVER_FAILED"},
    )
