"""Unit tests for the Sky Q MCP server tools.

Requires: pytest, pytest-asyncio, pytest-mock
Run: pytest tests/
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from skyq_mcp.server import call_tool, _clients


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse(content_list) -> dict | list:
    return json.loads(content_list[0].text)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_HOST = "192.168.1.99"

FAKE_DEVICE = SimpleNamespace(
    IPAddress=FAKE_HOST,
    hardwareName="Falcon",
    hardwareModel="ES240",
    manufacturer="Sky",
    modelNumber="Q112.000.21.00L",
    serialNumber="0627086857",
    versionNumber="32B12D",
    countryCode="GBR",
    bouquet=4101,
    subbouquet=9,
    hdrCapable=True,
    uhdCapable=True,
)

FAKE_MEDIA = SimpleNamespace(
    channel="BBC One South",
    channelno="101",
    image_url="https://example.com/logo.png",
    sid=2153,
    pvrid=None,
    live=True,
)

FAKE_STATE = SimpleNamespace(
    CurrentTransportState="PLAYING",
    CurrentTransportStatus="OK",
    CurrentSpeed="1",
    state="PLAYING",
)

FAKE_APP = SimpleNamespace(
    appid="com.bskyb.beehive",
    title="Beehive Bedlam",
)


@pytest.fixture(autouse=True)
def clean_clients():
    """Ensure the global client registry is empty before each test."""
    _clients._clients.clear()
    yield
    _clients._clients.clear()


@pytest.fixture
def mock_remote():
    """Patch SkyQRemote so no network calls are made."""
    with patch("skyq_mcp.skyq_client.SkyQRemote") as MockClass:
        instance = MagicMock()
        instance.get_device_information.return_value = FAKE_DEVICE
        instance.power_status.return_value = "ON"
        instance.get_current_state.return_value = FAKE_STATE
        instance.get_current_media.return_value = FAKE_MEDIA
        instance.get_active_application.return_value = FAKE_APP
        MockClass.return_value = instance
        yield instance


# ---------------------------------------------------------------------------
# Connection tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_success(mock_remote):
    result = await call_tool("skyq_connect", {"host": FAKE_HOST})
    data = parse(result)
    assert data["status"] == "connected"
    assert data["host"] == FAKE_HOST
    assert "device" in data


@pytest.mark.asyncio
async def test_connect_missing_host():
    result = await call_tool("skyq_connect", {})
    data = parse(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_list_devices(mock_remote):
    await call_tool("skyq_connect", {"host": FAKE_HOST})
    result = await call_tool("skyq_list_devices", {})
    data = parse(result)
    assert any(d["host"] == FAKE_HOST for d in data)


@pytest.mark.asyncio
async def test_disconnect(mock_remote):
    await call_tool("skyq_connect", {"host": FAKE_HOST})
    result = await call_tool("skyq_disconnect", {"host": FAKE_HOST})
    data = parse(result)
    assert data["status"] == "disconnected"


# ---------------------------------------------------------------------------
# Status tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_power_status(mock_remote):
    await call_tool("skyq_connect", {"host": FAKE_HOST})
    result = await call_tool("skyq_power_status", {"host": FAKE_HOST})
    data = parse(result)
    assert data["power_status"] == "ON"


@pytest.mark.asyncio
async def test_get_current_state(mock_remote):
    await call_tool("skyq_connect", {"host": FAKE_HOST})
    result = await call_tool("skyq_get_current_state", {"host": FAKE_HOST})
    data = parse(result)
    assert data["state"] == "PLAYING"


@pytest.mark.asyncio
async def test_get_current_media(mock_remote):
    await call_tool("skyq_connect", {"host": FAKE_HOST})
    result = await call_tool("skyq_get_current_media", {"host": FAKE_HOST})
    data = parse(result)
    assert data["channel"] == "BBC One South"
    assert data["live"] is True


@pytest.mark.asyncio
async def test_get_active_application(mock_remote):
    await call_tool("skyq_connect", {"host": FAKE_HOST})
    result = await call_tool("skyq_get_active_application", {"host": FAKE_HOST})
    data = parse(result)
    assert data["appid"] == "com.bskyb.beehive"


# ---------------------------------------------------------------------------
# Remote control tools
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_press_keys(mock_remote):
    await call_tool("skyq_connect", {"host": FAKE_HOST})
    result = await call_tool("skyq_press", {"host": FAKE_HOST, "keys": ["play", "pause"]})
    data = parse(result)
    assert data["pressed"] == ["play", "pause"]
    assert mock_remote.press.call_count == 2


@pytest.mark.asyncio
async def test_set_channel(mock_remote):
    await call_tool("skyq_connect", {"host": FAKE_HOST})
    result = await call_tool("skyq_set_channel", {"host": FAKE_HOST, "channel_number": "101"})
    data = parse(result)
    assert data["tuned_to"] == "101"
    # 3 digit presses for "101"
    assert mock_remote.press.call_count == 3


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_requires_connect():
    result = await call_tool("skyq_power_status", {"host": "10.0.0.1"})
    data = parse(result)
    assert "error" in data
    assert "skyq_connect" in data["error"]


@pytest.mark.asyncio
async def test_unknown_tool():
    result = await call_tool("skyq_does_not_exist", {"host": FAKE_HOST})
    data = parse(result)
    assert "error" in data
