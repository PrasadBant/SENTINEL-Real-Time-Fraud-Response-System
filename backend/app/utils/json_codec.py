"""
SENTINEL — JSON Codec Helpers
================================
Small, forgiving JSON encode/decode pair shared by everything that stores
a Python dict as a JSON blob in an external store (Postgres TEXT columns
via app/core/repository.py; Redis string values via
app/services/orchestrator.py's account cache) — one implementation
instead of two copies drifting apart.
"""

import json


def to_json(obj: dict) -> str:
    """Safely serialize a dict to a JSON string, skipping non-serialisable values."""
    try:
        return json.dumps(obj, default=str)
    except Exception:
        return "{}"


def from_json(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}
