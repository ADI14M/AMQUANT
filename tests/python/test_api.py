import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from backend.app.security import rate_limiter
    rate_limiter.records.clear()
    yield
    rate_limiter.records.clear()


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    root_response = client.get("/")
    assert root_response.status_code == 200
    assert root_response.json()["service"] == "amquant-api"


def test_existing_black_scholes_endpoint():
    response = client.post("/api/options/black-scholes", json={"spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2, "kind": "call"})
    assert response.status_code == 200
    assert response.json()["price"] == pytest.approx(10.4506, abs=0.001)


def test_all_module_routes_and_validation():
    foundation = client.post("/api/foundations/analyze", json={"spot": 100, "strike": 100, "premium": 10, "maturity": 1, "rate": 0.05, "volatility": 0.2, "steps": 50, "kind": "call", "position": "long", "exercise": "european"})
    bayesian = client.post("/api/bayesian/update", json={"alpha": 2, "beta": 2, "observations": [1, 0, 1]})
    stochastic = client.post("/api/stochastic/simulate", json={"process": "gbm", "spot": 100, "drift": 0.05, "volatility": 0.2, "maturity": 1, "steps": 20, "paths": 3, "seed": 7, "strike": 100, "rate": 0.05, "mc_paths": 1000})
    options = client.post("/api/options/analyze", json={"spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2, "kind": "call", "steps": 100})
    brownian = client.post("/api/stochastic/simulate", json={"process": "brownian", "drift": 0, "volatility": 0.2, "maturity": 1, "steps": 12, "paths": 3, "seed": 7})
    assert foundation.status_code == bayesian.status_code == stochastic.status_code == options.status_code == brownian.status_code == 200
    assert len(foundation.json()["tree"]["hedge_schedule"]) == 50 * 51 // 2
    assert options.json()["black_scholes"]["price"] == pytest.approx(10.4506, abs=0.001)
    assert client.post("/api/bayesian/update", json={"alpha": 1, "beta": 1, "observations": [2]}).status_code == 422
    assert client.post("/api/stochastic/simulate", json={"process": "gbm", "spot": 100, "drift": 0.05, "volatility": 0.2, "maturity": 1, "steps": 300, "paths": 3, "seed": 7}).status_code == 422


def test_research_intelligence_route():
    payload = {
        "asset": "SPY",
        "spot": 100.0,
        "strike": 100.0,
        "maturity": 1.0,
        "rate": 0.05,
        "volatility": 0.20,
        "drift": 0.08,
        "dividend_yield": 0.0,
        "kind": "call",
        "prior_alpha": 2.0,
        "prior_beta": 2.0,
        "observations": [1, 1, 0, 1, 1, 0, 1],
        "sim_steps": 50,
        "sim_paths": 10,
        "sim_seed": 42,
        "mc_paths": 5000,
        "tree_steps": 50,
    }
    response = client.post("/api/intelligence/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["setup"]["asset"] == "SPY"
    assert data["bayesian"]["posterior"]["alpha"] == 7.0
    assert data["bayesian"]["posterior"]["beta"] == 4.0
    assert "shift_summary" in data["bayesian"]
    assert len(data["stochastic"]["physical"]["paths"]) == 51
    assert len(data["stochastic"]["risk_neutral"]["paths"]) == 51
    assert data["valuation"]["black_scholes"]["price"] == pytest.approx(10.4506, abs=0.001)
    assert data["valuation"]["put_call_parity"]["holds"] is True
    assert len(data["valuation"]["models_comparison"]) >= 3
    assert "disclaimer" in data["conclusion"]
    assert "executive_summary" in data["conclusion"]

    # Test input validation failure
    invalid = client.post("/api/intelligence/analyze", json={**payload, "observations": [1, 2]})
    assert invalid.status_code == 422


def test_readiness_probe():
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["quant_engine"] is True
    assert data["checks"]["concurrency_protection"] is True
    assert data["checks"]["rate_limiter"] is True


def test_client_ip_render_proxy_detection():
    from starlette.requests import Request
    from backend.app.security import get_client_ip

    # 1. Direct connection from public IP (X-Forwarded-For must be ignored to prevent spoofing)
    scope_public = {
        "type": "http",
        "client": ("93.184.216.34", 54321),
        "headers": [(b"x-forwarded-for", b"203.0.113.99")],
    }
    req_pub = Request(scope_public)
    assert get_client_ip(req_pub) == "93.184.216.34"

    # 2. Connection from internal Render reverse proxy (10.x.x.x) with X-Forwarded-For
    scope_proxy = {
        "type": "http",
        "client": ("10.0.12.34", 12345),
        "headers": [(b"x-forwarded-for", b"203.0.113.50, 10.0.12.34")],
    }
    req_prox = Request(scope_proxy)
    assert get_client_ip(req_prox) == "203.0.113.50"

    # 3. Connection from localhost loopback with multi-hop chain
    scope_local = {
        "type": "http",
        "client": ("127.0.0.1", 8000),
        "headers": [(b"x-forwarded-for", b"192.0.2.1, 10.0.0.1, 127.0.0.1")],
    }
    req_loc = Request(scope_local)
    assert get_client_ip(req_loc) == "192.0.2.1"


def test_sliding_window_rate_limiter():
    from backend.app.security import SlidingWindowRateLimiter
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
    test_ip = "192.0.2.100"

    # First 3 requests allowed
    assert limiter.is_allowed(test_ip)[0] is True
    assert limiter.is_allowed(test_ip)[0] is True
    assert limiter.is_allowed(test_ip)[0] is True

    # 4th request within window rejected
    allowed, retry_after = limiter.is_allowed(test_ip)
    assert allowed is False
    assert retry_after > 0

    # Different IP is not affected
    assert limiter.is_allowed("192.0.2.101")[0] is True


def test_rate_limiting_middleware_429():
    # Health checks are exempt and should always return 200
    for _ in range(35):
        assert client.get("/api/health").status_code == 200

    # Non-exempt calculation endpoints are rate limited to 30 requests per minute
    for _ in range(30):
        res = client.post("/api/bayesian/update", json={"alpha": 2, "beta": 2, "observations": [1]})
        assert res.status_code == 200

    # 31st request from same IP within the window must return 429
    res_31 = client.post("/api/bayesian/update", json={"alpha": 2, "beta": 2, "observations": [1]})
    assert res_31.status_code == 429
    assert "Retry-After" in res_31.headers
    assert "Rate limit exceeded" in res_31.json()["detail"]


def test_payload_size_limit_413():
    # Attempting to post a body with Content-Length > 64KB (65536 bytes)
    oversized_length = 70 * 1024
    res = client.post(
        "/api/bayesian/update",
        headers={"Content-Length": str(oversized_length), "Content-Type": "application/json"},
        content=b"{}",
    )
    assert res.status_code == 413
    assert "Request body too large" in res.json()["detail"]


def test_resource_upper_bounds_and_validations():
    # 1. Monte Carlo paths upper bound (> 10,000)
    mc_over = client.post("/api/stochastic/simulate", json={
        "process": "gbm", "spot": 100, "drift": 0.05, "volatility": 0.2, "maturity": 1,
        "steps": 20, "paths": 3, "seed": 7, "mc_paths": 10001
    })
    assert mc_over.status_code == 422
    assert "errors" in mc_over.json()

    # 2. Simulation steps upper bound (> 500)
    steps_over = client.post("/api/stochastic/simulate", json={
        "process": "gbm", "spot": 100, "drift": 0.05, "volatility": 0.2, "maturity": 1,
        "steps": 501, "paths": 3, "seed": 7, "mc_paths": 1000
    })
    assert steps_over.status_code == 422

    # 3. Binomial tree steps upper bound (> 500 in options, > 50 in foundations)
    tree_over_opt = client.post("/api/options/analyze", json={
        "spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2,
        "kind": "call", "steps": 501
    })
    assert tree_over_opt.status_code == 422

    tree_over_fnd = client.post("/api/foundations/analyze", json={
        "spot": 100, "strike": 100, "premium": 10, "maturity": 1, "rate": 0.05, "volatility": 0.2,
        "steps": 51, "kind": "call", "position": "long", "exercise": "european"
    })
    assert tree_over_fnd.status_code == 422

    # 4. Bayesian observations upper bound (> 5,000)
    bayesian_over = client.post("/api/bayesian/update", json={
        "alpha": 2, "beta": 2, "observations": [1] * 5001
    })
    assert bayesian_over.status_code == 422

    # 5. Spot price upper bound (> 1e7)
    spot_over = client.post("/api/options/analyze", json={
        "spot": 2e7, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2,
        "kind": "call", "steps": 50
    })
    assert spot_over.status_code == 422


def test_sanitized_error_responses_no_traceback():
    # 422 validation response should have clean field and message without python class or memory addresses
    res_422 = client.post("/api/bayesian/update", json={"alpha": -5, "beta": 2, "observations": [1]})
    assert res_422.status_code == 422
    body = res_422.json()
    assert "detail" in body
    assert "errors" in body
    assert any("alpha" in err.get("field", "") for err in body["errors"])

    # Health endpoints are exempt from rate limiting and return 200
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/health/ready").status_code == 200


def test_unhandled_exception_masks_internal_traceback(monkeypatch):
    import backend.app.main

    # Simulate an unexpected internal engine crash
    def mock_broken_calc(*args, **kwargs):
        raise RuntimeError("Internal secret calculation memory corruption at /opt/render/secret/engine.c:99")

    monkeypatch.setattr(backend.app.main, "black_scholes", mock_broken_calc)

    res = client.post("/api/options/black-scholes", json={
        "spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2, "kind": "call"
    })
    assert res.status_code == 500
    data = res.json()
    assert "secret" not in data["detail"]
    assert "engine.c" not in data["detail"]
    assert "traceback" not in data
    assert "An internal error occurred" in data["detail"]


@pytest.mark.anyio
async def test_concurrency_guard_503_under_saturation():
    import asyncio
    from backend.app.security import calculation_semaphore, execute_guarded_calculation
    from fastapi import HTTPException

    # Temporarily acquire all permits of the semaphore
    permits = []
    for _ in range(5):
        await calculation_semaphore.acquire()
        permits.append(1)

    try:
        # A 6th guarded calculation should timeout and raise HTTPException(503)
        with pytest.raises(HTTPException) as exc_info:
            await execute_guarded_calculation(lambda: 42)
        assert exc_info.value.status_code == 503
        assert exc_info.value.headers.get("Retry-After") == "3"
        assert "peak capacity" in exc_info.value.detail
    finally:
        for _ in permits:
            calculation_semaphore.release()
