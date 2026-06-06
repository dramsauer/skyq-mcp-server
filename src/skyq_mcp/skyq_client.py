"""Manages connections to one or more Sky Q receivers."""

from __future__ import annotations

import logging
from typing import Any

from pyskyqremote.skyq_remote import SkyQRemote

logger = logging.getLogger(__name__)


class SkyQClientManager:
    """Thread-safe registry of SkyQRemote clients keyed by host address."""

    def __init__(self) -> None:
        self._clients: dict[str, SkyQRemote] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(
        self,
        host: str,
        port: int = 49160,
        json_port: int = 9006,
        epg_cache_len: int = 20,
    ) -> dict[str, Any]:
        """Create and register a SkyQRemote client.

        Returns a dict of basic device information so the caller can
        confirm the connection was successful.
        """
        client = SkyQRemote(
            host,
            port=port,
            json_port=json_port,
            epg_cache_len=epg_cache_len,
        )

        # Probe the device immediately to validate connectivity.
        try:
            device_info = client.get_device_information()
        except Exception as exc:
            raise ConnectionError(
                f"Connected to {host} but failed to retrieve device information: {exc}"
            ) from exc

        self._clients[host] = client
        logger.info("Registered Sky Q receiver at %s", host)

        # Flatten to a plain dict for the caller.
        if hasattr(device_info, "__dict__"):
            return {k: v for k, v in device_info.__dict__.items() if not k.startswith("_")}
        return {}

    def disconnect(self, host: str) -> None:
        """Remove a client from the registry (no network call needed)."""
        self._clients.pop(host, None)
        logger.info("Removed Sky Q receiver at %s", host)

    def get(self, host: str) -> SkyQRemote | None:
        """Return the SkyQRemote client for *host*, or None if not registered."""
        return self._clients.get(host)

    def list_devices(self) -> list[dict[str, str]]:
        """Return a list of all registered device hosts."""
        return [{"host": h} for h in self._clients]
