from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.security import execute_guarded_calculation
from quant_engine.foundations import crr_binomial, option_profit

router = APIRouter(prefix="/api/foundations", tags=["Financial Foundations"])


class FoundationRequest(BaseModel):
    spot: float = Field(gt=0, le=1e7, description="Asset spot price")
    strike: float = Field(gt=0, le=1e7, description="Option strike price")
    premium: float = Field(ge=0, le=1e7, description="Option premium paid or received")
    maturity: float = Field(ge=0, le=20, description="Maturity horizon in years")
    rate: float = Field(ge=-1, le=1, description="Risk-free rate")
    volatility: float = Field(ge=0, le=5, description="Volatility decimal")
    steps: int = Field(ge=1, le=50, description="Binomial tree steps (max 50 for full hedge schedule)")
    kind: Literal["call", "put"] = "call"
    position: Literal["long", "short"] = "long"
    exercise: Literal["european", "american"] = "european"


@router.post("/analyze")
async def analyze_foundation(request: FoundationRequest) -> dict[str, object]:
    try:
        tree = await execute_guarded_calculation(
            crr_binomial,
            request.spot,
            request.strike,
            request.maturity,
            request.rate,
            request.volatility,
            request.steps,
            request.kind,
            request.exercise,
            include_hedge_tree=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    terminal_spots = [max(request.spot, request.strike) * i / 20 for i in range(41)]
    return {
        "tree": tree,
        "position": request.position,
        "premium": request.premium,
        "payoff_curve": [{"spot": value, "intrinsic": max(value-request.strike, 0) if request.kind == "call" else max(request.strike-value, 0), "profit": option_profit(value, request.strike, request.premium, request.kind, request.position)} for value in terminal_spots],
        "hedge_explanation": "At expiry, there is no future hedge step." if request.maturity == 0 else "With zero volatility the tree has no distinct up/down branches, so a non-degenerate node hedge schedule is not defined." if request.volatility == 0 else "At each nonterminal node, hold delta shares and the reported cash amount in the risk-free asset to replicate the next-step option values. A negative cash value means borrowing. At American early-exercise nodes, the holder can terminate the contract.",
    }
