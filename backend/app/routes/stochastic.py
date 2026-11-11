from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.security import execute_guarded_calculation
from quant_engine.stochastic import simulate_process

router = APIRouter(prefix="/api/stochastic", tags=["Stochastic Simulator"])


class SimulationRequest(BaseModel):
    process: Literal["brownian", "gbm"]
    spot: float | None = Field(default=None, gt=0, le=1e7, description="Required for GBM; Brownian motion starts at zero")
    drift: float = Field(ge=-5, le=5, description="Annualized drift (or Brownian increment drift)")
    volatility: float = Field(ge=0, le=5, description="Annualized volatility")
    maturity: float = Field(gt=0, le=20, description="Years")
    steps: int = Field(ge=1, le=500, description="Time steps (max 500)")
    paths: int = Field(ge=1, le=40, description="Displayed paths (max 40)")
    seed: int = Field(ge=0, le=2**32-1)
    strike: float | None = Field(default=None, gt=0, le=1e7)
    rate: float = Field(default=0, ge=-1, le=1)
    mc_paths: int = Field(default=10000, ge=100, le=10000, description="Monte Carlo simulation sample paths (max 10,000)")


@router.post("/simulate")
async def simulate(request: SimulationRequest) -> dict[str, object]:
    if request.process == "gbm" and request.spot is None:
        raise HTTPException(status_code=422, detail="spot is required for geometric Brownian motion")
    try:
        return await execute_guarded_calculation(simulate_process, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

