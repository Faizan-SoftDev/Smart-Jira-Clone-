"""SQLAlchemy engine and request-scoped database session dependency."""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./smart_jira.db")
# Render Postgres exposes ``postgresql://`` URLs; SQLAlchemy needs its psycopg
# dialect name to use the installed psycopg 3 driver.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
_SQLITE_CONNECT_ARGS = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_SQLITE_CONNECT_ARGS)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    """Yield one session per request and always release its connection."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
