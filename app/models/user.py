"""
app/models/user.py
──────────────────
SQLAlchemy ORM model for the `users` table.

Design decisions:
  - Mapped[type] annotations give full type-checker support (SQLAlchemy 2.0 style).
  - created_at / updated_at are server-side defaults — the DB sets them, not Python.
  - verification_token is nullable — cleared after the user verifies their email.
  - language_preference persists the user's last-used UI language across sessions.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Identity ──────────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(80), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Email verification ────────────────────────────────────────────────────
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verification_token: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )
    verification_token_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Account state ─────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── User preferences ──────────────────────────────────────────────────────
    # "az" | "ru" | "en" — matches the language keys in the frontend i18n dict
    language_preference: Mapped[str] = mapped_column(
        String(5), default="az", nullable=False
    )
    # ISO date string e.g. "2024-01-15" — when the user started their 180-day run
    start_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    # server_default=func.now() means the DATABASE sets this, not SQLAlchemy.
    # onupdate=func.now() auto-updates updated_at on every row change.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    # "lazy='selectin'" means progress rows are loaded in a single extra SELECT,
    # not N+1 queries. Works correctly with async sessions.
    progress_entries: Mapped[list["Progress"]] = relationship(    # noqa: F821
        "Progress", back_populates="user", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} verified={self.is_verified}>"
