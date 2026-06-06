"""Runtime settings loaded from environment variables."""

from __future__ import annotations

import os


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes"}


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Sky Q connection
# ---------------------------------------------------------------------------

SKYQ_HOST: str = os.getenv("SKYQ_HOST", "")
SKYQ_PORT: int = _int("SKYQ_PORT", 49160)
SKYQ_JSON_PORT: int = _int("SKYQ_JSON_PORT", 9006)
SKYQ_EPG_CACHE_LEN: int = _int("SKYQ_EPG_CACHE_LEN", 20)

# ---------------------------------------------------------------------------
# Safety gate — write/mutation tools are disabled unless explicitly enabled
# ---------------------------------------------------------------------------

SKYQ_ALLOW_MUTATIONS: bool = _bool("SKYQ_ALLOW_MUTATIONS", False)

# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT: int = _int("SERVER_PORT", 8000)
