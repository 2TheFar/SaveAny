from typing import Literal

from pydantic import BaseModel


BilibiliLoginStatusValue = Literal["pending", "scanned", "success", "expired", "failed"]


class BilibiliLoginCreateResponse(BaseModel):
    loginId: str
    qrImage: str
    loginUrl: str
    expiresAt: float
    status: BilibiliLoginStatusValue


class BilibiliLoginStatusResponse(BaseModel):
    loginId: str
    status: BilibiliLoginStatusValue
    message: str
    expiresAt: float
    isLoggedIn: bool = False


class BilibiliSessionResponse(BaseModel):
    isLoggedIn: bool
    createdAt: float | None = None
    expiresAt: float | None = None
    source: str = "local"

