# Sky Q MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that exposes your **Sky Q satellite receiver** to AI assistants such as Claude.  
It wraps the excellent [`pyskyqremote`](https://github.com/RogerSelwyn/skyq_remote) library by Roger Selwyn.

---

## Features

| Category | What you can do |
|---|---|
| **Connection** | Register / unregister multiple Sky Q boxes by IP |
| **Device info** | Hardware model, firmware version, HDR/UHD capability, country |
| **Status** | Power state, transport state (PLAYING / PAUSED / STOPPED) |
| **Media** | Currently playing channel, channel number, live vs. recording |
| **Applications** | Which app is active (Netflix, YouTube, …) |
| **EPG** | Full programme guide for any channel and date range |
| **Recordings** | List, inspect, and delete PVR recordings |
| **Remote control** | Send any key press; tune to a channel by number |

---

## Requirements

- Python 3.11+
- A Sky Q box on your local network with the REST/JSON API accessible  
  (standard on all modern Sky Q hardware; UK, Italy, Germany supported)
- [`pyskyqremote`](https://pypi.org/project/pyskyqremote/) ≥ 0.3.8
- [`mcp`](https://pypi.org/project/mcp/) ≥ 1.0.0

> **Note:** `pyskyqremote` is no longer actively maintained by its author (no Sky Q hardware available for testing), but the library remains functional against current Sky Q firmware.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/skyq-mcp-server.git
cd skyq-mcp-server

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .

# For development (tests, linting)
pip install -e ".[dev]"
```

---

## Running the server

The server communicates over **stdio** (standard MCP transport):

```bash
python -m skyq_mcp
```

Or via the installed script:

```bash
skyq-mcp-server
```

---

## Connecting to an MCP client

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "skyq": {
      "command": "python",
      "args": ["-m", "skyq_mcp"],
      "cwd": "/path/to/skyq-mcp-server"
    }
  }
}
```

### Claude Code CLI

```bash
claude mcp add skyq -- python -m skyq_mcp
```

---

## Tool Reference

### Connection management

| Tool | Description |
|---|---|
| `skyq_connect` | Register a Sky Q box by IP. Call this first. |
| `skyq_list_devices` | List all registered boxes. |
| `skyq_disconnect` | Remove a registered box. |

**`skyq_connect` parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | string | required | IP address of the Sky Q box |
| `port` | integer | 49160 | Control port |
| `json_port` | integer | 9006 | JSON API port |
| `epg_cache_len` | integer | 20 | EPG cache size |

---

### Device & status

| Tool | Description |
|---|---|
| `skyq_get_device_info` | Hardware/software details |
| `skyq_power_status` | "ON", "STANDBY", or "POWERED OFF" |
| `skyq_get_current_state` | Transport state (PLAYING, PAUSED_PLAYBACK, STOPPED …) |

---

### Media & channels

| Tool | Description |
|---|---|
| `skyq_get_current_media` | Currently tuned channel or active recording PVR ID |
| `skyq_get_active_application` | App ID and title of the running application |

---

### EPG (Electronic Programme Guide)

| Tool | Parameters | Description |
|---|---|---|
| `skyq_get_epg` | `host`, `sid`, `date` (YYYY-MM-DD), `days` | EPG data for a channel |
| `skyq_get_programme_from_epg` | `host`, `sid`, `programme_uuid` | Single programme details |
| `skyq_get_current_live_tv_programme` | `host`, `sid` (optional) | Programme on air right now |

The **service ID** (`sid`) identifies a channel in the Sky EPG — e.g. `2153` for BBC One South, `1143` for Sky Comedy HD.  
You can discover the current channel's SID with `skyq_get_current_media`.

---

### Recordings (PVR)

| Tool | Parameters | Description |
|---|---|---|
| `skyq_get_recordings` | `host`, `offset`, `limit` | Paginated list of recordings |
| `skyq_get_recording` | `host`, `pvrid` | Details of one recording |
| `skyq_delete_recording` | `host`, `pvrid` | Delete a recording |

---

### Remote control

| Tool | Parameters | Description |
|---|---|---|
| `skyq_press` | `host`, `keys` (array) | Send key presses |
| `skyq_set_channel` | `host`, `channel_number` | Tune to a channel |

**Supported key names for `skyq_press`:**

```
sky  power  tvguide  boxoffice  services  interactive  search  sidebar
backup  help  up  down  left  right  select  channelup  channeldown
i  text  rewind  play  fastforward  stop  pause  record
red  green  yellow  blue  0  1  2  3  4  5  6  7  8  9
```

---

## Example conversation

```
You: Connect to my Sky Q box at 192.168.1.99
Claude: [calls skyq_connect with host=192.168.1.99]
        Connected. Falcon / ES240, firmware 32B12D, HDR & UHD capable.

You: What's on BBC One right now?
Claude: [calls skyq_get_current_live_tv_programme with sid=2153]
        "EastEnders" — 19:30–20:00. Drama set in the East End of London.

You: Show me tonight's BBC One schedule
Claude: [calls skyq_get_epg with sid=2153, date=today, days=1]
        19:30  EastEnders
        20:00  The One Show
        ...

You: What recordings do I have?
Claude: [calls skyq_get_recordings]
        1. Planet Earth III (P00001AA) — recorded 2024-01-15
        2. Formula 1 Highlights (P00002BB) — recorded 2024-01-14
        ...

You: Pause the TV
Claude: [calls skyq_press with keys=["pause"]]
        Done.
```

---

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/ tests/

# Type-check
mypy src/
```

### Project structure

```
skyq-mcp-server/
├── src/
│   └── skyq_mcp/
│       ├── __init__.py        # Package metadata
│       ├── __main__.py        # CLI entry point
│       ├── server.py          # MCP server & tool definitions
│       └── skyq_client.py     # SkyQRemote connection manager
├── tests/
│   ├── conftest.py
│   └── test_server.py         # Unit tests (fully mocked)
├── pyproject.toml
└── README.md
```

---

## Limitations & notes

- The `pyskyqremote` library is no longer actively maintained; it works against current Sky Q firmware but may break if Sky update the API.
- Recording management (delete) should be used with care — there is no undo.
- Channel service IDs (`sid`) are Sky-specific and differ by region and bouquet. Consult the EPG or `get_current_media` to discover them.
- The server manages multiple boxes in a single process; each `skyq_connect` call adds an entry to an in-memory registry that resets when the server restarts.

---

## License

MIT — see [LICENSE](LICENSE).
