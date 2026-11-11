from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.security import execute_guarded_calculation
from quant_engine.bayesian import beta_bernoulli_update

router = APIRouter(prefix="/api/bayesian", tags=["Bayesian Engine"])


class BayesianRequest(BaseModel):
    alpha: float = Field(gt=0, le=100000, description="Beta prior alpha parameter (successes)")
    beta: float = Field(gt=0, le=100000, description="Beta prior beta parameter (failures)")
    observations: list[int] = Field(max_length=5000, description="Observed binary outcomes (1 or 0), max 5,000")


@router.post("/update")
async def update_belief(request: BayesianRequest) -> dict[str, object]:
    if any(value not in (0, 1) for value in request.observations):
        raise HTTPException(status_code=422, detail="observations must contain only 0 or 1")
    return await execute_guarded_calculation(beta_bernoulli_update, request.alpha, request.beta, request.observations)

