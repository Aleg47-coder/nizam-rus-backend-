"""
Importing models here guarantees SQLAlchemy registers them with Base.metadata
before Alembic or create_all_tables() runs. Never remove these imports.
"""
from app.models.user import User        # noqa: F401
from app.models.progress import Progress  # noqa: F401
