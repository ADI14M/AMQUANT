import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


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
