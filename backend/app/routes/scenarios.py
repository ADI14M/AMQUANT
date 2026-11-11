"""Personal Saved Research Scenarios API."""
from typing import Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.db import db

router = APIRouter(prefix="/api/scenarios", tags=["Saved Scenarios"])

VALID_MODULES = Literal["foundations", "bayesian", "stochastic", "options", "intelligence"]


class ScenarioCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120, description="User-friendly scenario title")
    module_name: VALID_MODULES = Field(description="Target research module")
    scenario_data: dict[str, Any] = Field(description="Validated model parameters and configuration")


class ScenarioUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    scenario_data: dict[str, Any] | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_scenario(
    request: ScenarioCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Save a research scenario to the user's private workspace."""
    # Prevent oversized scenario payloads
    import json
    data_str = json.dumps(request.scenario_data)
    if len(data_str) > 32 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Scenario configuration payload too large (max 32 KB)",
        )

    return await db.create_scenario(
        user=user,
        title=request.title.strip(),
        module_name=request.module_name,
        scenario_data=request.scenario_data,
    )


@router.get("")
async def list_scenarios(
    module_name: VALID_MODULES | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List private saved scenarios for the authenticated user."""
    return await db.list_scenarios(
        user=user,
        module_name=module_name,
        limit=limit,
        offset=offset,
    )


@router.get("/{scenario_id}")
async def get_scenario(
    scenario_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve a single saved scenario, enforcing user ownership."""
    return await db.get_scenario(user=user, scenario_id=scenario_id)


@router.patch("/{scenario_id}")
async def update_scenario(
    scenario_id: str,
    request: ScenarioUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update title or scenario parameters for an owned scenario."""
    if request.scenario_data is not None:
        import json
        if len(json.dumps(request.scenario_data)) > 32 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Scenario configuration payload too large (max 32 KB)",
            )

    clean_title = request.title.strip() if request.title else None
    return await db.update_scenario(
        user=user,
        scenario_id=scenario_id,
        title=clean_title,
        scenario_data=request.scenario_data,
    )


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scenario(
    scenario_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    """Delete an owned scenario from the user's workspace."""
    await db.delete_scenario(user=user, scenario_id=scenario_id)

