"""Personal Research Run History API."""
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.db import db

router = APIRouter(prefix="/api/research-history", tags=["Research History"])

VALID_MODULES = Literal["foundations", "bayesian", "stochastic", "options", "intelligence"]


class HistoryCreateRequest(BaseModel):
    module_name: VALID_MODULES = Field(description="Module where research was conducted")
    summary: dict[str, Any] = Field(description="Concise summary metrics of calculation results")
    scenario_id: str | None = Field(default=None, description="Optional associated saved scenario UUID")


@router.post("", status_code=status.HTTP_201_CREATED)
async def record_history(
    request: HistoryCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Append a calculation run to the authenticated user's private audit log."""
    import json
    if len(json.dumps(request.summary)) > 16 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Summary payload exceeds 16 KB limit",
        )

    return await db.create_history_entry(
        user=user,
        module_name=request.module_name,
        summary=request.summary,
        scenario_id=request.scenario_id,
    )


@router.get("")
async def list_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List private research history for the authenticated user."""
    return await db.list_history(user=user, limit=limit, offset=offset)


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    history_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """Delete an individual research history entry."""
    await db.delete_history_entry(user=user, history_id=history_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """Clear all research history entries for the authenticated user."""
    await db.clear_history(user=user)

