"""
app/routers/auth.py
────────────────────
Authentication endpoints:

  POST /api/auth/register      — Create account, send verification email
  POST /api/auth/login         — Exchange credentials for JWT
  GET  /api/auth/verify-email  — Flip is_verified=True via token in URL
  POST /api/auth/resend-verification — Re-send the verification email
  GET  /api/auth/me            — Return the authenticated user's profile

All endpoints are documented automatically via FastAPI's OpenAPI at /docs.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.schemas import (
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    TokenOut,
    UserOut,
)
from app.core.security import (
    create_access_token,
    generate_verification_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.services.email_service import send_verification_email

settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    body: RegisterRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Flow:
      1. Check email + username are not already taken.
      2. Hash the password (never store plain text).
      3. Generate a secure verification token with a 24-hour expiry.
      4. Save the user to the DB with is_verified=False.
      5. Send the verification email in the background (non-blocking).
      6. Return a 201 with instructions to check email.

    The user cannot log in until they verify their email.
    (The /login endpoint enforces this check.)
    """
    # ── 1. Uniqueness check ───────────────────────────────────────────────────
    existing = await db.execute(
        select(User).where(
            or_(
                User.email == body.email.lower(),
                User.username == body.username.lower(),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or username already exists.",
        )

    # ── 2. Hash the password ──────────────────────────────────────────────────
    hashed = hash_password(body.password)

    # ── 3. Generate verification token ────────────────────────────────────────
    token = generate_verification_token()
    token_expires = datetime.now(timezone.utc) + timedelta(
        hours=settings.verification_token_expire_hours
    )

    # ── 4. Create and persist the user ────────────────────────────────────────
    new_user = User(
        email=body.email.lower(),
        username=body.username.lower(),
        hashed_password=hashed,
        language_preference=body.language_preference,
        is_verified=False,              # Not verified until they click the link
        verification_token=token,
        verification_token_expires=token_expires,
    )
    db.add(new_user)
    await db.flush()    # Flush to get new_user.id without committing yet

    # ── 5. Send verification email in background ──────────────────────────────
    # BackgroundTasks runs AFTER the response is sent — so the user gets their
    # 201 immediately instead of waiting for the SMTP/Resend round trip.
    base_url = str(request.base_url).rstrip("/")
    background_tasks.add_task(
        send_verification_email,
        to_email=new_user.email,
        username=new_user.username,
        token=token,
        base_url=base_url,
    )

    # DB commit happens automatically in get_db() dependency on clean exit
    return MessageResponse(
        message="Account created successfully! Check your email to verify your account.",
        detail=f"A verification link has been sent to {new_user.email}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/login",
    response_model=TokenOut,
    summary="Login and receive a JWT access token",
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenOut:
    """
    Flow:
      1. Find user by email OR username.
      2. Verify the password.
      3. Check is_verified (unverified users get a specific 403 message).
      4. Issue and return a JWT access token.

    Security: We use the same generic error message for "not found" and "wrong
    password" to prevent username/email enumeration attacks.
    """
    # ── 1. Find user ──────────────────────────────────────────────────────────
    identifier = body.email_or_username.lower()
    result = await db.execute(
        select(User).where(
            or_(User.email == identifier, User.username == identifier)
        )
    )
    user = result.scalar_one_or_none()

    # ── 2. Verify password ────────────────────────────────────────────────────
    # We deliberately give the same error for "user not found" and "wrong password"
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password.",
        )

    # ── 3. Check account state ────────────────────────────────────────────────
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in. Check your inbox for the verification link.",
        )

    # ── 4. Issue JWT ──────────────────────────────────────────────────────────
    expire_minutes = settings.jwt_access_token_expire_minutes
    access_token = create_access_token(subject=user.id)

    return TokenOut(
        access_token=access_token,
        token_type="bearer",
        expires_in=expire_minutes * 60,   # Frontend can use this to auto-logout
        user=UserOut.model_validate(user),
    )


# ─────────────────────────────────────────────────────────────────────────────
# VERIFY EMAIL
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/verify-email",
    response_model=MessageResponse,
    summary="Verify email address via token from email link",
)
async def verify_email(
    token: str = Query(..., description="The verification token from the email link"),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    The user clicks the link in their email → browser hits this endpoint.

    Flow:
      1. Find the user with this token.
      2. Check it hasn't expired.
      3. Flip is_verified=True and clear the token (one-use).

    After verifying, redirect the user to the frontend login page.
    (In production, return a redirect response instead of JSON.)
    """
    # ── 1. Find user with this token ──────────────────────────────────────────
    result = await db.execute(
        select(User).where(User.verification_token == token)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token.",
        )

    # ── 2. Check expiry ───────────────────────────────────────────────────────
    if user.verification_token_expires and datetime.now(timezone.utc) > user.verification_token_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link has expired. Please request a new one.",
        )

    # Already verified — idempotent (safe to call twice)
    if user.is_verified:
        return MessageResponse(message="Email is already verified. You can log in.")

    # ── 3. Mark as verified ───────────────────────────────────────────────────
    user.is_verified = True
    user.verification_token = None          # Burn the token — one use only
    user.verification_token_expires = None

    return MessageResponse(
        message="Email verified successfully! You can now log in.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# RESEND VERIFICATION
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend the verification email",
)
async def resend_verification(
    email: str = Query(...),
    request: Request = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    If the user lost or expired their first verification email.
    Rate-limit this endpoint in production (e.g., via slowapi).
    """
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    # Always return the same message — prevents email enumeration
    if not user or user.is_verified:
        return MessageResponse(
            message="If that address is registered and unverified, a new link is on its way."
        )

    # Issue a fresh token
    token = generate_verification_token()
    user.verification_token = token
    user.verification_token_expires = datetime.now(timezone.utc) + timedelta(
        hours=settings.verification_token_expire_hours
    )

    base_url = str(request.base_url).rstrip("/")
    background_tasks.add_task(
        send_verification_email,
        to_email=user.email,
        username=user.username,
        token=token,
        base_url=base_url,
    )

    return MessageResponse(
        message="If that address is registered and unverified, a new link is on its way."
    )


# ─────────────────────────────────────────────────────────────────────────────
# ME (protected)
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=UserOut,
    summary="Return the currently authenticated user's profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    """
    Simple profile endpoint. Frontend calls this on page load to confirm
    the stored JWT is still valid and to get fresh user data.
    """
    return UserOut.model_validate(current_user)
