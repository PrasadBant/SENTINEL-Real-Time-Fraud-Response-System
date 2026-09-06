import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# Make `app.*` importable regardless of the CWD `alembic` is invoked from
# (mirrors the sys.path handling in backend/tests/conftest.py and
# backend/scripts/cleanup_db.py).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from app.core.database import Base  # noqa: E402
from app.core import db_models  # noqa: E402,F401  registers every model on Base.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# disable_existing_loggers=False is essential here, not optional: this
# runs every time run_migrations() does (app.core.database, called from
# main.py's lifespan on every startup, not just once at dev-time) —
# fileConfig's default (True) silently disables every logger that
# already exists and isn't explicitly listed in alembic.ini's [loggers]
# section (root/sqlalchemy/alembic only), which is every "sentinel.*"
# logger the app itself uses (see app/core/logging_config.py). Found via
# manual verification: a real POST /transaction's logger.info() calls
# were silently no-ops after the app started, traced to exactly this.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Autogenerate support: point Alembic at the real ORM metadata instead of
# hand-diffing schema changes.
target_metadata = Base.metadata

# DATABASE_URL env var wins over alembic.ini's placeholder — same default
# as app.core.database.DATABASE_URL, kept in sync deliberately so `alembic
# upgrade head` targets whatever DB the app itself would connect to.
db_url = os.getenv("DATABASE_URL", "sqlite:///./sentinel.db")
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
