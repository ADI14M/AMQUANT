"""Pytest configuration and global fixtures for AMQUANT."""
import functools
import pytest
from fastapi.testclient import TestClient

from backend.app.access_security import access_rate_limiter, session_manager
from backend.app.security import rate_limiter

# Generate a reusable test session token for test suites
_test_session = session_manager.create_session("127.0.0.1")
TEST_ACCESS_TOKEN = _test_session["session_token"]

# Patch TestClient.request so that existing tests automatically send the access token
# while security tests can opt out by setting `client._skip_test_auth = True`
_original_request = TestClient.request

@functools.wraps(_original_request)
def _patched_request(self, method, url, *args, **kwargs):
    if not getattr(self, "_skip_test_auth", False):
        headers = kwargs.get("headers")
        if headers is None:
            kwargs["headers"] = {"X-Amquant-Access-Token": TEST_ACCESS_TOKEN}
        elif isinstance(headers, dict) and "X-Amquant-Access-Token" not in headers and "Authorization" not in headers:
            headers["X-Amquant-Access-Token"] = TEST_ACCESS_TOKEN
    return _original_request(self, method, url, *args, **kwargs)

TestClient.request = _patched_request


@pytest.fixture(autouse=True)
def reset_global_rate_limiter():
    """Reset the sliding window rate limiter and access rate limiter before and after each test."""
    rate_limiter.records.clear()
    access_rate_limiter._failures.clear()
    access_rate_limiter._lockouts.clear()
    yield
    rate_limiter.records.clear()
    access_rate_limiter._failures.clear()
    access_rate_limiter._lockouts.clear()
