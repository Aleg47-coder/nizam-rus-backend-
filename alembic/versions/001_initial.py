"""initial schema — users and progress tables

Revision ID: 001_initial
Revises: (none — this is the first migration)
Create Date: 2024-01-01 00:00:00.000000

This migration is auto-generated from the ORM models.
Running `alembic revision --autogenerate -m "initial schema"` would produce
something equivalent to this. Provided here so you can start with a working
migration history without running autogenerate first.

Apply: alembic upgrade head
Revert: alembic downgrade base
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# ── Alembic metadata ──────────────────────────────────────────────────────────
revision: str = "001_initial"
down_revision: Union[str, None] = None   # No parent — this is the base
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the users and progress tables from scratch."""

    # ── users table ───────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        # Identity
        sa.Column("email",    sa.String(255), nullable=False),
        sa.Column("username", sa.String(80),  nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),

        # Email verification
        sa.Column("is_verified",                sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("verification_token",         sa.String(128), nullable=True),
        sa.Column("verification_token_expires", sa.DateTime(timezone=True), nullable=True),

        # Account state
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),

        # Preferences
        sa.Column("language_preference", sa.String(5),  nullable=False, server_default="az"),
        sa.Column("start_date",          sa.String(10), nullable=True),

        # Timestamps — server_default means the DB sets these, not Python
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Unique indexes on email and username (enforces uniqueness at DB level)
    op.create_index("ix_users_email",    "users", ["email"],    unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    # Index on verification_token for fast lookup during email verification
    op.create_index("ix_users_verification_token", "users", ["verification_token"], unique=False)

    # ── progress table ────────────────────────────────────────────────────────
    op.create_table(
        "progress",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),

        # Foreign key — CASCADE means deleting a user wipes their progress
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # Day tracking (1–180)
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("phase",      sa.String(5), nullable=False),   # "a1"|"a2"|"b1"|"b2"
        sa.Column("completed",  sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Index on user_id for fast per-user queries
    op.create_index("ix_progress_user_id", "progress", ["user_id"], unique=False)

    # UNIQUE constraint on (user_id, day_number) — no double-counting
    op.create_unique_constraint("uq_user_day", "progress", ["user_id", "day_number"])


def downgrade() -> None:
    """Drop both tables — rolls back this migration completely."""
    op.drop_table("progress")
    op.drop_table("users")
