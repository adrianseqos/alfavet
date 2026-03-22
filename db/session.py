"""Database session management."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import DATABASE_URL, DB_ECHO

engine = create_engine(DATABASE_URL, echo=DB_ECHO, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    """Create a new database session."""
    return SessionLocal()
