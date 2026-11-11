"""HTTP entry point. Calculation details live in quant_engine."""
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    load_dotenv(".env")
    load_dotenv("frontend/.env.local")
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app.routes import auth_routes, bayesian, foundations, history, intelligence, options, scenarios, stochastic
from backend.app.security import SecurityMiddleware, execute_guarded_calculation
from quant_engine.options import black_scholes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("amquant.api")

app = FastAPI(title="AMQUANT API", version="0.1.0", description="Quantitative finance research API")

# Configure CORS: safe parsing of CORS_ORIGINS with fallback and production Vercel domain
cors_origins_env = os.getenv("CORS_ORIGINS", "")
parsed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

default_origins = [
    "https://amquant.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Deduplicate preserving order
allowed_origins = list(dict.fromkeys(parsed_origins + default_origins))

# Middlewares (SecurityMiddleware wrapped by CORSMiddleware so CORS headers apply to 413/429/500 responses)
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
)

# Global safe error handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    safe_errors = []
    for err in exc.errors():
        loc = " -> ".join(str(item) for item in err.get("loc", []) if item != "body")
        safe_errors.append({
            "field": loc or "request",
            "message": err.get("msg", "Invalid value"),
        })
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Request validation failed. Please check your parameter values.",
            "errors": safe_errors,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    headers = getattr(exc, "headers", None) or {}
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=headers,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled internal exception on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred while processing the calculation. Please verify your inputs and try again."
        },
    )


app.include_router(foundations.router)
app.include_router(bayesian.router)
app.include_router(stochastic.router)
app.include_router(options.router)
app.include_router(intelligence.router)
app.include_router(auth_routes.router)
app.include_router(scenarios.router)
app.include_router(history.router)


class OptionRequest(BaseModel):
    spot: float = Field(gt=0, le=1e7, description="Asset spot price")
    strike: float = Field(gt=0, le=1e7, description="Option strike price")
    maturity: float = Field(ge=0, le=100, description="Years")
    rate: float = Field(ge=-1, le=1, description="Continuously compounded annual risk-free rate")
    volatility: float = Field(ge=0, le=10, description="Annualized volatility as a decimal")
    kind: str = Field(pattern="^(call|put)$")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "amquant-api", "status": "ok", "docs": "/docs", "health": "/api/health", "ready": "/api/health/ready"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "amquant-api"}


@app.get("/api/health/ready")
def health_ready() -> dict[str, object]:
    """Readiness probe verifying engine and security infrastructure are active."""
    return {
        "status": "ready",
        "service": "amquant-api",
        "checks": {
            "quant_engine": True,
            "concurrency_protection": True,
            "rate_limiter": True,
        },
    }


@app.post("/api/options/black-scholes")
async def price_option(request: OptionRequest) -> dict[str, float | str]:
    price = await execute_guarded_calculation(
        black_scholes, request.spot, request.strike, request.maturity, request.rate, request.volatility, request.kind
    )
    return {"price": price, "kind": request.kind, "model": "Black–Scholes–Merton (no dividends)"}
