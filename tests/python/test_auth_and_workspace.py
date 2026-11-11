"""Automated tests for Supabase JWT verification, RLS enforcement, and research workspaces."""
import time
import uuid
import jwt
import pytest
from fastapi.testclient import TestClient

from backend.app.auth import verifier
from backend.app.db import db
from backend.app.main import app

client = TestClient(app)

TEST_SECRET = "super-secret-supabase-test-key-for-amquant-2026-signing"


@pytest.fixture(autouse=True)
def setup_auth_environment(monkeypatch):
    """Configure JWT verifier with test secret and clear in-memory test DB."""
    monkeypatch.setattr(verifier, "jwt_secret", TEST_SECRET)
    monkeypatch.setattr(verifier, "expected_issuer", "https://test-project.supabase.co/auth/v1")
    monkeypatch.setattr(db, "_test_mode", True)
    db._memory_scenarios.clear()
    db._memory_history.clear()
    db._memory_profiles.clear()


def create_test_jwt(user_id: uuid.UUID, email: str = "quant@amquant.io", expires_in: int = 3600, secret: str = TEST_SECRET) -> str:
    """Generate a valid signed Supabase JWT for testing."""
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + expires_in,
        "iss": "https://test-project.supabase.co/auth/v1",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_public_guest_access_unaffected():
    """Verify guests can access all five research modules without providing an Authorization header."""
    res_foundations = client.post("/api/foundations/analyze", json={
        "spot": 100, "strike": 100, "premium": 10, "maturity": 1, "rate": 0.05, "volatility": 0.2, "steps": 10
    })
    res_bayesian = client.post("/api/bayesian/update", json={
        "alpha": 2, "beta": 2, "observations": [1, 0, 1]
    })
    res_stochastic = client.post("/api/stochastic/simulate", json={
        "process": "gbm", "spot": 100, "drift": 0.05, "volatility": 0.2, "maturity": 1, "steps": 10, "paths": 2, "seed": 42
    })
    res_options = client.post("/api/options/analyze", json={
        "spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2, "kind": "call", "steps": 20
    })
    res_intelligence = client.post("/api/intelligence/analyze", json={
        "asset": "NVDA", "spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2, "drift": 0.08
    })

    assert res_foundations.status_code == 200
    assert res_bayesian.status_code == 200
    assert res_stochastic.status_code == 200
    assert res_options.status_code == 200
    assert res_intelligence.status_code == 200


def test_missing_and_malformed_token_rejection():
    """Verify private endpoints reject requests without valid Bearer tokens with 401."""
    # 1. Missing header
    res_missing = client.get("/api/auth/me")
    assert res_missing.status_code == 401
    assert "Bearer" in res_missing.headers.get("WWW-Authenticate", "")

    # 2. Non-Bearer scheme
    res_basic = client.get("/api/auth/me", headers={"Authorization": "Basic 12345"})
    assert res_basic.status_code == 401

    # 3. Invalid signature
    user_id = uuid.uuid4()
    tampered_token = create_test_jwt(user_id, secret="wrong-signing-secret-key-32-chars-long!")
    res_tampered = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert res_tampered.status_code == 401

    # 4. Expired token
    expired_token = create_test_jwt(user_id, expires_in=-60)
    res_expired = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_expired.status_code == 401


