from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from quant_engine.foundations import crr_binomial
from quant_engine.options import black_scholes_greeks, option_sensitivities

router = APIRouter(prefix="/api/options", tags=["Options Lab"])


class OptionAnalysisRequest(BaseModel):
    spot: float = Field(gt=0)
    strike: float = Field(gt=0)
    maturity: float = Field(ge=0, le=20)
    rate: float = Field(ge=-1, le=1)
    volatility: float = Field(gt=0, le=5, description="Positive for a defined smooth Black–Scholes Greek surface")
    dividend_yield: float = Field(default=0, ge=-1, le=1)
    kind: Literal["call", "put"] = "call"
    steps: int = Field(default=100, ge=1, le=500)


@router.post("/analyze")
def analyze_option(request: OptionAnalysisRequest) -> dict[str, object]:
    try:
        greeks = black_scholes_greeks(request.spot, request.strike, request.maturity, request.rate, request.volatility, request.kind, request.dividend_yield)
        tree_european = crr_binomial(request.spot, request.strike, request.maturity, request.rate, request.volatility, request.steps, request.kind, "european", request.dividend_yield)
        tree_american = crr_binomial(request.spot, request.strike, request.maturity, request.rate, request.volatility, request.steps, request.kind, "american", request.dividend_yield)
        sensitivity = option_sensitivities(request.spot, request.strike, request.maturity, request.rate, request.volatility, request.kind, request.dividend_yield)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "kind": request.kind,
        "black_scholes": greeks,
        "binomial_european": tree_european,
        "binomial_american": tree_american,
        "model_difference": tree_european["price"] - greeks["price"],
        "sensitivities": sensitivity,
        "assumptions": {"dividend_yield": request.dividend_yield, "rate_compounding": "continuous", "exercise": "European for Black–Scholes; American tree allows early exercise", "greek_units": "Vega and rho are per 1.00 change; theta per year."},
    }
