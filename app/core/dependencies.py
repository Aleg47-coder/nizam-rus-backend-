"""
app/core/dependencies.py
─────────────────────────
FastAPI dependency functions injected via Depends().

get_current_user:
  Reads the Bearer token from the Authorization header, decodes it,
  and returns the User ORM object. Used on every protected route.

get_current_verified_user:
  Same as above but also ensures the email has been verified.
  Use this on routes where unverified users should be blocked
  (e.g., updating progress — no point saving data for ghost accounts).

Usage in a router:
    from app.core.dependencies import get_current_verified_user
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/me")
    async def get_me(
        current_user: User = Depends(get_current_verified_user),
    ):
        return current_user
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# HTTPBearer extracts the token from "Authorization: Bearer <token>"
bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the JWT → look up the user in the DB → return the User object.
    Raises HTTP 401 on any failure (invalid token, expired, user deleted).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Fetch user from DB — confirms they still exist and aren't deactivated
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Extension of get_current_user that additionally blocks unverified accounts.
    Returns the same User object — just with the extra gate.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified. Please check your inbox.",
        )
    return current_user
