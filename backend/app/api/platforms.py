from fastapi import APIRouter

from app.models.bilibili import BilibiliLoginCreateResponse, BilibiliLoginStatusResponse, BilibiliSessionResponse
from app.services.bilibili_auth_service import (
    clear_bilibili_session,
    create_bilibili_login,
    get_bilibili_session,
    poll_bilibili_login,
)

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.post("/bilibili/login", response_model=BilibiliLoginCreateResponse)
def create_bilibili_login_session():
    return create_bilibili_login()


@router.get("/bilibili/login/{login_id}", response_model=BilibiliLoginStatusResponse)
def bilibili_login_status(login_id: str):
    return poll_bilibili_login(login_id)


@router.get("/bilibili/session", response_model=BilibiliSessionResponse)
def bilibili_session():
    return get_bilibili_session()


@router.delete("/bilibili/session", response_model=BilibiliSessionResponse)
def delete_bilibili_session():
    return clear_bilibili_session()

