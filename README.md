# Sky Q MCP Server

A Docker-based [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for
controlling Sky Q satellite receivers.  It exposes Sky Q features as MCP tools, including
EPG data, programme information, recording management, and remote-control commands.

Built on top of [pyskyqremote](https://github.com/RogerSelwyn/skyq_remote) by Roger Selwyn.
Primarily designed for UK receivers, with support for Italy and Germany.

---

## Quick Start

Create a local environment file:

```sh
make init
```

Edit `.env` and set your Sky Q box address:

```sh
SKYQ_HOST=192.168.1.99
```

Remote-control commands, channel changes, and recording deletion are disabled by default.
Enable them explicitly if you want assistants to change receiver state:

```sh
SKYQ_ALLOW_MUTATIONS=true
```

Start the MCP server:

```sh
make start
```

The MCP endpoint is available at:

```
http://localhost:8000/mcp
```

A health check is available at:

```
http://localhost:8000/health
```

View logs:

```sh
make logs
```

Stop the service:

```sh
make down
```

---

## Makefile

All operations go through `make`:

```sh
make help
```

Key targets:

| Target | Description |
|---|---|
| `make init` | Create `.env` from `.env.example` |
| `make build` | Build the Docker image |
| `make up` | Start in the foreground |
| `make start` | Start in the background |
| `make logs` | Follow service logs |
| `make down` | Stop and remove containers |
| `make check` | Check Python syntax and Compose config |
| `make test` | Run unit tests (no Sky Q box required) |
| `make test-e2e` | Run end-to-end tests (requires real box) |

---

## MCP Client Configuration

For MCP clients that support Streamable HTTP:

```json
{
  "mcpServers": {
    "skyq": {
      "transport": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

---

## Talking to the server with curl

The server speaks the MCP **Streamable HTTP** transport. To call a tool directly,
`POST` a JSON-RPC `tools/call` request to `/mcp/` (note the **trailing slash** — a request
to `/mcp` is redirected). You must accept both JSON and SSE, because the server streams its
reply as a `text/event-stream` (`event: message` / `data: …`).

**Check the box is reachable** — its power state:

```sh
curl -s -X POST http://localhost:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"skyq_power_status","arguments":{}}}'
```

```text
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text",
       "text":"{\n  \"power_status\": \"ON\"\n}"}],"isError":false}}
```

**Find a channel's service ID** — `skyq_current_media` returns the `sid` of whatever is
currently tuned (e.g. `141` for *Sky Sport Mix*):

```sh
curl -s -X POST http://localhost:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"skyq_current_media","arguments":{}}}'
```

**Get the EPG for a specific day** — here, tomorrow's schedule (`days: 1`) for sid `141`.
`date` is `YYYY-MM-DD` (UTC) and defaults to today if omitted:

```sh
curl -s -X POST http://localhost:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"skyq_epg",
                 "arguments":{"sid":141,"date":"2025-01-02","days":1}}}'
```

The tool result is JSON encoded as a string inside the SSE `data:` line. To strip the SSE
framing and pretty-print the programme list:

```sh
curl -s -X POST http://localhost:8000/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"skyq_epg","arguments":{"sid":141,"days":1}}}' \
  | sed -n 's/^data: //p' \
  | python3 -c 'import sys,json; print(json.loads(json.load(sys.stdin)["result"]["content"][0]["text"]).get("channelname"))'
```

> **Port note:** these examples assume the default `SERVER_PORT=8000`. If you set a
> different `SERVER_PORT` in `.env` (e.g. `8009`), Compose publishes that same port on the
> host — just use it in the URLs above (`http://localhost:8009/mcp/`).

---

## Available Tools

### Read-only (always available)

| Tool | Description |
|---|---|
| `skyq_device_info` | Hardware model, firmware, serial number, HDR/UHD capability |
| `skyq_power_status` | Power state: ON, STANDBY, or POWERED OFF |
| `skyq_current_state` | Transport state: PLAYING, PAUSED_PLAYBACK, STOPPED |
| `skyq_current_media` | Currently playing channel or recording |
| `skyq_active_application` | App currently running (Netflix, YouTube, …) |
| `skyq_epg` | EPG schedule for a channel by service ID and date |
| `skyq_programme_from_epg` | Single programme details by UUID |
| `skyq_current_live_programme` | Programme on air right now |
| `skyq_recordings` | Paginated list of stored recordings |
| `skyq_recording` | Details of one recording by PVR ID |

### Mutation tools (require `SKYQ_ALLOW_MUTATIONS=true`)

| Tool | Description |
|---|---|
| `skyq_press` | Send remote-control key presses |
| `skyq_set_channel` | Tune to a channel by number |
| `skyq_delete_recording` | Permanently delete a recording |

---

## Safety

Write/mutation tools are **disabled by default**.  An AI assistant cannot accidentally
change your receiver state unless you explicitly opt in:

```sh
# .env
SKYQ_ALLOW_MUTATIONS=true
```

Calling a mutation tool without this flag returns an error explaining how to enable it.

---

## Integration Tests

End-to-end tests run inside Docker and require a real Sky Q box:

```sh
make test-e2e           # direct + MCP layer
make test-e2e-direct    # Sky Q box directly, no MCP
make test-e2e-mcp       # MCP HTTP layer only
```

Optional mutation smoke test (sends a single key press):

```sh
make test-e2e-mutation-smoke
```

Unit tests (fully mocked, no box required):

```sh
make test
```

---

## Configuration Reference

All settings are read from `.env` (or environment variables):

| Variable | Default | Description |
|---|---|---|
| `SKYQ_HOST` | *(required)* | IP address of the Sky Q box |
| `SKYQ_PORT` | `49160` | Control port |
| `SKYQ_JSON_PORT` | `9006` | JSON API port |
| `SKYQ_EPG_CACHE_LEN` | `20` | EPG cache size |
| `SKYQ_ALLOW_MUTATIONS` | `false` | Enable write/control tools |
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8000` | Server port |

---

## Notes

- `pyskyqremote` is no longer actively maintained (the author no longer has Sky Q hardware),
  but the library is functional against current Sky Q firmware.
- Channel service IDs (`sid`) are Sky-specific — use `skyq_current_media` to discover
  the sid of the currently tuned channel.
- Recording deletion is permanent; there is no undo.

---

## License

MIT
