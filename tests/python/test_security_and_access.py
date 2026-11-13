"""Comprehensive test suite for AMQUANT Private Access Security, Password Gate, and Admin Controls."""
import time
import uuid
import jwt
import pytest
from fastapi.testclient import TestClient

from backend.app.access_security import (
    AMQUANT_SESSION_SECRET,
    OWNER_EMAIL,
    access_rate_limiter,
    password_manager,
    security_logger,
    session_manager,
)
from backend.app.auth import SUPABASE_JWT_SECRET
from backend.app.main import app

# Unauthenticated client (skips default test token injection)
client = TestClient(app)
client._skip_test_auth = True


@pytest.fixture(autouse=True)
def reset_security_state():
    """Reset rate limiters and session revocation state between tests."""
    access_rate_limiter._failures.clear()
    access_rate_limiter._lockouts.clear()
    session_manager.revoked_jtis.clear()
    session_manager.revocation_epoch = 0.0
    yield
    access_rate_limiter._failures.clear()
    access_rate_limiter._lockouts.clear()
    session_manager.revoked_jtis.clear()
    session_manager.revocation_epoch = 0.0


def test_public_health_and_root_endpoints_accessible_without_token():
    """Public infrastructure probes must remain accessible without authentication."""
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok", "service": "amquant-api"}

    res_ready = client.get("/api/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"

    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["service"] == "amquant-api"


def test_protected_endpoints_reject_unauthenticated_requests():
    """All calculation and market data routes must return 401 when accessed without token."""
    # Global options calculation
    res1 = client.post("/api/options/black-scholes", json={"spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2, "kind": "call"})
    assert res1.status_code == 401
    assert "Private platform access required" in res1.json()["detail"]

    # Indian market overview
    res2 = client.get("/api/india/market-overview")
    assert res2.status_code == 401

    # Foundations calculation
    res3 = client.post("/api/foundations/analyze", json={"spot": 100, "strike": 100, "premium": 10, "maturity": 1, "rate": 0.05, "volatility": 0.2, "steps": 10, "kind": "call", "position": "long", "exercise": "european"})
    assert res3.status_code == 401


def test_invalid_and_expired_tokens_are_rejected():
    """Forged or expired tokens must be rejected with 401."""
    # Malformed token
    res = client.get("/api/india/market-overview", headers={"X-Amquant-Access-Token": "invalid_forged_token"})
    assert res.status_code == 401

    # Expired session token
    expired_payload = {
        "sub": "beta_access",
        "role": "platform_access",
        "jti": str(uuid.uuid4()),
        "iat": int(time.time()) - 3600,
        "exp": int(time.time()) - 10,  # Expired 10 seconds ago
        "client_ip": "127.0.0.1",
    }
    expired_token = jwt.encode(expired_payload, AMQUANT_SESSION_SECRET, algorithm="HS256")
    res_exp = client.get("/api/india/market-overview", headers={"X-Amquant-Access-Token": expired_token})
    assert res_exp.status_code == 401


def test_password_verification_and_session_issuance():
    """Submitting the correct access password unlocks the platform and returns a signed token."""
    # 1. Invalid password
    res_fail = client.post("/api/auth/access/verify", json={"password": "wrong_guess_123"})
    assert res_fail.status_code == 401
    assert "Incorrect access password" in res_fail.json()["detail"]

    # 2. Correct password (defaults to 'amquant2026' in dev unless configured)
    res_ok = client.post("/api/auth/access/verify", json={"password": "amquant2026"})
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["ok"] is True
    assert "session_token" in data
    assert "expires_at" in data

    token = data["session_token"]
    # Check status endpoint with issued token
    res_status = client.get("/api/auth/access/status", headers={"X-Amquant-Access-Token": token})
    assert res_status.status_code == 200
    assert res_status.json()["authenticated"] is True

    # Use issued token to access protected calculation
    res_calc = client.post(
        "/api/options/black-scholes",
        json={"spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2, "kind": "call"},
        headers={"X-Amquant-Access-Token": token},
    )
    assert res_calc.status_code == 200
    assert res_calc.json()["price"] > 0


def test_rate_limiting_and_lockout_on_failed_unlock_attempts():
    """5 consecutive failed attempts must trigger a 429 lockout."""
    for attempt in range(4):
        res = client.post("/api/auth/access/verify", json={"password": f"bad_guess_{attempt}"})
        assert res.status_code == 401

    # 5th attempt triggers lockout
    res_lockout = client.post("/api/auth/access/verify", json={"password": "bad_guess_5"})
    assert res_lockout.status_code == 429
    assert "Too many failed unlock attempts" in res_lockout.json()["detail"]
    assert "Retry-After" in res_lockout.headers

    # Even with the correct password, locked IP is denied until cooldown expires
    res_blocked = client.post("/api/auth/access/verify", json={"password": "amquant2026"})
    assert res_blocked.status_code == 429


def test_session_revocation():
    """Revoking an active session invalidates access."""
    # Obtain token
    res_ok = client.post("/api/auth/access/verify", json={"password": "amquant2026"})
    token = res_ok.json()["session_token"]

    # Revoke
    res_revoke = client.post("/api/auth/access/revoke", headers={"X-Amquant-Access-Token": token})
    assert res_revoke.status_code == 200
    assert res_revoke.json()["ok"] is True

    # Subsequent check shows unauthenticated
    res_status = client.get("/api/auth/access/status", headers={"X-Amquant-Access-Token": token})
    assert res_status.json()["authenticated"] is False

    # Protected endpoint rejects revoked token
    res_calc = client.post(
        "/api/options/black-scholes",
        json={"spot": 100, "strike": 100, "maturity": 1, "rate": 0.05, "volatility": 0.2, "kind": "call"},
        headers={"X-Amquant-Access-Token": token},
    )
    assert res_calc.status_code == 401


def test_owner_only_administration():
    """Administrative endpoints must be accessible exclusively to the owner (Adi)."""
    # 1. Unauthenticated -> 401
    res_unauth = client.get("/api/admin/security-logs")
    assert res_unauth.status_code == 401

    # 2. Shared beta password token -> 401 (shared password is NOT an admin account!)
    res_pw = client.post("/api/auth/access/verify", json={"password": "amquant2026"})
    beta_token = res_pw.json()["session_token"]
    res_admin_beta = client.get("/api/admin/security-logs", headers={"X-Amquant-Access-Token": beta_token})
    assert res_admin_beta.status_code == 401

    # Create mock Supabase JWTs for tester vs owner
    secret = SUPABASE_JWT_SECRET or "test-jwt-secret-at-least-32-chars-long"

    from backend.app.auth import verifier
    verifier.jwt_secret = secret

    tester_payload = {
        "sub": str(uuid.uuid4()),
        "email": "tester@example.com",
        "aud": "authenticated",
        "iss": verifier.expected_issuer,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    tester_jwt = jwt.encode(tester_payload, secret, algorithm="HS256")

    owner_payload = {
        "sub": str(uuid.uuid4()),
        "email": OWNER_EMAIL,
        "aud": "authenticated",
        "iss": verifier.expected_issuer,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    owner_jwt = jwt.encode(owner_payload, secret, algorithm="HS256")

    res_tester = client.get("/api/admin/security-logs", headers={"Authorization": f"Bearer {tester_jwt}"})
    assert res_tester.status_code == 403
    assert "restricted to the platform owner" in res_tester.json()["detail"]

    # 4. Owner attempting admin endpoint -> 200 OK!
    res_owner = client.get("/api/admin/security-logs", headers={"Authorization": f"Bearer {owner_jwt}"})
    assert res_owner.status_code == 200
    assert "events" in res_owner.json()

    # 5. Owner rotating password
    res_rotate = client.post(
        "/api/admin/rotate-password",
        json={"new_password": "new_secure_amquant_pass_2026"},
        headers={"Authorization": f"Bearer {owner_jwt}"},
    )
    assert res_rotate.status_code == 200
    assert res_rotate.json()["ok"] is True

    # Old password no longer works
    assert client.post("/api/auth/access/verify", json={"password": "amquant2026"}).status_code == 401
    # New password works
    assert client.post("/api/auth/access/verify", json={"password": "new_secure_amquant_pass_2026"}).status_code == 200


def test_security_headers_injected_on_all_responses():
    """Responses must include X-Robots-Tag, X-Content-Type-Options, X-Frame-Options, and HSTS."""
    res = client.get("/api/health")
    assert res.headers.get("X-Robots-Tag") == "noindex, nofollow, noarchive, nosnippet"
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "DENY"
    assert "max-age=" in res.headers.get("Strict-Transport-Security", "")
