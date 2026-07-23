"""
app/core/schemas.py
───────────────────
Pydantic v2 schemas define the exact shape of every API request and response.

Rule of thumb used here:
  - *Request schemas* (Register, Login, etc.) validate incoming data.
  - *Response schemas* (UserOut, TokenOut, etc.) control what leaves the server.
  - Passwords and tokens are NEVER included in response schemas.

model_config = ConfigDict(from_attributes=True) lets Pydantic read ORM objects
directly without manually calling .dict() on them.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


# ════════════════════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    """Body for POST /auth/register"""
    email: EmailStr
    username: str = Field(
        min_length=3, max_length=30,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="3–30 chars, letters/digits/underscore/hyphen only"
    )
    password: str = Field(min_length=8, max_length=128)
    language_preference: Literal["az", "ru", "en"] = "az"

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce at least one digit and one letter."""
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        return v


class LoginRequest(BaseModel):
    """Body for POST /auth/login — accepts email or username"""
    email_or_username: str = Field(description="Email address or username")
    password: str


class TokenOut(BaseModel):
    """Returned on successful login"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int                   # seconds until expiry
    user: "UserOut"                   # embedded so frontend has profile immediately


class MessageResponse(BaseModel):
    """Generic OK / info response"""
    message: str
    detail: Optional[str] = None


# ════════════════════════════════════════════════════════════════════════════
# USER
# ════════════════════════════════════════════════════════════════════════════

class UserOut(BaseModel):
    """Safe user representation — no password hash, no verification token"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    is_verified: bool
    is_active: bool
    language_preference: str
    start_date: Optional[str]
    created_at: datetime


class LanguagePreferenceUpdate(BaseModel):
    """Body for PATCH /users/me/language"""
    language: Literal["az", "ru", "en"]


# ════════════════════════════════════════════════════════════════════════════
# PROGRESS
# ════════════════════════════════════════════════════════════════════════════

class ProgressEntry(BaseModel):
    """A single completed-day record — matches the Progress ORM model"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_number: int
    phase: str
    completed: bool
    completed_at: datetime


class UpdateProgressRequest(BaseModel):
    """
    Body for POST /progress/update

    Supports toggling a single day OR bulk-importing progress (e.g. on first login
    when the user already has localStorage data they want to sync to the server).
    """
    day_number: int = Field(ge=1, le=180)
    phase: Literal["a1", "a2", "b1", "b2"]
    # True = mark complete, False = un-mark (toggle support)
    completed: bool = True


class BulkProgressRequest(BaseModel):
    """Body for POST /progress/bulk — sync multiple days at once"""
    entries: list[UpdateProgressRequest] = Field(max_length=180)


class ProgressResponse(BaseModel):
    """Returned by GET /progress/me"""
    # completed_days is the dict the frontend already uses: {"1": true, "5": true}
    completed_days: dict[str, bool]
    total_completed: int
    start_date: Optional[str]


# Forward reference resolution (Python 3.10 still needs this)
TokenOut.model_rebuild()
