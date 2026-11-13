"""AMQUANT Private Platform Access Security, Argon2id Password Hashing, Session Management & Audit Logging."""
from __future__ import annotations

import collections
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import jwt
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

logger = logging.getLogger("amquant.access_security")

# Load environment variables if not already loaded
try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    load_dotenv(".env")
    load_dotenv("frontend/.env.local")
except ImportError:
    pass

# ==============================================================================
# CONFIGURATION & SECRETS
# ==============================================================================

OWNER_EMAIL = (os.getenv("AMQUANT_OWNER_EMAIL") or "adi@amquant.in").strip().lower()

# Secret used to sign session access tokens
AMQUANT_SESSION_SECRET = (
    os.getenv("AMQUANT_SESSION_SECRET")
    or os.getenv("SUPABASE_JWT_SECRET")
    or secrets.token_hex(32)
)

# Shared access password configuration
ENV_PASSWORD_HASH = os.getenv("AMQUANT_SHARED_ACCESS_PASSWORD_HASH", "").strip()
ENV_PLAINTEXT_PASSWORD = os.getenv("AMQUANT_SHARED_ACCESS_PASSWORD", "").strip()

# Session lifetime (7 days)
SESSION_DURATION_SECONDS = 7 * 24 * 3600

# Rate limiting for password unlock attempts
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300.0   # 5 minutes
LOCKOUT_DURATION_SECONDS = 900.0 # 15 minutes lockout


# ==============================================================================
# SECURITY EVENT LOGGER
# ==============================================================================

class SecurityEventLogger:
    """In-memory security event audit logger with circular buffer and structured output."""

    def __init__(self, max_events: int = 1000):
        self._events: collections.deque[dict[str, Any]] = collections.deque(maxlen=max_events)

    def log(self, event_type: str, client_ip: str, detail: str = "", metadata: dict[str, Any] | None = None) -> None:
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "client_ip": client_ip,
            "detail": detail,
            "metadata": metadata or {},
        }
        self._events.append(event)
        logger.info("[SECURITY EVENT: %s] IP=%s Detail=%s", event_type, client_ip, detail)

    def get_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, len(self._events)))
        return list(self._events)[-limit:]


security_logger = SecurityEventLogger()


# ==============================================================================
# ARGON2ID PASSWORD MANAGER
# ==============================================================================

class AccessPasswordManager:
    """Manages constant-time Argon2id password verification and dynamic password rotation."""

    def __init__(self):
        self._active_hash: str = ""
        self._initialize()

    def _initialize(self) -> None:
        if ENV_PASSWORD_HASH:
            self._active_hash = ENV_PASSWORD_HASH
            logger.info("Loaded shared access password hash from environment.")
        elif ENV_PLAINTEXT_PASSWORD:
            self._active_hash = self.hash_password(ENV_PLAINTEXT_PASSWORD)
            logger.info("Derived Argon2id hash from environment plaintext password.")
        else:
            # Fallback default for development / local testing
            default_dev_pw = "amquant2026"
            self._active_hash = self.hash_password(default_dev_pw)
            logger.warning(
                "No AMQUANT_SHARED_ACCESS_PASSWORD_HASH or AMQUANT_SHARED_ACCESS_PASSWORD configured. "
                "Defaulting to development password 'amquant2026'. Set this in production!"
            )

    @staticmethod
    def hash_password(plaintext: str) -> str:
        """Derive an Argon2id PHC-encoded hash with a random 16-byte salt."""
        salt = os.urandom(16)
        kdf = Argon2id(salt=salt, length=32, iterations=2, lanes=4, memory_cost=65536)
        return kdf.derive_phc_encoded(plaintext.encode("utf-8"))

    def verify_password(self, candidate: str) -> bool:
        """Verify candidate password using constant-time Argon2id PHC verification."""
        if not candidate or not self._active_hash:
            return False
        try:
            Argon2id.verify_phc_encoded(candidate.encode("utf-8"), self._active_hash)
            return True
        except Exception:
            return False

    def rotate_password(self, new_plaintext: str) -> str:
        """Rotate the active password in memory and return the new PHC hash."""
        if len(new_plaintext.strip()) < 8:
            raise ValueError("Access password must be at least 8 characters long.")
        new_hash = self.hash_password(new_plaintext.strip())
        self._active_hash = new_hash
        return new_hash

    @property
    def current_hash_preview(self) -> str:
        """Preview first and last characters of current hash for admin verification without exposing salt/key."""
        if not self._active_hash:
            return "none"
        parts = self._active_hash.split("$")
        return f"$argon2id${parts[2] if len(parts) > 2 else 'v=19'}...{self._active_hash[-6:]}"


password_manager = AccessPasswordManager()


# ==============================================================================
# FAILED ATTEMPT RATE LIMITER
# ==============================================================================

