"""
app/core/security.py
────────────────────
All cryptographic primitives live here:
  - Password hashing (bcrypt via passlib)
  - JWT access token creation and verification
  - Secure random token generation (for email verification)

Keeping this isolated means you can swap algorithms without touching routes.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# ── Password hashing ──────────────────────────────────────────────────────────
# bcrypt is the industry standard. deprecated="auto" means old hashes are
# transparently re-hashed on next login (handles future algorithm upgrades).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Turn a plain-text password into a bcrypt hash. Store the hash, not the plain."""
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Compare a plain-text password against a stored hash.
    Returns True if they match, False otherwise.
    This is timing-safe — takes the same time regardless of where mismatch occurs.
    """
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(subject: Any, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: Typically the user's ID (str/int). Goes into the "sub" claim.
        expires_delta: How long until the token expires. Defaults to settings.

    Returns:
        A signed JWT string to send to the frontend.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": str(subject),    # Subject — who this token represents
        "exp": expire,          # Expiry — rejected after this timestamp
        "iat": datetime.now(timezone.utc),  # Issued at
        "type": "access",       # Custom claim to distinguish from refresh tokens
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT. Raises JWTError on tampered / expired tokens.

    Returns:
        The decoded payload dict (e.g. {"sub": "42", "exp": ..., "type": "access"})
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        # Guard against accidentally accepting refresh tokens as access tokens
        if payload.get("type") != "access":
            raise JWTError("Wrong token type")
        return payload
    except JWTError:
        raise   # Re-raise; caller handles the HTTP 401 response


# ── Email verification tokens ─────────────────────────────────────────────────
def generate_verification_token() -> str:
    """
    Create a cryptographically secure URL-safe random token.
    32 bytes = 256 bits of entropy — far beyond brute-force reach.
    """
    return secrets.token_urlsafe(32)
