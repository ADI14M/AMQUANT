"""Production security, rate limiting, access control, and resource protection for AMQUANT API."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import time
from typing import Callable

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app.access_security import security_logger, session_manager

logger = logging.getLogger("amquant.security")

# Resource protection configuration
MAX_REQUEST_BODY_BYTES = 64 * 1024  # 64 KB
RATE_LIMIT_REQUESTS = 30           # 30 requests per minute
RATE_LIMIT_WINDOW_SECONDS = 60.0   # 1 minute window
MAX_CONCURRENT_CALCULATIONS = 5    # Max simultaneous heavy calculations on single instance
CALCULATION_SEMAPHORE_TIMEOUT = 1.0  # Seconds to wait for semaphore before 503

# Global semaphore for expensive CPU/NumPy calculations
calculation_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALCULATIONS)

# Unauthenticated public endpoints (minimal public surface)
PUBLIC_EXEMPT_PATHS = {
    "/",
    "/api/health",
    "/api/health/ready",
    "/api/auth/access/verify",
    "/api/auth/access/status",
    "/api/auth/access/revoke",
}


async def execute_guarded_calculation(func: Callable, *args, **kwargs):
    """Execute a CPU-intensive calculation with concurrency protection.
    
    Limits concurrent expensive calculations to MAX_CONCURRENT_CALCULATIONS
    to prevent memory exhaustion on resource-constrained hosting (Render 512MB RAM).
    Offloads synchronous calculation code to a threadpool to avoid event-loop blocking.
    """
    try:
        await asyncio.wait_for(calculation_semaphore.acquire(), timeout=CALCULATION_SEMAPHORE_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            headers={"Retry-After": "3"},
            detail="The quantitative calculation engine is currently at peak capacity. Please retry in a few moments.",
        )
    try:
        return await run_in_threadpool(func, *args, **kwargs)
    finally:
        calculation_semaphore.release()


def get_client_ip(request: Request) -> str:
    """Extract client IP safely with Render/cloud reverse-proxy awareness.
    
    If request.client.host is a private/loopback address (meaning the connection
    arrived via Render's trusted reverse proxy), we inspect the X-Forwarded-For chain.
    """
    direct_host = request.client.host if request.client else "127.0.0.1"

    try:
        direct_ip_obj = ipaddress.ip_address(direct_host)
    except ValueError:
        return "127.0.0.1"

    if direct_ip_obj.is_private or direct_ip_obj.is_loopback:
        # Check CF-Connecting-IP first when connection arrives from trusted edge proxy
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            try:
                cf_obj = ipaddress.ip_address(cf_ip.strip())
                return str(cf_obj)
            except ValueError:
                pass

        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ips = [p.strip() for p in forwarded_for.split(",") if p.strip()]
            if ips:
                # Walk backwards to find the rightmost public client IP
                for candidate in reversed(ips):
                    try:
                        cand_obj = ipaddress.ip_address(candidate)
                        if not (cand_obj.is_private or cand_obj.is_loopback):
                            return str(cand_obj)
                    except ValueError:
                        continue
                try:
                    return str(ipaddress.ip_address(ips[0]))
                except ValueError:
                    pass

    return str(direct_ip_obj)


class SlidingWindowRateLimiter:
    """In-memory sliding-window rate limiter per client IP."""

    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: float = RATE_LIMIT_WINDOW_SECONDS):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.records: dict[str, list[float]] = {}
        self.last_cleanup = time.monotonic()

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        if now - self.last_cleanup > 60.0 or len(self.records) > 5000:
            self._cleanup(cutoff)
            self.last_cleanup = now

        timestamps = self.records.get(client_ip, [])
        valid_timestamps = [t for t in timestamps if t > cutoff]

        if len(valid_timestamps) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - valid_timestamps[0])) + 1
            self.records[client_ip] = valid_timestamps
            return False, max(retry_after, 1)

        valid_timestamps.append(now)
        self.records[client_ip] = valid_timestamps
        return True, 0

    def _cleanup(self, cutoff: float) -> None:
        """Remove IPs that have no timestamps in the current window."""
        stale_keys = [k for k, v in self.records.items() if not v or v[-1] <= cutoff]
        for k in stale_keys:
            del self.records[k]


rate_limiter = SlidingWindowRateLimiter()


def is_authenticated_request(request: Request) -> bool:
    """Determine whether request holds a valid access session token or Supabase JWT."""
    # 1. Check custom X-Amquant-Access-Token header
    token = request.headers.get("X-Amquant-Access-Token")
    if token and token.strip():
        valid, _ = session_manager.verify_session(token.strip())
        if valid:
            return True

    # 2. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.strip():
        scheme, _, bearer_token = auth_header.partition(" ")
        if scheme.lower() == "bearer" and bearer_token.strip():
            candidate = bearer_token.strip()
            # Try as access session token
            valid, _ = session_manager.verify_session(candidate)
            if valid:
                return True
            # Try as Supabase JWT
            try:
                from backend.app.auth import verifier
                claims = verifier.verify_token(candidate)
                if claims and claims.get("sub"):
                    return True
            except Exception:
                pass

    # 3. Check cookie
    cookie_token = request.cookies.get("amquant_access_session")
    if cookie_token and cookie_token.strip():
        valid, _ = session_manager.verify_session(cookie_token.strip())
        if valid:
            return True

    return False


def apply_security_headers(response: Response) -> Response:
    """Inject strict security headers across all HTTP responses."""
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing access authorization, payload limits, rate limits, and security headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        method = request.method
        client_ip = get_client_ip(request)

        # 1. Allow CORS preflight requests (OPTIONS) to proceed cleanly to CORSMiddleware
        if method == "OPTIONS":
            response = await call_next(request)
            return apply_security_headers(response)

        # 2. Check if route requires private platform access authorization
        is_public = path in PUBLIC_EXEMPT_PATHS
        if not is_public and path.startswith("/api/"):
            if not is_authenticated_request(request):
                security_logger.log(
                    "UNAUTHORIZED_ACCESS_ATTEMPT",
                    client_ip,
                    f"Blocked unauthenticated call to {method} {path}",
                )
                response = JSONResponse(
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                    content={
                        "detail": "Private platform access required. Please authenticate with the shared access password."
                    },
                )
                return apply_security_headers(response)

        # 3. Check request body size limit via Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_int = int(content_length)
                if length_int > MAX_REQUEST_BODY_BYTES:
                    logger.warning("Rejected payload of %d bytes from client %s (limit: %d)", length_int, client_ip, MAX_REQUEST_BODY_BYTES)
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large ({length_int} bytes). Maximum allowed size is {MAX_REQUEST_BODY_BYTES} bytes."
                        },
                    )
                    return apply_security_headers(response)
            except ValueError:
                pass

        # 4. Rate limiting per client IP (exempting health check endpoints)
        if path not in {"/api/health", "/api/health/ready", "/"}:
            allowed, retry_after = rate_limiter.is_allowed(client_ip)
            if not allowed:
                security_logger.log("RATE_LIMIT_EXCEEDED", client_ip, f"Rate limit on {path}")
                response = JSONResponse(
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                    content={
                        "detail": f"Rate limit exceeded (maximum {RATE_LIMIT_REQUESTS} requests per minute). Please retry in {retry_after} seconds."
                    },
                )
                return apply_security_headers(response)

        try:
            response = await call_next(request)
            return apply_security_headers(response)
        except Exception as exc:
            logger.error("Unhandled exception during request processing for %s: %s", path, exc, exc_info=True)
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal error occurred while processing the calculation. Please verify your inputs and try again."
                },
            )
            return apply_security_headers(response)
