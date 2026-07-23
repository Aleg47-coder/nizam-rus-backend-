"""
app/routers/users.py
──────────────────────
User profile management endpoints:

  GET   /api/users/me                 — Get my profile
  PATCH /api/users/me/language        — Update language preference
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_verified_user
from app.core.schemas import LanguagePreferenceUpdate, MessageResponse, UserOut
from app.models.user import User

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me", response_model=UserOut, summary="Get my profile")
async def get_profile(
    current_user: User = Depends(get_current_verified_user),
) -> UserOut:
    return UserOut.model_validate(current_user)


@router.patch(
    "/me/language",
    response_model=MessageResponse,
    summary="Save language preference to server",
)
async def update_language(
    body: LanguagePreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> MessageResponse:
    """
    Called whenever the user clicks a language toggle button.
    The frontend already switches the UI instantly; this just persists
    the choice so it's remembered on the next login / device.
    """
    current_user.language_preference = body.language
    return MessageResponse(message=f"Language preference updated to '{body.language}'")
