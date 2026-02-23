"""Authentication dependencies for protected API routes."""

import hmac

from fastapi import Depends, Header, HTTPException, status

from .settings import Settings, get_settings



def _extract_bearer_token(authorization: str | None) -> str:
    """Parse a bearer token from the Authorization header."""

    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing auth header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid auth scheme")

    return token



def require_api_key(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Validate caller token for standard API routes."""

    token = _extract_bearer_token(authorization)
    if not hmac.compare_digest(token, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")



def require_admin_api_key(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Validate caller token for admin-only routes."""

    token = _extract_bearer_token(authorization)
    expected = settings.admin_api_key or settings.api_key
    if not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")
