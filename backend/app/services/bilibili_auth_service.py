import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlparse
from uuid import uuid4

import requests

from app.core.config import BROWSER_USER_AGENT, SAVEANY_BILIBILI_AUTH_FILE
from app.core.errors import SaveAnyBackendError
from app.models.bilibili import BilibiliLoginCreateResponse, BilibiliLoginStatusResponse, BilibiliSessionResponse

LOGIN_TTL_SECONDS = 180
LOGIN_GENERATE_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate?source=main-fe-header"
LOGIN_POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
SENSITIVE_COOKIE_KEYS = {"SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid", "access_token"}


@dataclass
class BilibiliLoginSession:
    login_id: str
    qrcode_key: str
    login_url: str
    qr_image: str
    expires_at: float
    status: str = "pending"
    message: str = "等待扫码"


LOGIN_SESSIONS: dict[str, BilibiliLoginSession] = {}


def create_bilibili_login() -> BilibiliLoginCreateResponse:
    try:
        response = requests.get(LOGIN_GENERATE_URL, headers=bilibili_headers(), timeout=(8, 20))
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise SaveAnyBackendError("BILIBILI_LOGIN_FAILED", "无法创建 B 站登录二维码，请稍后重试。") from exc
    except ValueError as exc:
        raise SaveAnyBackendError("BILIBILI_LOGIN_FAILED", "B 站登录接口返回内容无法解析。") from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    login_url = data.get("url") if isinstance(data, dict) else None
    qrcode_key = data.get("qrcode_key") if isinstance(data, dict) else None
    if not isinstance(login_url, str) or not isinstance(qrcode_key, str):
        raise SaveAnyBackendError("BILIBILI_LOGIN_FAILED", "B 站登录接口没有返回二维码信息。")

    login_id = str(uuid4())
    expires_at = time.time() + LOGIN_TTL_SECONDS
    session = BilibiliLoginSession(
        login_id=login_id,
        qrcode_key=qrcode_key,
        login_url=login_url,
        qr_image=build_qr_data_url(login_url),
        expires_at=expires_at,
    )
    LOGIN_SESSIONS[login_id] = session
    cleanup_login_sessions()

    return BilibiliLoginCreateResponse(
        loginId=session.login_id,
        qrImage=session.qr_image,
        loginUrl=session.login_url,
        expiresAt=session.expires_at,
        status="pending",
    )


