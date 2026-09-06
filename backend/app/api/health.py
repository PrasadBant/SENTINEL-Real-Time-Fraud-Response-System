"""
SENTINEL — Health Check
===========================
Phase 2: actually checks Postgres and Redis connectivity instead of
always returning 200 "the process is up" regardless of whether either
dependency is reachable — the old version would report healthy even
while every request was failing behind it. Returns 503 (not 200) when
either check fails, so container orchestration / uptime monitoring can
tell the difference, matching the postgres/redis services' own
healthchecks in docker-compose.yml.
"""

import logging

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.core import redis_client
from app.core.database import SessionLocal

logger = logging.getLogger("sentinel.health")

router = APIRouter()


def _check_postgres() -> bool:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("Health check: Postgres unreachable: %s", e)
        return False
    finally:
        db.close()


def _check_redis() -> bool:
    try:
        return bool(redis_client.get_redis().ping())
    except Exception as e:
        logger.warning("Health check: Redis unreachable: %s", e)
        return False


@router.get("/health")
def health_check(response: Response) -> dict[str, str]:
    postgres_ok = _check_postgres()
    redis_ok = _check_redis()
    healthy = postgres_ok and redis_ok

    response.status_code = 200 if healthy else 503
    return {
        "status": "ok" if healthy else "unhealthy",
        "postgres": "ok" if postgres_ok else "unreachable",
        "redis": "ok" if redis_ok else "unreachable",
    }
