"""Authentication dependencies for FastAPI.

Uses Supabase Auth for user management. JWTs issued by Supabase are
verified via the supabase-py client's `auth.get_user(token)` method,
which validates the token signature and expiry against the Supabase
backend.

For service-to-service calls (e.g. GitHub Actions triggering scrapes),
a static SERVICE_API_KEY is accepted as a fallback.
"""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.database import get_supabase_client

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    settings: Settings = Depends(get_settings),
):
    """Verify the Bearer token and return the authenticated user.

    Supports two auth modes:
    1. Supabase JWT — issued after email/password login.
    2. Service API key — a static key for automated (non-user) calls.

    Raises:
        HTTPException 401: If the token is invalid or expired.
    """
    token = credentials.credentials

    # Mode 2: Service API key (for GitHub Actions, cron jobs)
    if settings.service_api_key and token == settings.service_api_key:
        return {"id": "service", "email": "service@automated", "is_service": True}

    # Mode 1: Supabase JWT verification
    try:
        client = get_supabase_client()
        user_response = client.auth.get_user(token)
        user = user_response.user
        if user is None:
            raise ValueError("No user returned")
        return {
            "id": user.id,
            "email": user.email,
            "is_service": False,
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_user(current_user: dict = Depends(get_current_user)):
    """Dependency that ensures the caller is an actual user, not a service key."""
    if current_user.get("is_service"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires user authentication, not a service key.",
        )
    return current_user
