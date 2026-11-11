"""Authentication and Profile management routes."""
from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.db import db

router = APIRouter(prefix="/api/auth", tags=["Authentication & Profiles"])


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100, description="User public display name")


@router.get("/me")
async def get_my_profile(user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, Any]:
    """Retrieve profile and session identity for the current authenticated user."""
    profile = await db.get_profile(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": profile.get("display_name"),
        "created_at": profile.get("created_at"),
        "updated_at": profile.get("updated_at"),
    }


@router.patch("/profile")
async def update_my_profile(
    request: ProfileUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update display name for the current authenticated user."""
    updated = await db.upsert_profile(user, display_name=request.display_name.strip())
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": updated.get("display_name"),
        "updated_at": updated.get("updated_at"),
    }

