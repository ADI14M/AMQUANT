"""Routes for Private Platform Shared Password Verification and Access Session Management."""
from typing import Any
from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.app.access_security import (
    SESSION_DURATION_SECONDS,
    access_rate_limiter,
    password_manager,
    security_logger,
    session_manager,
)
from backend.app.security import get_client_ip

router = APIRouter(prefix="/api/auth/access", tags=["Private Access Gate"])


class VerifyAccessRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128, description="Shared private access password")


@router.post("/verify")
async def verify_access(
    req: VerifyAccessRequest,
    request: Request,
    response: Response,
) -> dict[str, Any]:
    """Verify shared access password and issue a cryptographically signed session token."""
    client_ip = get_client_ip(request)

    # 1. Check rate-limit lockout
    locked, retry_after = access_rate_limiter.is_locked(client_ip)
    if locked:
        security_logger.log(
            "ACCESS_PASSWORD_LOCKED",
            client_ip,
            f"Blocked unlock attempt during active lockout ({retry_after}s remaining)",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            detail=f"Too many failed unlock attempts. Access is temporarily locked. Please retry in {retry_after} seconds.",
        )

    # 2. Verify password with constant-time Argon2id check
    is_valid = password_manager.verify_password(req.password)
    if not is_valid:
        is_locked_now, retry_after_failure = access_rate_limiter.record_failure(client_ip)
        security_logger.log("ACCESS_PASSWORD_FAILURE", client_ip, "Incorrect password attempt")
        if is_locked_now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after_failure)},
                detail=f"Too many failed unlock attempts. Access is locked for {retry_after_failure} seconds.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect access password. Please verify and retry.",
        )

    # 3. Successful verification -> reset failures and issue session
    access_rate_limiter.record_success(client_ip)
    security_logger.log("ACCESS_PASSWORD_SUCCESS", client_ip, "Platform access unlocked successfully")
    session = session_manager.create_session(client_ip)

    # Set secure HttpOnly cookie for browsers supporting credentialed CORS
    response.set_cookie(
        key="amquant_access_session",
        value=session["session_token"],
        max_age=SESSION_DURATION_SECONDS,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )

    return {
        "ok": True,
        "session_token": session["session_token"],
        "expires_at": session["expires_at"],
        "detail": "AMQUANT private access unlocked.",
    }


def extract_token_from_request(
    request: Request,
    x_access_token: str | None = None,
    authorization: str | None = None,
) -> str | None:
    """Extract session token from header or cookie."""
    if x_access_token and x_access_token.strip():
        return x_access_token.strip()

    if authorization and authorization.strip():
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()

    cookie_token = request.cookies.get("amquant_access_session")
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    return None


@router.get("/status")
async def get_access_status(
    request: Request,
    x_amquant_access_token: str | None = Header(None, alias="X-Amquant-Access-Token"),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Check if the caller holds an active, verified access session."""
    token = extract_token_from_request(request, x_amquant_access_token, authorization)
    if not token:
        return {"authenticated": False}

    valid, claims = session_manager.verify_session(token)
    if not valid or not claims:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "expires_at": claims.get("exp"),
        "role": claims.get("role"),
    }


@router.post("/revoke")
async def revoke_access(
    request: Request,
    response: Response,
    x_amquant_access_token: str | None = Header(None, alias="X-Amquant-Access-Token"),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Revoke the current access session and delete cookie."""
    token = extract_token_from_request(request, x_amquant_access_token, authorization)
    if token:
        session_manager.revoke_session(token)

    response.delete_cookie(
        key="amquant_access_session",
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    )
    return {"ok": True, "detail": "Access session revoked successfully."}
