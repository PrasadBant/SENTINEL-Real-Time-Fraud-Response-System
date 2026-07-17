"""
SENTINEL — SQLAlchemy Database Setup
=====================================
Creates a SQLite database (sentinel.db) in the backend directory.
Switchable to PostgreSQL by changing DATABASE_URL in the environment.

Usage:
    from app.core.database import engine, SessionLocal, Base, init_db
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Allow override via environment variable for PostgreSQL in production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sentinel.db")

# SQLite-specific: allow same-thread usage (needed for FastAPI sync routes)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,  # Set True to log all SQL statements for debugging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that provides a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables defined in db_models. Safe to call on every startup."""
    # Import here to ensure all models are registered with Base before create_all
    from app.core import db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    print("  [Database] SQLite DB initialized  (sentinel.db)")