class AccessRateLimiter:
    """Enforces strict rate limiting on access password attempts with temporary IP lockout."""

    def __init__(
        self,
        max_attempts: int = MAX_FAILED_ATTEMPTS,
        window_seconds: float = LOCKOUT_WINDOW_SECONDS,
        lockout_duration_seconds: float = LOCKOUT_DURATION_SECONDS,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_duration_seconds = lockout_duration_seconds
        # client_ip -> list of failure timestamps
        self._failures: dict[str, list[float]] = {}
        # client_ip -> lockout expiration timestamp
        self._lockouts: dict[str, float] = {}

    def is_locked(self, client_ip: str) -> tuple[bool, int]:
        """Check if an IP is currently locked out. Returns (locked, remaining_seconds)."""
        now = time.monotonic()
        locked_until = self._lockouts.get(client_ip, 0.0)
        if now < locked_until:
            remaining = int(locked_until - now) + 1
            return True, max(remaining, 1)

        # Clear expired lockout
        if client_ip in self._lockouts:
            del self._lockouts[client_ip]
            self._failures.pop(client_ip, None)

        return False, 0

    def record_failure(self, client_ip: str) -> tuple[bool, int]:
        """Record a failed attempt. If threshold exceeded, triggers lockout. Returns (is_locked_now, retry_after)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        timestamps = [t for t in self._failures.get(client_ip, []) if t > cutoff]
        timestamps.append(now)
        self._failures[client_ip] = timestamps

        if len(timestamps) >= self.max_attempts:
            lockout_until = now + self.lockout_duration_seconds
            self._lockouts[client_ip] = lockout_until
            retry_after = int(self.lockout_duration_seconds)
            security_logger.log(
                "ACCESS_PASSWORD_LOCKED",
                client_ip,
                f"IP locked out for {retry_after}s after {len(timestamps)} failed attempts",
            )
            return True, retry_after

        return False, 0

    def record_success(self, client_ip: str) -> None:
        """Reset failures for an IP upon successful unlock."""
        self._failures.pop(client_ip, None)
        self._lockouts.pop(client_ip, None)

    def get_status(self) -> dict[str, Any]:
        """Return active lockouts and failure tracking statistics."""
        now = time.monotonic()
        active_lockouts = {
            ip: int(exp - now) for ip, exp in self._lockouts.items() if exp > now
        }
        return {
            "locked_ip_count": len(active_lockouts),
            "locked_ips": active_lockouts,
            "tracked_ip_count": len(self._failures),
        }


access_rate_limiter = AccessRateLimiter()


# ==============================================================================
# SESSION MANAGER (CRYPTOGRAPHIC SIGNED ACCESS TOKENS)
# ==============================================================================

class AccessSessionManager:
    """Issues and verifies cryptographically signed JWT access tokens with revocation support."""

    def __init__(self, secret: str = AMQUANT_SESSION_SECRET):
        self.secret = secret
        self.revoked_jtis: set[str] = set()
        self.revocation_epoch: float = 0.0

    def create_session(self, client_ip: str) -> dict[str, Any]:
        """Create a new signed session token valid for SESSION_DURATION_SECONDS."""
        now = int(time.time())
        exp = now + SESSION_DURATION_SECONDS
        jti = str(uuid.uuid4())

        payload = {
            "sub": "beta_access",
            "role": "platform_access",
            "jti": jti,
            "iat": now,
            "exp": exp,
            "client_ip": client_ip,
        }

        token = jwt.encode(payload, self.secret, algorithm="HS256")
        expires_at_iso = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()

        security_logger.log("SESSION_CREATED", client_ip, f"Session jti={jti} issued")
        return {
            "session_token": token,
            "expires_at": expires_at_iso,
            "jti": jti,
        }

    def verify_session(self, token: str) -> tuple[bool, dict[str, Any] | None]:
        """Verify token signature, expiry, and revocation state. Returns (is_valid, claims)."""
        if not token:
            return False, None
        try:
            claims = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                options={"verify_exp": True, "verify_iat": True, "require": ["exp", "sub", "jti", "iat"]},
            )

            # Check revocation epoch (revoke all)
            token_iat = claims.get("iat", 0)
            if token_iat < self.revocation_epoch:
                return False, None

            # Check specific JTI blacklist
            jti = claims.get("jti")
            if jti in self.revoked_jtis:
                return False, None

            # Verify subject and role
            if claims.get("sub") != "beta_access" or claims.get("role") != "platform_access":
                return False, None

            return True, claims
        except Exception:
            return False, None

    def revoke_session(self, token: str) -> bool:
        """Revoke a single session token."""
        valid, claims = self.verify_session(token)
        if valid and claims and "jti" in claims:
            self.revoked_jtis.add(claims["jti"])
            security_logger.log("SESSION_REVOKED", claims.get("client_ip", "unknown"), f"Session jti={claims['jti']} revoked")
            return True
        return False

    def revoke_all_sessions(self) -> None:
        """Revoke all currently issued sessions globally."""
        self.revocation_epoch = time.time()
        self.revoked_jtis.clear()
        security_logger.log("ALL_SESSIONS_REVOKED", "admin", f"All sessions issued prior to {self.revocation_epoch} invalidated")


session_manager = AccessSessionManager()


# ==============================================================================
# OWNER PRIVILEGE VERIFICATION
# ==============================================================================

def is_owner_email(email: str | None) -> bool:
    """Check if an email matches the configured owner email."""
    if not email:
        return False
    return email.strip().lower() == OWNER_EMAIL
