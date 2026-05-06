from fastapi import APIRouter

from app.services.system_check_service import run_system_check

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/check")
def system_check():
    return run_system_check()

