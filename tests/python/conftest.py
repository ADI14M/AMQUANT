"""Pytest configuration and global fixtures for AMQUANT."""
import pytest
from backend.app.security import rate_limiter

@pytest.fixture(autouse=True)
def reset_global_rate_limiter():
    """Reset the sliding window rate limiter before and after each test."""
    rate_limiter.records.clear()
    yield
    rate_limiter.records.clear()

