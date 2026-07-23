"""add exam_history table

Revision ID: 002_exam_history
Revises: 001_initial
Create Date: 2024-06-01 00:00:00.000000

This migration shows the pattern for adding NEW tables after the initial deploy.
It also demonstrates how to add a column to an existing table with a server_default
so it doesn't require a full table rewrite (critical for large tables in production).

Apply:  alembic upgrade head
Revert: alembic downgrade 001_initial
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_exam_history"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add an exam_history table to persist quiz/exam results server-side.
    These are currently stored only in localStorage (examHistory key).
    Moving them to the server lets users see their exam history on any device.
    """

    # ── New table: exam_history ───────────────────────────────────────────────
    op.create_table(
        "exam_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Matches the examId strings in the frontend EXAMS array
        # e.g. "exam-a1", "exam-a2", "exam-b1", "exam-b2"
        sa.Column("exam_id",    sa.String(20),  nullable=False),
        sa.Column("score",      sa.Integer(),   nullable=False),   # Correct answers
        sa.Column("total",      sa.Integer(),   nullable=False),   # Total questions
        sa.Column("percentage", sa.Float(),     nullable=False),   # score/total * 100
        sa.Column("passed",     sa.Boolean(),   nullable=False),   # pct >= 70
        sa.Column("taken_at",   sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── New column on users: timezone ────────────────────────────────────────
    # Adding a column with server_default is safe even on large tables:
    # - SQLite: rewrites the table (acceptable for dev/small prod)
    # - PostgreSQL: adds the column with DEFAULT instantly (no rewrite needed)
    op.add_column(
        "users",
        sa.Column(
            "timezone",
            sa.String(50),
            nullable=False,
            server_default="Asia/Baku",   # Default to Baku timezone for NIZAM-RUS users
        ),
    )


def downgrade() -> None:
    """Roll back: drop exam_history and remove timezone column."""
    op.drop_table("exam_history")
    op.drop_column("users", "timezone")


# ─────────────────────────────────────────────────────────────────────────────
# HOW TO CREATE YOUR OWN MIGRATIONS
# ─────────────────────────────────────────────────────────────────────────────
#
# After changing any SQLAlchemy model in app/models/:
#
#   # Auto-detect what changed and generate a migration file:
#   alembic revision --autogenerate -m "describe what you changed"
#
#   # Review the generated file in alembic/versions/ before applying!
#   # Autogenerate is good but not perfect — always review.
#
#   # Apply to the DB:
#   alembic upgrade head
#
#   # Check current migration state:
#   alembic current
#
#   # See full migration history:
#   alembic history --verbose
#
# ─────────────────────────────────────────────────────────────────────────────
# POSTGRESQL MIGRATION NOTE
# ─────────────────────────────────────────────────────────────────────────────
#
# When you switch from SQLite → PostgreSQL in production:
#
#   1. Change DATABASE_URL in .env:
#      DATABASE_URL=postgresql+asyncpg://nizamuser:password@localhost:5432/nizam_rus
#
#   2. Install the async postgres driver:
#      pip install asyncpg
#
#   3. Create the database:
#      sudo -u postgres psql -c "CREATE DATABASE nizam_rus;"
#      sudo -u postgres psql -c "CREATE USER nizamuser WITH PASSWORD 'password';"
#      sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE nizam_rus TO nizamuser;"
#
#   4. Run all migrations against the new DB:
#      alembic upgrade head
#
#   5. (Optional) Migrate existing data with pg_dump/COPY or a script.
#
#   No Python code needs to change — the ORM is fully database-agnostic.
# ─────────────────────────────────────────────────────────────────────────────