def test_profile_retrieval_and_update():
    """Test authenticated profile retrieval and display name updates."""
    user_id = uuid.uuid4()
    token = create_test_jwt(user_id, email="alice@hedgefund.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch initial profile
    res_me = client.get("/api/auth/me", headers=headers)
    assert res_me.status_code == 200
    data = res_me.json()
    assert data["id"] == str(user_id)
    assert data["email"] == "alice@hedgefund.com"
    assert data["display_name"] == "alice"

    # Update profile display name
    res_update = client.patch("/api/auth/profile", headers=headers, json={"display_name": "Alice Quantitative"})
    assert res_update.status_code == 200
    assert res_update.json()["display_name"] == "Alice Quantitative"

    # Fetch profile again to verify persistence
    res_after = client.get("/api/auth/me", headers=headers)
    assert res_after.json()["display_name"] == "Alice Quantitative"


def test_saved_scenario_crud_lifecycle_and_validation():
    """Test full CRUD lifecycle of saved research scenarios with boundary checks."""
    user_id = uuid.uuid4()
    token = create_test_jwt(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    scenario_payload = {
        "title": "NVDA Volatility Smile Calibration",
        "module_name": "options",
        "scenario_data": {
            "spot": 135.5,
            "strike": 140.0,
            "maturity": 0.5,
            "volatility": 0.35,
            "rate": 0.045,
            "kind": "call",
        },
    }

    # 1. Create Scenario
    res_create = client.post("/api/scenarios", headers=headers, json=scenario_payload)
    assert res_create.status_code == 201
    created = res_create.json()
    assert created["title"] == "NVDA Volatility Smile Calibration"
    assert created["module_name"] == "options"
    assert created["user_id"] == str(user_id)
    scenario_id = created["id"]

    # 2. List Scenarios
    res_list = client.get("/api/scenarios", headers=headers)
    assert res_list.status_code == 200
    items = res_list.json()
    assert len(items) == 1
    assert items[0]["id"] == scenario_id

    # 3. Get Single Scenario
    res_get = client.get(f"/api/scenarios/{scenario_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["scenario_data"]["spot"] == 135.5

    # 4. Update Scenario Title
    res_patch = client.patch(f"/api/scenarios/{scenario_id}", headers=headers, json={
        "title": "NVDA Q3 Calibrated Surface"
    })
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "NVDA Q3 Calibrated Surface"

    # 5. Delete Scenario
    res_del = client.delete(f"/api/scenarios/{scenario_id}", headers=headers)
    assert res_del.status_code == 204

    # 6. Verify Deletion
    res_after = client.get(f"/api/scenarios/{scenario_id}", headers=headers)
    assert res_after.status_code == 404

    # Validation: invalid module name
    res_inv_mod = client.post("/api/scenarios", headers=headers, json={
        "title": "Invalid Module Test",
        "module_name": "crypto_pump",
        "scenario_data": {"val": 1},
    })
    assert res_inv_mod.status_code == 422

    # Validation: empty title
    res_inv_title = client.post("/api/scenarios", headers=headers, json={
        "title": "",
        "module_name": "options",
        "scenario_data": {"val": 1},
    })
    assert res_inv_title.status_code == 422


def test_cross_user_isolation_and_ownership_enforcement():
    """Verify that User B cannot access, read, update, or delete User A's scenarios or history."""
    user_a = uuid.uuid4()
    token_a = create_test_jwt(user_a, email="user_a@amquant.io")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    user_b = uuid.uuid4()
    token_b = create_test_jwt(user_b, email="user_b@amquant.io")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A creates a scenario
    res_a = client.post("/api/scenarios", headers=headers_a, json={
        "title": "User A Proprietary Strategy",
        "module_name": "intelligence",
        "scenario_data": {"secret_alpha": 42},
    })
    assert res_a.status_code == 201
    scenario_id_a = res_a.json()["id"]

    # User B lists scenarios: must NOT see User A's scenario
    res_b_list = client.get("/api/scenarios", headers=headers_b)
    assert res_b_list.status_code == 200
    assert len(res_b_list.json()) == 0

    # User B attempts to read User A's scenario directly: must return 404
    res_b_read = client.get(f"/api/scenarios/{scenario_id_a}", headers=headers_b)
    assert res_b_read.status_code == 404

    # User B attempts to patch User A's scenario: must return 404
    res_b_patch = client.patch(f"/api/scenarios/{scenario_id_a}", headers=headers_b, json={"title": "Hacked"})
    assert res_b_patch.status_code == 404

    # User B attempts to delete User A's scenario: must return 404
    res_b_del = client.delete(f"/api/scenarios/{scenario_id_a}", headers=headers_b)
    assert res_b_del.status_code == 404

    # User A's scenario must still exist unchanged
    res_a_check = client.get(f"/api/scenarios/{scenario_id_a}", headers=headers_a)
    assert res_a_check.status_code == 200
    assert res_a_check.json()["title"] == "User A Proprietary Strategy"


def test_research_history_lifecycle():
    """Test recording, listing, deleting, and clearing personal calculation run history."""
    user_id = uuid.uuid4()
    token = create_test_jwt(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Record calculation run
    entry_payload = {
        "module_name": "options",
        "summary": {
            "bsm_price": 10.4506,
            "delta": 0.6368,
            "spot": 100.0,
            "strike": 100.0,
        },
    }
    res_rec = client.post("/api/research-history", headers=headers, json=entry_payload)
    assert res_rec.status_code == 201
    entry_id = res_rec.json()["id"]

    # 2. List history
    res_list = client.get("/api/research-history", headers=headers)
    assert res_list.status_code == 200
    entries = res_list.json()
    assert len(entries) == 1
    assert entries[0]["id"] == entry_id
    assert entries[0]["summary"]["bsm_price"] == 10.4506

    # 3. Delete single entry
    res_del_entry = client.delete(f"/api/research-history/{entry_id}", headers=headers)
    assert res_del_entry.status_code == 204

    # 4. Verify empty list
    res_list2 = client.get("/api/research-history", headers=headers)
    assert len(res_list2.json()) == 0

    # 5. Record two entries and test clear_history
    client.post("/api/research-history", headers=headers, json=entry_payload)
    client.post("/api/research-history", headers=headers, json=entry_payload)
    assert len(client.get("/api/research-history", headers=headers).json()) == 2

    res_clear = client.delete("/api/research-history", headers=headers)
    assert res_clear.status_code == 204
    assert len(client.get("/api/research-history", headers=headers).json()) == 0
