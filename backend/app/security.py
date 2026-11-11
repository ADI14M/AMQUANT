"""Production security, rate limiting, and resource protection for AMQUANT API."""
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

logger = logging.getLogger("amquant.security")

# Resource protection configuration
MAX_REQUEST_BODY_BYTES = 64 * 1024  # 64 KB
RATE_LIMIT_REQUESTS = 30           # 30 requests per minute
RATE_LIMIT_WINDOW_SECONDS = 60.0   # 1 minute window
MAX_CONCURRENT_CALCULATIONS = 5    # Max simultaneous heavy calculations on single instance
CALCULATION_SEMAPHORE_TIMEOUT = 1.0  # Seconds to wait for semaphore before 503

# Global semaphore for expensive CPU/NumPy calculations
calculation_semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALCULATIONS)


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
    In proxy architectures that append client IPs, the rightmost non-internal IP or
    the verified connecting IP is selected to prevent spoofing.
    If the direct connection is from a public IP, X-Forwarded-For is not trusted.
    """
    direct_host = request.client.host if request.client else "127.0.0.1"

    try:
        direct_ip_obj = ipaddress.ip_address(direct_host)
    except ValueError:
        return "127.0.0.1"

    # If connected through a private/internal network (e.g. Render proxy or local)
    if direct_ip_obj.is_private or direct_ip_obj.is_loopback:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Render proxy appends the client IP to X-Forwarded-For
            # Split and clean all parts
            ips = [p.strip() for p in forwarded_for.split(",") if p.strip()]
            if ips:
                # Iterate from right to left to find the first valid non-internal IP,
                # or fallback to the leftmost IP
                for candidate in reversed(ips):
                    try:
                        cand_obj = ipaddress.ip_address(candidate)
                        if not (cand_obj.is_private or cand_obj.is_loopback):
                            return str(cand_obj)
                    except ValueError:
                        continue
                # If all were private/loopback, return the first valid IP
                try:
                    return str(ipaddress.ip_address(ips[0]))
                except ValueError:
                    pass

    return str(direct_ip_obj)


class SlidingWindowRateLimiter:
    """In-memory sliding-window rate limiter per client IP.
    
    Maintains timestamp records in a sliding window with automatic pruning
    to avoid memory leakage on memory-constrained (512MB) instances.
    """

    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: float = RATE_LIMIT_WINDOW_SECONDS):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.records: dict[str, list[float]] = {}
        self.last_cleanup = time.monotonic()

    def is_allowed(self, client_ip: str) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Periodically prune stale IPs every 60 seconds or if tracking over 5000 IPs
        if now - self.last_cleanup > 60.0 or len(self.records) > 5000:
            self._cleanup(cutoff)
            self.last_cleanup = now

        timestamps = self.records.get(client_ip, [])
        # Filter timestamps in current window
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


# Global rate limiter instance
rate_limiter = SlidingWindowRateLimiter()


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing payload size limits and per-IP rate limits."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # 1. Exempt health and documentation endpoints from rate limiting
        if path in {"/api/health", "/api/health/ready", "/", "/docs", "/openapi.json"}:
            return await call_next(request)

        # 2. Check request body size limit via Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_int = int(content_length)
                if length_int > MAX_REQUEST_BODY_BYTES:
                    logger.warning("Rejected payload of %d bytes from client (limit: %d)", length_int, MAX_REQUEST_BODY_BYTES)
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body too large ({length_int} bytes). Maximum allowed size is {MAX_REQUEST_BODY_BYTES} bytes."
                        },
                    )
            except ValueError:
                pass

        # 3. Rate limiting per client IP
        client_ip = get_client_ip(request)
        allowed, retry_after = rate_limiter.is_allowed(client_ip)
        if not allowed:
            logger.warning("Rate limit exceeded for IP: %s (path: %s)", client_ip, path)
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": str(retry_after)},
                content={
                    "detail": f"Rate limit exceeded (maximum {RATE_LIMIT_REQUESTS} requests per minute). Please retry in {retry_after} seconds."
                },
            )

        try:
            return await call_next(request)
        except Exception as exc:
            logger.error("Unhandled exception during request processing for %s: %s", path, exc, exc_info=True)
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal error occurred while processing the calculation. Please verify your inputs and try again."
                },
            )
