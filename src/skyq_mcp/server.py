"""Sky Q MCP Server implementation using the MCP SDK and pyskyqremote."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

from .skyq_client import SkyQClientManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

app = Server("skyq-mcp-server")
_clients = SkyQClientManager()


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _ok(data: Any) -> list[types.TextContent]:
    """Wrap a result as a JSON text content block."""
    return [types.TextContent(type="text", text=json.dumps(data, default=str, indent=2))]


def _err(message: str) -> list[types.TextContent]:
    """Wrap an error as a JSON text content block."""
    return [types.TextContent(type="text", text=json.dumps({"error": message}, indent=2))]


def _require_host(args: dict) -> tuple[str | None, list[types.TextContent] | None]:
    host = args.get("host")
    if not host:
        return None, _err("'host' parameter is required")
    return host, None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[types.Tool] = [
    # ── Connection management ───────────────────────────────────────────────
    types.Tool(
        name="skyq_connect",
        description=(
            "Register a Sky Q receiver by its IP address so it can be used by "
            "other tools.  Returns basic device information on success."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "IP address or hostname of the Sky Q box (e.g. '192.168.1.99')",
                },
                "port": {
                    "type": "integer",
                    "description": "Control port (default 49160)",
                    "default": 49160,
                },
                "json_port": {
                    "type": "integer",
                    "description": "JSON API port (default 9006)",
                    "default": 9006,
                },
                "epg_cache_len": {
                    "type": "integer",
                    "description": "Number of EPG entries to cache (default 20)",
                    "default": 20,
                },
            },
            "required": ["host"],
        },
    ),
    types.Tool(
        name="skyq_list_devices",
        description="List all currently registered Sky Q receivers.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="skyq_disconnect",
        description="Remove a previously registered Sky Q receiver.",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box to remove"},
            },
            "required": ["host"],
        },
    ),

    # ── Device info & status ────────────────────────────────────────────────
    types.Tool(
        name="skyq_get_device_info",
        description="Return hardware and software information about a Sky Q receiver.",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
            },
            "required": ["host"],
        },
    ),
    types.Tool(
        name="skyq_power_status",
        description="Return the power state of the Sky Q box: 'ON', 'STANDBY', or 'POWERED OFF'.",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
            },
            "required": ["host"],
        },
    ),
    types.Tool(
        name="skyq_get_current_state",
        description=(
            "Return the current transport state of the Sky Q box "
            "(e.g. PLAYING, PAUSED_PLAYBACK, STOPPED)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
            },
            "required": ["host"],
        },
    ),

    # ── Media & channels ────────────────────────────────────────────────────
    types.Tool(
        name="skyq_get_current_media",
        description=(
            "Return information about what the Sky Q box is currently playing: "
            "channel name, channel number, service ID, and whether it is a live "
            "broadcast or a recording (PVR)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
            },
            "required": ["host"],
        },
    ),
    types.Tool(
        name="skyq_get_active_application",
        description="Return the app currently running on the Sky Q box (e.g. Netflix, YouTube).",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
            },
            "required": ["host"],
        },
    ),

    # ── EPG ─────────────────────────────────────────────────────────────────
    types.Tool(
        name="skyq_get_epg",
        description=(
            "Fetch Electronic Programme Guide (EPG) data for a channel identified by "
            "its Sky service ID (sid).  Returns a list of programmes for the "
            "specified date and number of days."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
                "sid": {
                    "type": "integer",
                    "description": "Sky service ID of the channel (e.g. 2153 for BBC One South)",
                },
                "date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format (defaults to today)",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of days of EPG data to retrieve (default 2)",
                    "default": 2,
                },
            },
            "required": ["host", "sid"],
        },
    ),
    types.Tool(
        name="skyq_get_programme_from_epg",
        description=(
            "Fetch details for a single programme from the EPG by service ID and "
            "UTC programme UUID or by start time."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
                "sid": {"type": "integer", "description": "Sky service ID of the channel"},
                "programme_uuid": {
                    "type": "string",
                    "description": "Programme UUID as returned by get_epg",
                },
            },
            "required": ["host", "sid", "programme_uuid"],
        },
    ),
    types.Tool(
        name="skyq_get_current_live_tv_programme",
        description=(
            "Return the programme currently broadcasting on the channel the Sky Q "
            "box is tuned to, including title, synopsis, start/end times."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
                "sid": {
                    "type": "integer",
                    "description": (
                        "Sky service ID of the channel.  If omitted, the currently "
                        "tuned channel is used."
                    ),
                },
            },
            "required": ["host"],
        },
    ),

    # ── Recordings (PVR) ────────────────────────────────────────────────────
    types.Tool(
        name="skyq_get_recordings",
        description="Return a list of recordings stored on the Sky Q box.",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
                "offset": {
                    "type": "integer",
                    "description": "Pagination offset (default 0)",
                    "default": 0,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of recordings to return (default 50)",
                    "default": 50,
                },
            },
            "required": ["host"],
        },
    ),
    types.Tool(
        name="skyq_get_recording",
        description="Return details of a specific recording by its PVR ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
                "pvrid": {"type": "string", "description": "PVR recording ID (e.g. 'P12345ABC')"},
            },
            "required": ["host", "pvrid"],
        },
    ),
    types.Tool(
        name="skyq_delete_recording",
        description="Delete a recording from the Sky Q box by its PVR ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
                "pvrid": {"type": "string", "description": "PVR recording ID to delete"},
            },
            "required": ["host", "pvrid"],
        },
    ),

    # ── Remote control ──────────────────────────────────────────────────────
    types.Tool(
        name="skyq_press",
        description=(
            "Send one or more remote-control key presses to the Sky Q box.  "
            "Keys include: sky, power, tvguide, boxoffice, services, interactive, "
            "search, sidebar, backup, help, up, down, left, right, select, "
            "channelup, channeldown, i, text, rewind, play, fastforward, stop, "
            "pause, record, red, green, yellow, blue, 0-9."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of key names to press",
                },
            },
            "required": ["host", "keys"],
        },
    ),
    types.Tool(
        name="skyq_set_channel",
        description="Tune the Sky Q box to a specific channel number.",
        inputSchema={
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "IP address of the Sky Q box"},
                "channel_number": {
                    "type": "string",
                    "description": "Channel number as a string (e.g. '101' for BBC One)",
                },
            },
            "required": ["host", "channel_number"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool list handler
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


# ---------------------------------------------------------------------------
# Tool call dispatcher
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:

    # ── Connection management ────────────────────────────────────────────────
    if name == "skyq_connect":
        host = arguments.get("host")
        if not host:
            return _err("'host' is required")
        try:
            info = _clients.connect(
                host=host,
                port=arguments.get("port", 49160),
                json_port=arguments.get("json_port", 9006),
                epg_cache_len=arguments.get("epg_cache_len", 20),
            )
            return _ok({"status": "connected", "host": host, "device": info})
        except Exception as exc:
            return _err(f"Failed to connect to {host}: {exc}")

    if name == "skyq_list_devices":
        return _ok(_clients.list_devices())

    if name == "skyq_disconnect":
        host, err = _require_host(arguments)
        if err:
            return err
        _clients.disconnect(host)
        return _ok({"status": "disconnected", "host": host})

    # ── All remaining tools require a registered client ──────────────────────
    host, err = _require_host(arguments)
    if err:
        return err

    client = _clients.get(host)
    if client is None:
        return _err(
            f"No Sky Q receiver registered for host '{host}'. "
            "Call skyq_connect first."
        )

    try:
        # ── Device info & status ─────────────────────────────────────────────
        if name == "skyq_get_device_info":
            info = client.get_device_information()
            return _ok(info.__dict__ if hasattr(info, "__dict__") else info)

        if name == "skyq_power_status":
            return _ok({"power_status": client.power_status()})

        if name == "skyq_get_current_state":
            state = client.get_current_state()
            return _ok(state.__dict__ if hasattr(state, "__dict__") else state)

        # ── Media & channels ─────────────────────────────────────────────────
        if name == "skyq_get_current_media":
            media = client.get_current_media()
            return _ok(media.__dict__ if hasattr(media, "__dict__") else media)

        if name == "skyq_get_active_application":
            app_info = client.get_active_application()
            return _ok(app_info.__dict__ if hasattr(app_info, "__dict__") else app_info)

        # ── EPG ──────────────────────────────────────────────────────────────
        if name == "skyq_get_epg":
            sid = arguments["sid"]
            days = arguments.get("days", 2)
            date_str = arguments.get("date")
            epg_date = (
                datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if date_str
                else datetime.now(timezone.utc)
            )
            epg = client.get_epg_data(sid, epg_date, days)
            # Serialise nested dataclass / objects
            result = _serialise(epg)
            return _ok(result)

        if name == "skyq_get_programme_from_epg":
            sid = arguments["sid"]
            uuid = arguments["programme_uuid"]
            prog = client.get_programme_from_epg(sid, uuid)
            return _ok(_serialise(prog))

        if name == "skyq_get_current_live_tv_programme":
            sid = arguments.get("sid")
            if sid is None:
                # derive sid from current media
                media = client.get_current_media()
                sid = getattr(media, "sid", None)
                if not sid:
                    return _err("Could not determine current channel SID; supply 'sid' explicitly.")
            prog = client.get_current_live_tv_programme(sid)
            return _ok(_serialise(prog))

        # ── Recordings ───────────────────────────────────────────────────────
        if name == "skyq_get_recordings":
            offset = arguments.get("offset", 0)
            limit = arguments.get("limit", 50)
            recordings = client.get_recordings(offset=offset, limit=limit)
            return _ok(_serialise(recordings))

        if name == "skyq_get_recording":
            pvrid = arguments["pvrid"]
            recording = client.get_recording(pvrid)
            return _ok(_serialise(recording))

        if name == "skyq_delete_recording":
            pvrid = arguments["pvrid"]
            result = client.delete_recording(pvrid)
            return _ok({"deleted": pvrid, "result": result})

        # ── Remote control ───────────────────────────────────────────────────
        if name == "skyq_press":
            keys = arguments.get("keys", [])
            for key in keys:
                client.press(key)
            return _ok({"pressed": keys})

        if name == "skyq_set_channel":
            channel_number = str(arguments["channel_number"])
            # Send each digit as a key press, then 'select'
            for digit in channel_number:
                client.press(digit)
            return _ok({"tuned_to": channel_number})

        return _err(f"Unknown tool: {name}")

    except Exception as exc:
        logger.exception("Error executing tool %s", name)
        return _err(f"Tool '{name}' raised an exception: {exc}")


# ---------------------------------------------------------------------------
# Object serialisation helper
# ---------------------------------------------------------------------------

def _serialise(obj: Any) -> Any:
    """Recursively convert pyskyqremote objects to plain dicts / lists."""
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
# Entry-point
# ---------------------------------------------------------------------------

async def run() -> None:
    """Start the MCP server on stdio."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="skyq-mcp-server",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )
