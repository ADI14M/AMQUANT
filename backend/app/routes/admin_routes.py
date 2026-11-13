"""Owner-Only Administration Routes for AMQUANT Security & System Configuration."""
import os
import shutil
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.access_security import (
    OWNER_EMAIL,
    access_rate_limiter,
    is_owner_email,
    password_manager,
    security_logger,
    session_manager,
)
from backend.app.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/api/admin", tags=["Owner Administration"])


def require_owner(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """Dependency verifying that the authenticated user possesses Owner privileges."""
    if not is_owner_email(user.email):
        security_logger.log(
            "ADMIN_ACCESS_FORBIDDEN",
            "auth_user",
            f"Non-owner user {user.email} attempted admin access",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative access is restricted to the platform owner (Adi).",
        )
    return user


class RotatePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128, description="New shared private access password")


@router.get("/security-logs")
async def get_security_logs(
    limit: int = Query(default=100, ge=1, le=500),
    owner: AuthenticatedUser = Depends(require_owner),
) -> dict[str, Any]:
    """Retrieve recent security and access events. Owner only."""
    events = security_logger.get_recent_events(limit=limit)
    security_logger.log("ADMIN_ACTION", "admin", f"Owner {owner.email} inspected security logs")
    return {
        "count": len(events),
        "events": events,
    }


@router.post("/rotate-password")
async def rotate_shared_password(
    req: RotatePasswordRequest,
    owner: AuthenticatedUser = Depends(require_owner),
) -> dict[str, Any]:
    """Rotate the shared access password and invalidate all existing beta sessions. Owner only."""
    try:
        new_hash = password_manager.rotate_password(req.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    session_manager.revoke_all_sessions()
    security_logger.log(
        "ACCESS_PASSWORD_ROTATED",
        "admin",
        f"Owner {owner.email} rotated access password; all prior sessions revoked",
    )
    return {
        "ok": True,
        "detail": "Shared access password rotated successfully. All active user sessions revoked.",
        "hash_preview": password_manager.current_hash_preview,
    }


@router.post("/revoke-all-sessions")
async def revoke_all_sessions(
    owner: AuthenticatedUser = Depends(require_owner),
) -> dict[str, Any]:
    """Revoke all issued access sessions globally. Owner only."""
    session_manager.revoke_all_sessions()
    security_logger.log(
        "ACCESS_ALL_SESSIONS_REVOKED",
        "admin",
        f"Owner {owner.email} revoked all active platform sessions",
    )
    return {
        "ok": True,
        "detail": "All active access sessions have been globally revoked.",
    }


@router.get("/system-status")
async def get_system_status(
    owner: AuthenticatedUser = Depends(require_owner),
) -> dict[str, Any]:
    """Inspect system health, rate limiter status, and disk storage without exposing credentials."""
    data_dir = os.getenv("AMQUANT_DATA_DIR", "./quant_engine/india/data")
    disk_usage = {}
    if os.path.exists(data_dir):
        total, used, free = shutil.disk_usage(data_dir)
        disk_usage = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
        }

    return {
        "owner_email": OWNER_EMAIL,
        "active_password_configured": bool(password_manager._active_hash),
        "password_hash_preview": password_manager.current_hash_preview,
        "rate_limiter_status": access_rate_limiter.get_status(),
        "storage_directory": data_dir,
        "disk_usage": disk_usage,
    }
