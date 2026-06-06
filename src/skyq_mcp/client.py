"""Thin wrapper around pyskyqremote.SkyQRemote."""

from __future__ import annotations

import logging

from pyskyqremote.skyq_remote import SkyQRemote

from . import settings

logger = logging.getLogger(__name__)

_client: SkyQRemote | None = None


def get_client() -> SkyQRemote:
    """Return a module-level SkyQRemote instance, creating it on first call."""
    global _client
    if _client is None:
        if not settings.SKYQ_HOST:
            raise RuntimeError(
                "SKYQ_HOST is not configured. Set it in .env before starting the server."
            )
        logger.info(
            "Connecting to Sky Q box at %s (port %s)", settings.SKYQ_HOST, settings.SKYQ_PORT
        )
        _client = SkyQRemote(
            settings.SKYQ_HOST,
            port=settings.SKYQ_PORT,
            json_port=settings.SKYQ_JSON_PORT,
            epg_cache_len=settings.SKYQ_EPG_CACHE_LEN,
        )
    return _client
