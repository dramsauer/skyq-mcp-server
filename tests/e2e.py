"""End-to-end tests for the Sky Q MCP server.

These tests run inside the Docker container and require a real Sky Q box
reachable at SKYQ_HOST.  They are invoked via Makefile targets:

  make test-e2e            # direct + MCP
  make test-e2e-direct     # Sky Q box only, no MCP layer
  make test-e2e-mcp        # MCP HTTP layer only (server must be running)
  make test-e2e-mutation-smoke  # includes one mutation (key press)

Usage:
  python -m tests.e2e [--skip-direct] [--skip-mcp]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import httpx

MCP_URL = os.getenv("MCP_URL", "http://localhost:8000/mcp")
HEALTH_URL = os.getenv("HEALTH_URL", "http://localhost:8000/health")
ALLOW_MUTATION_SMOKE = os.getenv("E2E_MUTATION_SMOKE", "").lower() in {"1", "true", "yes"}

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

_failures: list[str] = []


def _check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS}  {label}")
    else:
        print(f"  {FAIL}  {label}" + (f" — {detail}" if detail else ""))
        _failures.append(label)


# ---------------------------------------------------------------------------
# Direct Sky Q tests (via pyskyqremote)
# ---------------------------------------------------------------------------


def run_direct_tests() -> None:
    print("\n=== Direct Sky Q tests ===")
    try:
        from pyskyqremote.skyq_remote import SkyQRemote
        from skyq_mcp import settings

        client = SkyQRemote(settings.SKYQ_HOST, port=settings.SKYQ_PORT, json_port=settings.SKYQ_JSON_PORT)

        info = client.get_device_information()
        _check("get_device_information returns object", info is not None)

        status = client.power_status()
        _check("power_status is a string", isinstance(status, str), status)

        media = client.get_current_media()
        _check("get_current_media returns object", media is not None)

    except Exception as exc:
        _check("direct Sky Q connection", False, str(exc))


# ---------------------------------------------------------------------------
# MCP HTTP tests
# ---------------------------------------------------------------------------


def _jsonrpc(client: httpx.Client, method: str, params: dict) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = client.post(MCP_URL, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def run_mcp_tests() -> None:
    print("\n=== MCP HTTP tests ===")
    try:
        with httpx.Client() as client:
            # Health
            r = client.get(HEALTH_URL, timeout=5)
            _check("GET /health returns 200", r.status_code == 200)

            # tools/list
            resp = _jsonrpc(client, "tools/list", {})
            tools = resp.get("result", {}).get("tools", [])
            tool_names = {t["name"] for t in tools}
            _check("tools/list returns tools", len(tools) > 0)
            _check("skyq_device_info listed", "skyq_device_info" in tool_names)
            _check("skyq_power_status listed", "skyq_power_status" in tool_names)
            _check("skyq_press listed", "skyq_press" in tool_names)

            # skyq_power_status
            resp = _jsonrpc(client, "tools/call", {"name": "skyq_power_status", "arguments": {}})
            content = resp.get("result", {}).get("content", [{}])
            data = json.loads(content[0].get("text", "{}"))
            _check("skyq_power_status responds", "power_status" in data or "error" in data)

            # mutation blocked by default
            resp = _jsonrpc(client, "tools/call", {"name": "skyq_press", "arguments": {"keys": ["play"]}})
            content = resp.get("result", {}).get("content", [{}])
            data = json.loads(content[0].get("text", "{}"))
            _check("skyq_press blocked without SKYQ_ALLOW_MUTATIONS", "error" in data)

            # optional mutation smoke test
            if ALLOW_MUTATION_SMOKE:
                print("\n  [mutation smoke — sending 'sky' key press]")
                resp = _jsonrpc(client, "tools/call", {"name": "skyq_press", "arguments": {"keys": ["sky"]}})
                content = resp.get("result", {}).get("content", [{}])
                data = json.loads(content[0].get("text", "{}"))
                _check("skyq_press mutation smoke", "pressed" in data, str(data))

    except Exception as exc:
        _check("MCP HTTP connection", False, str(exc))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-direct", action="store_true")
    parser.add_argument("--skip-mcp", action="store_true")
    args = parser.parse_args()

    if not args.skip_direct:
        run_direct_tests()
    if not args.skip_mcp:
        run_mcp_tests()

    print()
    if _failures:
        print(f"❌  {len(_failures)} test(s) failed: {', '.join(_failures)}")
        sys.exit(1)
    else:
        print("✅  All tests passed.")


if __name__ == "__main__":
    main()
