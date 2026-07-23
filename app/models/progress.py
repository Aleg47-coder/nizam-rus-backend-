"""
app/models/progress.py
──────────────────────
SQLAlchemy ORM model for the `progress` table.

Schema design:
  One row per (user_id, day_number) pair.
  This is intentional — it's simple to query, add, and delete individual days.

  day_number:  1–180, maps directly to your DAYS_DATA[].day in the frontend.
  phase:       "a1" | "a2" | "b1" | "b2" — denormalised for fast filtering.
  completed:   bool — allows "attempted but failed" state in the future.
  completed_at: exact timestamp of when the user clicked "Mark complete".

  UniqueConstraint on (user_id, day_number) ensures we never double-count.
"""
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String,
    UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Progress(Base):
    __tablename__ = "progress"

    # One composite uniqueness constraint instead of a separate index
    __table_args__ = (
        UniqueConstraint("user_id", "day_number", name="uq_user_day"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Foreign key ───────────────────────────────────────────────────────────
    # ON DELETE CASCADE: if a user is deleted, their progress is deleted too.
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Day tracking ──────────────────────────────────────────────────────────
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase: Mapped[str] = mapped_column(String(5), nullable=False)   # "a1" | "a2" | "b1" | "b2"
    completed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationship back to User ─────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="progress_entries")   # noqa: F821

    def __repr__(self) -> str:
        return f"<Progress user={self.user_id} day={self.day_number} phase={self.phase}>"
