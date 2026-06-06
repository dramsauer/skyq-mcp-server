"""Unit tests for the Sky Q MCP server.

All Sky Q network calls are mocked — no real receiver is needed.
Run with: pytest tests/
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Provide required env vars before importing the server
os.environ.setdefault("SKYQ_HOST", "192.168.1.99")

from skyq_mcp.server import app, call_tool  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(content_list) -> dict | list:
    return json.loads(content_list[0].text)


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

FAKE_DEVICE = SimpleNamespace(
    IPAddress="192.168.1.99",
    hardwareName="Falcon",
    hardwareModel="ES240",
    manufacturer="Sky",
    modelNumber="Q112.000.21.00L",
    serialNumber="0627086857",
    versionNumber="32B12D",
    countryCode="GBR",
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

FAKE_APP = SimpleNamespace(appid="com.bskyb.beehive", title="Beehive Bedlam")


# ---------------------------------------------------------------------------
# Fixture — mock pyskyqremote so nothing hits the network
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_remote():
    with patch("skyq_mcp.client._client", None), \
         patch("skyq_mcp.client.SkyQRemote") as MockClass:
        instance = MagicMock()
        instance.get_device_information.return_value = FAKE_DEVICE
        instance.power_status.return_value = "ON"
        instance.get_current_state.return_value = FAKE_STATE
        instance.get_current_media.return_value = FAKE_MEDIA
        instance.get_active_application.return_value = FAKE_APP
        MockClass.return_value = instance
        yield instance


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_device_info():
    result = await call_tool("skyq_device_info", {})
    data = parse(result)
    assert data["hardwareName"] == "Falcon"


@pytest.mark.asyncio
async def test_power_status():
    result = await call_tool("skyq_power_status", {})
    assert parse(result)["power_status"] == "ON"


@pytest.mark.asyncio
async def test_current_state():
    result = await call_tool("skyq_current_state", {})
    assert parse(result)["state"] == "PLAYING"


@pytest.mark.asyncio
async def test_current_media():
    result = await call_tool("skyq_current_media", {})
    data = parse(result)
    assert data["channel"] == "BBC One South"
    assert data["live"] is True


@pytest.mark.asyncio
async def test_active_application():
    result = await call_tool("skyq_active_application", {})
    assert parse(result)["appid"] == "com.bskyb.beehive"


# ---------------------------------------------------------------------------
# Mutation guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_press_blocked_by_default():
    with patch("skyq_mcp.server.settings.SKYQ_ALLOW_MUTATIONS", False):
        result = await call_tool("skyq_press", {"keys": ["play"]})
        data = parse(result)
        assert "error" in data
        assert "SKYQ_ALLOW_MUTATIONS" in data["error"]


@pytest.mark.asyncio
async def test_press_allowed_when_mutations_enabled(mock_remote):
    with patch("skyq_mcp.server.settings.SKYQ_ALLOW_MUTATIONS", True):
        result = await call_tool("skyq_press", {"keys": ["play", "pause"]})
        data = parse(result)
        assert data["pressed"] == ["play", "pause"]
        assert mock_remote.press.call_count == 2


@pytest.mark.asyncio
async def test_set_channel_blocked_by_default():
    with patch("skyq_mcp.server.settings.SKYQ_ALLOW_MUTATIONS", False):
        result = await call_tool("skyq_set_channel", {"channel_number": "101"})
        assert "error" in parse(result)


@pytest.mark.asyncio
async def test_set_channel_allowed(mock_remote):
    with patch("skyq_mcp.server.settings.SKYQ_ALLOW_MUTATIONS", True):
        result = await call_tool("skyq_set_channel", {"channel_number": "101"})
        assert parse(result)["tuned_to"] == "101"
        assert mock_remote.press.call_count == 3  # digits "1", "0", "1"


@pytest.mark.asyncio
async def test_delete_recording_blocked_by_default():
    with patch("skyq_mcp.server.settings.SKYQ_ALLOW_MUTATIONS", False):
        result = await call_tool("skyq_delete_recording", {"pvrid": "P12345ABC"})
        assert "error" in parse(result)


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_tool():
    result = await call_tool("skyq_does_not_exist", {})
    assert "error" in parse(result)
