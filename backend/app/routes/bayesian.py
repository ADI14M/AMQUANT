from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from quant_engine.bayesian import beta_bernoulli_update

router = APIRouter(prefix="/api/bayesian", tags=["Bayesian Engine"])


class BayesianRequest(BaseModel):
    alpha: float = Field(gt=0, le=100000)
    beta: float = Field(gt=0, le=100000)
    observations: list[int] = Field(max_length=500)


@router.post("/update")
def update_belief(request: BayesianRequest) -> dict[str, object]:
    if any(value not in (0, 1) for value in request.observations):
        raise HTTPException(status_code=422, detail="observations must contain only 0 or 1")
    return beta_bernoulli_update(request.alpha, request.beta, request.observations)
