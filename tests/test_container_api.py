import asyncio
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from api import api_server


@pytest.fixture
def container_api(monkeypatch, tmp_path):
    monkeypatch.setenv("MAXWELL_CONTAINER_MODE", "true")
    monkeypatch.setattr(api_server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api_server, "_has_admin_auth", lambda request: True)
    monkeypatch.setattr(api_server, "_load_control", dict)
    monkeypatch.setattr(api_server, "_rag_query_one", lambda *args: None)
    return tmp_path


def test_container_mode_never_invokes_pm2(container_api, monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("container API attempted supervisor subprocess")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    request = SimpleNamespace(query={})
    assert asyncio.run(api_server._pm2_json()) == []
    assert asyncio.run(api_server.pm2_logs(request)).status == 501
    assert asyncio.run(api_server.pm2_restart(request)).status == 501
    assert asyncio.run(api_server.pm2_status(request)).status == 200


@pytest.mark.parametrize("age,online", [(30, True), (200, False), (-60, False)])
def test_container_status_uses_recent_snapshot(container_api, age, online):
    timestamp = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
    (container_api / "discord_state.json").write_text(json.dumps({"updated_at": timestamp}))
    response = asyncio.run(api_server.bot_status(SimpleNamespace()))
    body = json.loads(response.text)
    assert body["supervisor"] == "compose"
    assert body["status_source"] == "discord_snapshot"
    assert body["online"] is online
    assert body["snapshot_updated_at"] == timestamp


def test_missing_snapshot_is_not_online(container_api):
    body = json.loads(asyncio.run(api_server.bot_status(SimpleNamespace())).text)
    assert body["online"] is False


def test_legacy_status_retains_pm2(container_api, monkeypatch):
    monkeypatch.delenv("MAXWELL_CONTAINER_MODE")

    async def pm2():
        return [{"name": "maxwell-bot", "pm2_env": {"status": "online"}}]

    monkeypatch.setattr(api_server, "_pm2_json", pm2)
    body = json.loads(asyncio.run(api_server.bot_status(SimpleNamespace())).text)
    assert body["supervisor"] == "pm2"
    assert body["online"] is True
