"""Sky Q MCP Server — Streamable HTTP transport.

Configuration is read entirely from environment variables (see settings.py).
Mutation tools (remote control, delete recording) are blocked unless
SKYQ_ALLOW_MUTATIONS=true is set.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from . import settings
from .client import get_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP application
# ---------------------------------------------------------------------------

app = Server("skyq-mcp-server")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, default=str, indent=2))]


def _err(message: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps({"error": message}, indent=2))]


def _mutation_blocked() -> list[types.TextContent]:
    return _err(
        "This tool modifies receiver state and is disabled. "
        "Set SKYQ_ALLOW_MUTATIONS=true to enable write operations."
    )


def _serialise(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialise(i) for i in obj]
    if hasattr(obj, "__dict__"):
        return {k: _serialise(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    return str(obj)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_READ_TOOLS: list[types.Tool] = [
    types.Tool(
        name="skyq_device_info",
        description=(
            "Return hardware and software information about the Sky Q receiver: "
            "model, firmware version, serial number, HDR/UHD capability, country."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="skyq_power_status",
        description="Return the power state of the Sky Q box: 'ON', 'STANDBY', or 'POWERED OFF'.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="skyq_current_state",
        description=(
            "Return the current transport state of the Sky Q box "
            "(e.g. PLAYING, PAUSED_PLAYBACK, STOPPED)."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="skyq_current_media",
        description=(
            "Return what the Sky Q box is currently playing: channel name, "
            "channel number, service ID (sid), and whether it is live TV or a recording."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="skyq_active_application",
        description="Return the app currently active on the Sky Q box (e.g. Netflix, YouTube).",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="skyq_epg",
        description=(
            "Fetch Electronic Programme Guide (EPG) data for a channel. "
            "Provide the Sky service ID (sid) — e.g. 2153 for BBC One South — "
            "and an optional start date and number of days."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sid": {
                    "type": "integer",
                    "description": "Sky service ID of the channel (e.g. 2153 for BBC One South)",
                },
                "date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (defaults to today UTC)",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days of EPG data to retrieve (default 2)",
                    "default": 2,
                },
            },
            "required": ["sid"],
        },
    ),
    types.Tool(
        name="skyq_programme_from_epg",
        description="Return details of a single EPG programme by service ID and programme UUID.",
        inputSchema={
            "type": "object",
            "properties": {
                "sid": {"type": "integer", "description": "Sky service ID of the channel"},
                "programme_uuid": {
                    "type": "string",
                    "description": "Programme UUID as returned by skyq_epg",
                },
            },
            "required": ["sid", "programme_uuid"],
        },
    ),
    types.Tool(
        name="skyq_current_live_programme",
        description=(
            "Return the programme currently on air on a given channel (by service ID). "
            "If sid is omitted, the currently tuned channel is used."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sid": {
                    "type": "integer",
                    "description": "Sky service ID (omit to use currently tuned channel)",
                },
            },
        },
    ),
    types.Tool(
        name="skyq_recordings",
        description="Return a paginated list of recordings stored on the Sky Q box.",
        inputSchema={
            "type": "object",
            "properties": {
                "offset": {"type": "integer", "description": "Pagination offset (default 0)", "default": 0},
                "limit": {"type": "integer", "description": "Max recordings to return (default 50)", "default": 50},
            },
        },
    ),
    types.Tool(
        name="skyq_recording",
        description="Return details of a specific recording by its PVR ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "pvrid": {"type": "string", "description": "PVR recording ID (e.g. 'P12345ABC')"},
            },
            "required": ["pvrid"],
        },
    ),
]

_MUTATION_TOOLS: list[types.Tool] = [
    types.Tool(
        name="skyq_press",
        description=(
            "⚠ Mutation — Send one or more remote-control key presses to the Sky Q box. "
            "Requires SKYQ_ALLOW_MUTATIONS=true. "
            "Keys: sky, power, tvguide, up, down, left, right, select, "
            "channelup, channeldown, play, pause, stop, rewind, fastforward, "
            "record, red, green, yellow, blue, 0–9, and more."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of key names to press",
                },
            },
            "required": ["keys"],
        },
    ),
    types.Tool(
        name="skyq_set_channel",
        description=(
            "⚠ Mutation — Tune the Sky Q box to a specific channel number. "
            "Requires SKYQ_ALLOW_MUTATIONS=true."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "channel_number": {
                    "type": "string",
                    "description": "Channel number as a string (e.g. '101' for BBC One)",
                },
            },
            "required": ["channel_number"],
        },
    ),
    types.Tool(
        name="skyq_delete_recording",
        description=(
            "⚠ Mutation — Permanently delete a recording from the Sky Q box. "
            "Requires SKYQ_ALLOW_MUTATIONS=true. There is no undo."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "pvrid": {"type": "string", "description": "PVR recording ID to delete"},
            },
            "required": ["pvrid"],
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return _READ_TOOLS + _MUTATION_TOOLS


# ---------------------------------------------------------------------------
# Tool call dispatcher
# ---------------------------------------------------------------------------


@app.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:

    # Guard mutation tools
    _mutation_names = {t.name for t in _MUTATION_TOOLS}
    if name in _mutation_names and not settings.SKYQ_ALLOW_MUTATIONS:
        return _mutation_blocked()

    try:
        client = get_client()
    except RuntimeError as exc:
        return _err(str(exc))

    try:
        # ── Read tools ────────────────────────────────────────────────────────
        if name == "skyq_device_info":
            info = client.get_device_information()
            return _ok(_serialise(info))

        if name == "skyq_power_status":
            return _ok({"power_status": client.power_status()})

        if name == "skyq_current_state":
            return _ok(_serialise(client.get_current_state()))

        if name == "skyq_current_media":
            return _ok(_serialise(client.get_current_media()))

        if name == "skyq_active_application":
            return _ok(_serialise(client.get_active_application()))

        if name == "skyq_epg":
            sid = arguments["sid"]
            days = arguments.get("days", 2)
            date_str = arguments.get("date")
            epg_date = (
                datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if date_str
                else datetime.now(timezone.utc)
            )
            return _ok(_serialise(client.get_epg_data(sid, epg_date, days)))

        if name == "skyq_programme_from_epg":
            return _ok(_serialise(client.get_programme_from_epg(arguments["sid"], arguments["programme_uuid"])))

        if name == "skyq_current_live_programme":
            sid = arguments.get("sid")
            if sid is None:
                media = client.get_current_media()
                sid = getattr(media, "sid", None)
                if not sid:
                    return _err("Cannot determine current channel SID. Supply 'sid' explicitly.")
            return _ok(_serialise(client.get_current_live_tv_programme(sid)))

        if name == "skyq_recordings":
            return _ok(_serialise(client.get_recordings(
                offset=arguments.get("offset", 0),
                limit=arguments.get("limit", 50),
            )))

        if name == "skyq_recording":
            return _ok(_serialise(client.get_recording(arguments["pvrid"])))

        # ── Mutation tools ────────────────────────────────────────────────────
        if name == "skyq_press":
            keys = arguments.get("keys", [])
            for key in keys:
                client.press(key)
            return _ok({"pressed": keys})

        if name == "skyq_set_channel":
            channel_number = str(arguments["channel_number"])
            for digit in channel_number:
                client.press(digit)
            return _ok({"tuned_to": channel_number})

        if name == "skyq_delete_recording":
            pvrid = arguments["pvrid"]
            result = client.delete_recording(pvrid)
            return _ok({"deleted": pvrid, "result": result})

        return _err(f"Unknown tool: {name}")

    except Exception as exc:
        logger.exception("Error executing tool '%s'", name)
        return _err(f"Tool '{name}' raised an exception: {exc}")


# ---------------------------------------------------------------------------
# Starlette ASGI application with /mcp endpoint
# ---------------------------------------------------------------------------


async def _health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "skyq-mcp-server", "host": settings.SKYQ_HOST})


def create_app() -> Starlette:
    session_manager = StreamableHTTPSessionManager(
        app=app,
        event_store=None,
        json_response=False,
        stateless=True,
    )

    async def handle_mcp(request: Request) -> Any:
        return await session_manager.handle_request(request)

    return Starlette(
        routes=[
            Route("/health", _health, methods=["GET"]),
            Mount("/mcp", app=session_manager.asgi_app),
        ]
    )
