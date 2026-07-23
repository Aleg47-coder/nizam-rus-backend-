"""
app/routers/progress.py
────────────────────────
Progress tracking endpoints (all require a verified JWT):

  POST  /api/progress/update     — Toggle one day complete/incomplete
  POST  /api/progress/bulk       — Sync many days at once (localStorage migration)
  GET   /api/progress/me         — Fetch full progress for the frontend
  PATCH /api/progress/start-date — Set / update the user's 180-day start date
  DELETE /api/progress/reset     — Nuclear option: delete all progress for this user
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.database import get_db
from app.core.dependencies import get_current_verified_user
from app.core.schemas import (
    BulkProgressRequest,
    MessageResponse,
    ProgressEntry,
    ProgressResponse,
    UpdateProgressRequest,
)
from app.models.progress import Progress
from app.models.user import User

router = APIRouter(prefix="/api/progress", tags=["Progress"])


# ─────────────────────────────────────────────────────────────────────────────
# TOGGLE ONE DAY
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/update",
    response_model=ProgressEntry,
    summary="Mark a day complete or incomplete (toggle)",
)
async def update_progress(
    body: UpdateProgressRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> ProgressEntry:
    """
    Toggle behaviour mirrors the frontend's localStorage toggleComplete():
      - If the row doesn't exist → create it as completed=True.
      - If the row exists and completed=True → set completed=False (un-mark).
      - If the row exists and completed=False → set completed=True (re-mark).

    This endpoint is called every time the user clicks "Mark complete" on a day card.
    """
    # Find existing progress row for this user + day
    result = await db.execute(
        select(Progress).where(
            Progress.user_id == current_user.id,
            Progress.day_number == body.day_number,
        )
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        # First time completing this day — create the row
        entry = Progress(
            user_id=current_user.id,
            day_number=body.day_number,
            phase=body.phase,
            completed=body.completed,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        await db.flush()   # Get the ID before commit
    else:
        # Toggle: flip the completed flag (or honour the explicit body.completed value)
        existing.completed = body.completed
        if body.completed:
            existing.completed_at = datetime.now(timezone.utc)   # Update timestamp on re-completion
        entry = existing

    return ProgressEntry.model_validate(entry)


# ─────────────────────────────────────────────────────────────────────────────
# BULK SYNC (localStorage → Server migration)
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/bulk",
    response_model=MessageResponse,
    summary="Sync many days at once — useful when migrating from localStorage",
)
async def bulk_update_progress(
    body: BulkProgressRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> MessageResponse:
    """
    Called once on first login if the user has existing localStorage data.
    Uses SQLite's INSERT OR REPLACE (upsert) to avoid duplicates.

    Frontend flow:
      1. User logs in for the first time on a device.
      2. Frontend reads localStorage completed dict.
      3. If it has entries, POSTs them here as a bulk sync.
      4. From then on, every toggle calls /update instead.
    """
    if not body.entries:
        return MessageResponse(message="No entries to sync.")

    # Build upsert-ready dicts for all entries
    now = datetime.now(timezone.utc)
    rows = [
        {
            "user_id": current_user.id,
            "day_number": entry.day_number,
            "phase": entry.phase,
            "completed": entry.completed,
            "completed_at": now,
        }
        for entry in body.entries
    ]

    # SQLite upsert: INSERT OR REPLACE honours the UniqueConstraint(user_id, day_number)
    # For PostgreSQL, swap to: insert(...).on_conflict_do_update(...)
    stmt = sqlite_insert(Progress).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "day_number"],
        set_={
            "completed": stmt.excluded.completed,
            "completed_at": stmt.excluded.completed_at,
        },
    )
    await db.execute(stmt)

    return MessageResponse(
        message=f"Synced {len(rows)} progress entries successfully.",
        detail=f"User {current_user.id} | {len(rows)} rows upserted",
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET MY PROGRESS
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/me",
    response_model=ProgressResponse,
    summary="Fetch full progress for the authenticated user",
)
async def get_my_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> ProgressResponse:
    """
    Returns the completed_days dict the frontend already uses:
      { "1": true, "5": true, "23": true, ... }

    The frontend replaces its in-memory `completed` object with this on login,
    so the UI instantly reflects the user's real progress across all devices.
    """
    result = await db.execute(
        select(Progress).where(Progress.user_id == current_user.id)
    )
    entries = result.scalars().all()

    # Build the dict the frontend expects: string keys, bool values
    completed_days = {str(e.day_number): e.completed for e in entries}
    total = sum(1 for v in completed_days.values() if v)

    return ProgressResponse(
        completed_days=completed_days,
        total_completed=total,
        start_date=current_user.start_date,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SET START DATE
# ─────────────────────────────────────────────────────────────────────────────
@router.patch(
    "/start-date",
    response_model=MessageResponse,
    summary="Set or update the user's 180-day program start date",
)
async def set_start_date(
    start_date: str,   # ISO format: "2024-01-15"
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> MessageResponse:
    """
    Called when the user first launches the app (or resets their program).
    Mirrors the localStorage.setItem('nizam_rus_startDate', date) call.
    """
    try:
        datetime.strptime(start_date, "%Y-%m-%d")   # Validate format
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be in YYYY-MM-DD format",
        )
    current_user.start_date = start_date
    return MessageResponse(message=f"Start date set to {start_date}")


# ─────────────────────────────────────────────────────────────────────────────
# RESET ALL PROGRESS
# ─────────────────────────────────────────────────────────────────────────────
@router.delete(
    "/reset",
    response_model=MessageResponse,
    summary="Delete ALL progress for the authenticated user",
    status_code=status.HTTP_200_OK,
)
async def reset_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_verified_user),
) -> MessageResponse:
    """
    Nuclear option — mirrors the "Reset Progress" button in the frontend.
    Also clears the start_date so the 180-day timer resets.
    """
    await db.execute(delete(Progress).where(Progress.user_id == current_user.id))
    current_user.start_date = None
    return MessageResponse(message="All progress has been reset.")
