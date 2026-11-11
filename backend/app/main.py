"""HTTP entry point. Calculation details live in quant_engine."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app.routes import bayesian, foundations, intelligence, options, stochastic
from quant_engine.options import black_scholes

app = FastAPI(title="AMQUANT API", version="0.1.0", description="Quantitative finance research API")

cors_origins_env = os.getenv("CORS_ORIGINS", "")
allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
if not allowed_origins:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(foundations.router)
app.include_router(bayesian.router)
app.include_router(stochastic.router)
app.include_router(options.router)
app.include_router(intelligence.router)


class OptionRequest(BaseModel):
    spot: float = Field(gt=0)
    strike: float = Field(gt=0)
    maturity: float = Field(ge=0, description="Years")
    rate: float = Field(description="Continuously compounded annual risk-free rate")
    volatility: float = Field(ge=0, description="Annualized volatility as a decimal")
    kind: str = Field(pattern="^(call|put)$")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "amquant-api", "status": "ok", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "amquant-api"}


@app.post("/api/options/black-scholes")
def price_option(request: OptionRequest) -> dict[str, float | str]:
    price = black_scholes(request.spot, request.strike, request.maturity, request.rate, request.volatility, request.kind)
    return {"price": price, "kind": request.kind, "model": "Black–Scholes–Merton (no dividends)"}
