"""
SENTINEL — SQLAlchemy Database Setup
=====================================
Defaults to a local SQLite file (sentinel.db) in the backend directory;
set DATABASE_URL to point at Postgres instead (see docker-compose.yml /
.env.example) — that's the real deployment target from Phase 0 on.

Usage:
    from app.core.database import engine, SessionLocal, Base, run_migrations
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

# backend/app/core/database.py -> backend/app/core -> backend/app -> backend
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_db():
    """FastAPI dependency that provides a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Run Alembic migrations up to head. Replaces the old create_all()-based
    init_db(): schema is now defined by alembic/versions/*, not inferred
    from whatever the current ORM models happen to look like — so a
    schema change without a matching migration is caught here (Alembic
    errors) instead of silently working via create_all()'s "only create
    what's missing, never alter existing tables" behavior."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(_BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "alembic"))
    command.upgrade(cfg, "head")
    print(f"  [Database] Migrations applied (alembic upgrade head) — {DATABASE_URL}")
