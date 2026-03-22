"""Initialize database schema (creates all tables)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.models import Base
from db.session import engine


def init_db() -> None:
    """Create all tables defined in models."""
    Base.metadata.create_all(engine)
    print("Database tables created successfully.")


if __name__ == "__main__":
    init_db()
