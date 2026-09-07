"""SQLite database connection and session management using SQLAlchemy 2.0."""

import os
from collections.abc import Generator
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.config import settings

# Ensure data directory exists
db_url = settings.database_url
if db_url.startswith("sqlite:///./"):
    db_relative_path = db_url.replace("sqlite:///./", "")
    db_file = Path(__file__).resolve().parent.parent.parent / db_relative_path
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine_url = f"sqlite:///{db_file}"
else:
    engine_url = db_url

# Create SQLite engine with WAL mode for fast concurrent reads/writes
engine = create_engine(
    engine_url,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=settings.debug,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable SQLite WAL journal mode and foreign keys for speed and reliability."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy database models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize all tables defined in models."""
    import src.db.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
