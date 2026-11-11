"""Cryptographic Supabase JWT verification and FastAPI authentication dependencies."""
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any
import jwt
from jwt import PyJWKClient, PyJWTError
from fastapi import Depends, Header, HTTPException, status

logger = logging.getLogger("amquant.auth")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

# Expected claims
EXPECTED_AUDIENCE = "authenticated"
EXPECTED_ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else None


@dataclass(frozen=True)
class AuthenticatedUser:
    """Represents a cryptographically verified user identity from a Supabase JWT."""
    id: uuid.UUID
    email: str
    jwt: str
    claims: dict[str, Any]


class SupabaseTokenVerifier:
    """Verifies Supabase JWT access tokens using either JWKS (asymmetric) or shared secret (HS256)."""

    def __init__(self, supabase_url: str = SUPABASE_URL, jwt_secret: str = SUPABASE_JWT_SECRET):
        self.supabase_url = supabase_url
        self.jwt_secret = jwt_secret
        self._jwks_client: PyJWKClient | None = None
        if self.supabase_url:
            jwks_url = f"{self.supabase_url}/auth/v1/.well-known/jwks.json"
            self._jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)

    def verify_token(self, token: str) -> dict[str, Any]:
        """Verify JWT signature, expiry, issuer, subject, and audience.
        
        Returns decoded claims dict on success.
        Raises ValueError with details on failure.
        """
        if not token:
            raise ValueError("Token is required")

        # Peek at header to determine algorithm and key ID
        try:
            unverified_header = jwt.get_unverified_header(token)
        except PyJWTError as exc:
            raise ValueError(f"Malformed token header: {exc}") from exc

        alg = unverified_header.get("alg", "HS256")
        
        # Options to enforce
        decode_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "require": ["exp", "sub"],
        }

        # 1. Asymmetric verification (RS256, ES256, etc.) via Supabase JWKS
        if alg.startswith(("RS", "ES")) and self._jwks_client:
            try:
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[alg],
                    audience=EXPECTED_AUDIENCE,
                    issuer=EXPECTED_ISSUER if EXPECTED_ISSUER else None,
                    options=decode_options,
                )
                return claims
            except Exception as exc:
                raise ValueError(f"Asymmetric token verification failed: {exc}") from exc

        # 2. Symmetric verification (HS256) via SUPABASE_JWT_SECRET
        if self.jwt_secret:
            try:
                claims = jwt.decode(
                    token,
                    self.jwt_secret,
                    algorithms=["HS256"],
                    audience=EXPECTED_AUDIENCE,
                    issuer=EXPECTED_ISSUER if EXPECTED_ISSUER else None,
                    options=decode_options,
                )
                return claims
            except PyJWTError as exc:
                raise ValueError(f"Symmetric token verification failed: {exc}") from exc

        # 3. Fallback: If JWKS client configured but token is HS256 and no secret set
        if not self.jwt_secret and not (alg.startswith(("RS", "ES")) and self._jwks_client):
            raise ValueError(
                "Backend authentication is not configured: missing SUPABASE_JWT_SECRET or JWKS endpoint"
            )

        raise ValueError(f"Unsupported token algorithm '{alg}' or missing verification key")


# Singleton token verifier
verifier = SupabaseTokenVerifier()


def get_current_user(authorization: str | None = Header(None)) -> AuthenticatedUser:
    """FastAPI dependency for protected endpoints requiring verified authentication.
    
    Extracts Bearer token from Authorization header and cryptographically validates it.
    Never trusts client-supplied user IDs; derives identity solely from JWT subject ('sub').
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme; Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = token.strip()
    try:
        claims = verifier.verify_token(token)
    except ValueError as exc:
        logger.warning("Rejected invalid JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or untrusted authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim ('sub')",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(sub))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject ('sub') is not a valid UUID",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    email = str(claims.get("email", ""))
    return AuthenticatedUser(id=user_uuid, email=email, jwt=token, claims=claims)


def get_optional_user(authorization: str | None = Header(None)) -> AuthenticatedUser | None:
    """FastAPI dependency for endpoints accessible to both guests and authenticated users.
    
    Returns AuthenticatedUser if a valid Bearer token is provided, or None for guests.
    """
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None

    try:
        claims = verifier.verify_token(token.strip())
        sub = claims.get("sub")
        if not sub:
            return None
        user_uuid = uuid.UUID(str(sub))
        return AuthenticatedUser(
            id=user_uuid,
            email=str(claims.get("email", "")),
            jwt=token.strip(),
            claims=claims,
        )
    except Exception:
        # For optional auth, malformed or expired tokens simply treat caller as guest
        return None