def poll_bilibili_login(login_id: str) -> BilibiliLoginStatusResponse:
    session = LOGIN_SESSIONS.get(login_id)
    if not session:
        raise SaveAnyBackendError("BILIBILI_LOGIN_NOT_FOUND", "登录会话不存在或已过期。", 404)

    if time.time() > session.expires_at:
        session.status = "expired"
        session.message = "二维码已过期，请重新扫码。"
        return login_status_response(session)

    if session.status in {"success", "expired", "failed"}:
        return login_status_response(session)

    try:
        response = requests.get(
            LOGIN_POLL_URL,
            params={"qrcode_key": session.qrcode_key, "source": "main-fe-header"},
            headers=bilibili_headers(),
            timeout=(8, 20),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        session.status = "failed"
        session.message = "登录状态查询失败，请重新扫码。"
        raise SaveAnyBackendError("BILIBILI_LOGIN_FAILED", session.message) from exc
    except ValueError as exc:
        session.status = "failed"
        session.message = "B 站登录状态返回内容无法解析。"
        raise SaveAnyBackendError("BILIBILI_LOGIN_FAILED", session.message) from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    code = data.get("code") if isinstance(data, dict) else None
    if code == 86101:
        session.status = "pending"
        session.message = "等待扫码"
    elif code == 86090:
        session.status = "scanned"
        session.message = "已扫码，请在手机上确认登录。"
    elif code == 86038:
        session.status = "expired"
        session.message = "二维码已过期，请重新扫码。"
    else:
        redirect_url = data.get("url") if isinstance(data, dict) else None
        cookie = cookie_from_bilibili_redirect(redirect_url)
        if not cookie:
            session.status = "failed"
            session.message = "登录成功但未拿到有效 Cookie。"
        else:
            write_bilibili_cookie(cookie)
            session.status = "success"
            session.message = "B 站登录成功。"

    return login_status_response(session)


def get_bilibili_session() -> BilibiliSessionResponse:
    payload = read_bilibili_auth_payload()
    if not payload:
        return BilibiliSessionResponse(isLoggedIn=False)

    created_at = payload.get("createdAt")
    expires_at = payload.get("expiresAt")
    return BilibiliSessionResponse(
        isLoggedIn=bool(payload.get("cookie")),
        createdAt=created_at if isinstance(created_at, (int, float)) else None,
        expiresAt=expires_at if isinstance(expires_at, (int, float)) else None,
    )


def clear_bilibili_session() -> BilibiliSessionResponse:
    SAVEANY_BILIBILI_AUTH_FILE.unlink(missing_ok=True)
    return BilibiliSessionResponse(isLoggedIn=False)


def get_bilibili_cookie() -> str | None:
    payload = read_bilibili_auth_payload()
    cookie = payload.get("cookie") if payload else None
    return cookie if isinstance(cookie, str) and cookie else None


def has_bilibili_session() -> bool:
    return get_bilibili_cookie() is not None


def read_bilibili_auth_payload() -> dict | None:
    try:
        payload = json.loads(SAVEANY_BILIBILI_AUTH_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def write_bilibili_cookie(cookie: str) -> None:
    SAVEANY_BILIBILI_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"cookie": cookie, "createdAt": time.time(), "source": "bilibili_web_qr"}
    SAVEANY_BILIBILI_AUTH_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    chmod_owner_only(SAVEANY_BILIBILI_AUTH_FILE)


def cookie_from_bilibili_redirect(value: object) -> str | None:
    if not isinstance(value, str) or "?" not in value:
        return None

    parsed = urlparse(value)
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    selected = []
    for key, cookie_value in pairs:
        if key in SENSITIVE_COOKIE_KEYS or key.startswith("DedeUserID"):
            selected.append(f"{key}={cookie_value.replace(',', '%2C')}")
    return ";".join(selected) if selected else None


def redact_sensitive_text(value: str) -> str:
    redacted = value
    for key in SENSITIVE_COOKIE_KEYS:
        redacted = re.sub(rf"({re.escape(key)}=)[^;\s&]+", rf"\1<redacted>", redacted, flags=re.I)
    redacted = re.sub(r"(Cookie:\s*)[^\r\n]+", r"\1<redacted>", redacted, flags=re.I)
    redacted = re.sub(r"(-c\s+)[^\r\n]+", r"\1<redacted>", redacted, flags=re.I)
    return redacted


def build_qr_data_url(login_url: str) -> str:
    try:
        import qrcode
    except ImportError as exc:
        raise SaveAnyBackendError("DEPENDENCY_MISSING", "缺少 qrcode 依赖，无法生成 B 站扫码二维码。", 500) from exc

    image = qrcode.make(login_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def bilibili_headers() -> dict[str, str]:
    return {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.bilibili.com/",
    }


def login_status_response(session: BilibiliLoginSession) -> BilibiliLoginStatusResponse:
    return BilibiliLoginStatusResponse(
        loginId=session.login_id,
        status=session.status,
        message=session.message,
        expiresAt=session.expires_at,
        isLoggedIn=has_bilibili_session(),
    )


def cleanup_login_sessions() -> None:
    now = time.time()
    expired = [login_id for login_id, session in LOGIN_SESSIONS.items() if now - session.expires_at > 60]
    for login_id in expired:
        LOGIN_SESSIONS.pop(login_id, None)


def chmod_owner_only(path: Path) -> None:
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass

