"""
Unit tests for the current quantclaw_receiver/device_manager.py logic.

说明：
- 这个文件测的是当前 main.py 主线使用的 QuantClawDeviceManager。
- 不依赖真实 PostgreSQL。
- 不需要启动 main.py。
- 不需要真实设备。
- 通过 monkeypatch 替换 DatabaseManager / UDPBroadcastReceiver，专注测试 device_manager.py 自身逻辑。

运行：
    python -m pytest tests/test_main_device_manager.py -q
"""

import json
from datetime import datetime, timezone

import pytest

from quantclaw_receiver.config import QuantClawConfig
from quantclaw_receiver.exceptions import (
    InvalidJsonError,
    InvalidSignatureError,
    InvalidTimestampError,
    QuantClawError,
)
from quantclaw_receiver.utils import make_sign
import quantclaw_receiver.device_manager as dm_module


# =========================
# Fake dependencies
# =========================

class FakeDatabaseManager:
    """替代真实 DatabaseManager，避免连接 PostgreSQL。"""

    instances = []

    def __init__(self, config):
        self.config = config
        self.schema_ensured = False
        self.register_calls = []
        self.heartbeat_calls = []
        self.pairing_calls = []
        self.devices_list_calls = []
        self.registration_status_calls = []
        self.heartbeat_status_calls = []
        self.health_connected = True
        self.heartbeat_error = None
        self.heartbeat_data = {
            "nextHeartbeatIntervalSec": 60,
            "serverTime": "2026-06-01T16:31:00Z",
        }
        FakeDatabaseManager.instances.append(self)

    def ensure_schema(self):
        self.schema_ensured = True

    def register_device(self, mac, payload):
        self.register_calls.append((mac, payload))
        return {
            "mac": mac,
            "isNew": True,
            "heartbeatIntervalSec": 60,
            "serverTime": "2026-06-01T16:31:00Z",
        }

    def process_heartbeat(self, mac, payload):
        self.heartbeat_calls.append((mac, payload))
        if self.heartbeat_error is not None:
            return self.heartbeat_error, None
        return None, self.heartbeat_data

    def get_pairing_snapshot(self, mac, observed_macs):
        self.pairing_calls.append((mac, observed_macs))
        return {
            "observedMacs": observed_macs,
            "pairedCandidateMacs": observed_macs,
            "scanMode": "loop",
            "pairedCount": len(observed_macs),
            "pairedDevices": [],
        }

    def get_devices_list(self, user_phone=""):
        self.devices_list_calls.append(user_phone)
        return {
            "scanMode": "loop",
            "totalKnownCount": 1,
            "userPhone": user_phone,
            "devices": [
                {
                    "mac": "aa:bb:cc:dd:ee:01",
                    "hostname": "fake-device",
                    "isOnline": True,
                }
            ],
        }

    def get_registration_status(self, device_id):
        self.registration_status_calls.append(device_id)
        return {"mac": device_id, "registered": True}

    def get_heartbeat_status(self, device_id):
        self.heartbeat_status_calls.append(device_id)
        return {"mac": device_id, "status": "online", "isOnline": True}

    def health_check(self):
        return {"connected": self.health_connected, "driver": "fake-postgres"}


class FakeUDPBroadcastReceiver:
    """替代真实 UDPBroadcastReceiver，避免真实 socket 监听。"""

    instances = []

    def __init__(self, config, db_manager):
        self.config = config
        self.db_manager = db_manager
        self.started = False
        self.stopped = False
        FakeUDPBroadcastReceiver.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class FakeClient:
    def __init__(self, host="127.0.0.1"):
        self.host = host


class FakeUrl:
    def __init__(self, path="/api/device/register", query=""):
        self.path = path
        self.query = query

    def __str__(self):
        if self.query:
            return f"http://testserver{self.path}?{self.query}"
        return f"http://testserver{self.path}"


class FakeRequest:
    """
    足够满足 device_manager.py 使用的 Request 替身：
    - await request.body()
    - request.headers.items()
    - request.client.host
    - request.url.query
    - str(request.url)
    """

    def __init__(
        self,
        body=b"",
        headers=None,
        path="/api/device/register",
        query="",
        client_host="127.0.0.1",
    ):
        self._body = body
        self.headers = headers or {}
        self.url = FakeUrl(path=path, query=query)
        self.client = FakeClient(client_host)

    async def body(self):
        return self._body


@pytest.fixture(autouse=True)
def patch_external_dependencies(monkeypatch):
    """每个测试自动替换掉真实 DB 和 UDP。"""
    FakeDatabaseManager.instances.clear()
    FakeUDPBroadcastReceiver.instances.clear()

    monkeypatch.setattr(dm_module, "DatabaseManager", FakeDatabaseManager)
    monkeypatch.setattr(dm_module, "UDPBroadcastReceiver", FakeUDPBroadcastReceiver)


def make_manager(**overrides):
    config = QuantClawConfig(
        allow_insecure=overrides.pop("allow_insecure", True),
        udp_enabled=overrides.pop("udp_enabled", False),
        device_secret=overrides.pop("device_secret", "unit-secret"),
        max_skew_sec=overrides.pop("max_skew_sec", 300),
        heartbeat_interval_sec=overrides.pop("heartbeat_interval_sec", 60),
        next_heartbeat_interval_sec=overrides.pop("next_heartbeat_interval_sec", 60),
        heartbeat_allow_implicit=overrides.pop("heartbeat_allow_implicit", True),
        pg_host=overrides.pop("pg_host", "localhost"),
        pg_port=overrides.pop("pg_port", 5432),
        pg_user=overrides.pop("pg_user", "postgres"),
        pg_password=overrides.pop("pg_password", "postgres"),
        pg_dbname=overrides.pop("pg_dbname", "quantclaw"),
        udp_bind_port=overrides.pop("udp_bind_port", 12345),
        udp_response_port=overrides.pop("udp_response_port", 12346),
        host=overrides.pop("host", "0.0.0.0"),
        port=overrides.pop("port", 8082),
    )
    assert not overrides, f"Unknown config overrides: {overrides}"
    return dm_module.QuantClawDeviceManager(config)


def json_body(payload):
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# =========================
# Startup / shutdown / health
# =========================

@pytest.mark.asyncio
async def test_startup_ensures_schema_and_does_not_start_udp_when_disabled():
    manager = make_manager(udp_enabled=False)

    await manager.startup()

    assert manager.db_manager.schema_ensured is True
    assert manager.udp_receiver.started is False


@pytest.mark.asyncio
async def test_startup_starts_udp_when_enabled():
    manager = make_manager(udp_enabled=True)

    await manager.startup()

    assert manager.db_manager.schema_ensured is True
    assert manager.udp_receiver.started is True


@pytest.mark.asyncio
async def test_shutdown_stops_udp_receiver():
    manager = make_manager(udp_enabled=True)

    await manager.shutdown()

    assert manager.udp_receiver.stopped is True


@pytest.mark.asyncio
async def test_health_check_reports_healthy_when_db_connected():
    manager = make_manager(udp_enabled=True, port=8082)

    result = await manager.health_check()

    assert result["status"] == "healthy"
    assert result["database"]["connected"] is True
    assert result["config"]["port"] == 8082
    assert result["config"]["udp_broadcast_receiver"]["enabled"] is True
    assert result["config"]["hmac_required"] is False


@pytest.mark.asyncio
async def test_health_check_reports_degraded_when_db_disconnected():
    manager = make_manager()
    manager.db_manager.health_connected = False

    result = await manager.health_check()

    assert result["status"] == "degraded"
    assert result["database"]["connected"] is False


# =========================
# Device list / status pass-through
# =========================

@pytest.mark.asyncio
async def test_get_devices_list_delegates_to_database_with_user_phone():
    manager = make_manager()

    result = await manager.get_devices_list(user_phone="13708800655")

    assert result["userPhone"] == "13708800655"
    assert manager.db_manager.devices_list_calls == ["13708800655"]


@pytest.mark.asyncio
async def test_get_registration_status_delegates_to_database():
    manager = make_manager()

    result = await manager.get_registration_status("aa:bb:cc:dd:ee:01")

    assert result == {"mac": "aa:bb:cc:dd:ee:01", "registered": True}
    assert manager.db_manager.registration_status_calls == ["aa:bb:cc:dd:ee:01"]


@pytest.mark.asyncio
async def test_get_heartbeat_status_delegates_to_database():
    manager = make_manager()

    result = await manager.get_heartbeat_status("aa:bb:cc:dd:ee:01")

    assert result["status"] == "online"
    assert result["isOnline"] is True
    assert manager.db_manager.heartbeat_status_calls == ["aa:bb:cc:dd:ee:01"]


# =========================
# validate_request
# =========================

@pytest.mark.asyncio
async def test_validate_request_parses_json_body_and_normalizes_register_payload():
    manager = make_manager(allow_insecure=True)
    body = json_body(
        {
            "MAC": "AA-BB-CC-DD-EE-01",
            "host": "unit-device",
            "deviceModel": "QuantClaw-Test",
            "firmware_version": "1.0.0",
            "last_ssid": "unit-wifi",
            "device_ip": "192.168.1.100",
            "ttyd": "enabled",
            "ttyd_port": "7682",
            "mdns": "unit-device.local",
            "http_port": "8080",
        }
    )
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/register",
        client_host="192.168.1.10",
    )

    payload = await manager.validate_request("/api/device/register", request, body)

    assert payload["mac"] == "aa:bb:cc:dd:ee:01"
    assert payload["hostname"] == "unit-device"
    assert payload["model"] == "QuantClaw-Test"
    assert payload["firmwareVersion"] == "1.0.0"
    assert payload["ssid"] == "unit-wifi"
    assert payload["ip"] == "192.168.1.100"
    assert payload["ttydEnabled"] is True
    assert payload["ttydPort"] == 7682
    assert payload["mdnsHost"] == "unit-device.local"
    assert payload["httpPort"] == 8080
    assert payload["accessScope"] == "lan"
    assert payload["_observedMacs"][0] == "aa:bb:cc:dd:ee:01"


@pytest.mark.asyncio
async def test_validate_request_merges_query_params_without_overwriting_body_values():
    manager = make_manager(allow_insecure=True)
    body = json_body(
        {
            "mac": "AA:BB:CC:DD:EE:01",
            "hostname": "body-host",
            "ip": "192.168.1.100",
        }
    )
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/register",
        query="hostname=query-host&model=QueryModel&ssid=query-wifi",
        client_host="192.168.1.10",
    )

    payload = await manager.validate_request("/api/device/register", request, body)

    assert payload["hostname"] == "body-host"
    assert payload["model"] == "QueryModel"
    assert payload["ssid"] == "query-wifi"


@pytest.mark.asyncio
async def test_validate_request_parses_form_encoded_body_when_content_type_is_not_json():
    manager = make_manager(allow_insecure=True)
    body = b"mac=AA%3ABB%3ACC%3ADD%3AEE%3A02&hostname=form-device&ip=192.168.1.102"
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
        path="/api/device/register",
        client_host="192.168.1.10",
    )

    payload = await manager.validate_request("/api/device/register", request, body)

    assert payload["mac"] == "aa:bb:cc:dd:ee:02"
    assert payload["hostname"] == "form-device"
    assert payload["ip"] == "192.168.1.102"


@pytest.mark.asyncio
async def test_validate_request_rejects_invalid_json():
    manager = make_manager(allow_insecure=True)
    body = b"{bad-json"
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/register",
    )

    with pytest.raises(InvalidJsonError):
        await manager.validate_request("/api/device/register", request, body)


@pytest.mark.asyncio
async def test_validate_request_rejects_json_array_body():
    manager = make_manager(allow_insecure=True)
    body = b'["not", "object"]'
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/register",
    )

    with pytest.raises(InvalidJsonError):
        await manager.validate_request("/api/device/register", request, body)


@pytest.mark.asyncio
async def test_validate_request_secure_mode_requires_signature_headers():
    manager = make_manager(allow_insecure=False)
    body = json_body({"mac": "AA:BB:CC:DD:EE:01"})
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/register",
    )

    with pytest.raises(QuantClawError) as exc:
        await manager.validate_request("/api/device/register", request, body)

    assert exc.value.code == 1001
    assert "missing X-Timestamp" in exc.value.message


@pytest.mark.asyncio
async def test_validate_request_secure_mode_accepts_valid_signature_for_register():
    manager = make_manager(allow_insecure=False, device_secret="unit-secret")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "mac": "AA:BB:CC:DD:EE:01",
        "hostname": "secure-device",
        "model": "QuantClaw-Secure",
        "firmwareVersion": "1.0.0",
        "ssid": "secure-wifi",
        "ip": "192.168.1.101",
        "interfaces": [],
        "ttydEnabled": True,
        "ttydPort": 7681,
        "mdnsHost": "secure-device.local",
        "httpPort": 80,
        "accessScope": "lan",
        "timestamp": timestamp,
    }
    body = json_body(payload)
    signature = make_sign("POST", "/api/device/register", timestamp, body, "unit-secret")
    request = FakeRequest(
        body=body,
        headers={
            "content-type": "application/json",
            "x-timestamp": timestamp,
            "x-signature": signature,
        },
        path="/api/device/register",
        client_host="192.168.1.10",
    )

    result = await manager.validate_request("/api/device/register", request, body)

    assert result["mac"] == "aa:bb:cc:dd:ee:01"
    assert result["hostname"] == "secure-device"


@pytest.mark.asyncio
async def test_validate_request_secure_mode_rejects_invalid_signature():
    manager = make_manager(allow_insecure=False, device_secret="unit-secret")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "mac": "AA:BB:CC:DD:EE:01",
        "hostname": "secure-device",
        "model": "QuantClaw-Secure",
        "firmwareVersion": "1.0.0",
        "ssid": "secure-wifi",
        "ip": "192.168.1.101",
        "interfaces": [],
        "ttydEnabled": True,
        "ttydPort": 7681,
        "mdnsHost": "secure-device.local",
        "httpPort": 80,
        "accessScope": "lan",
        "timestamp": timestamp,
    }
    body = json_body(payload)
    request = FakeRequest(
        body=body,
        headers={
            "content-type": "application/json",
            "x-timestamp": timestamp,
            "x-signature": "bad-signature",
        },
        path="/api/device/register",
        client_host="192.168.1.10",
    )

    with pytest.raises(InvalidSignatureError):
        await manager.validate_request("/api/device/register", request, body)


@pytest.mark.asyncio
async def test_validate_request_secure_mode_rejects_timestamp_mismatch():
    manager = make_manager(allow_insecure=False, device_secret="unit-secret")
    header_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload_timestamp = "2026-01-01T00:00:00Z"
    payload = {
        "mac": "AA:BB:CC:DD:EE:01",
        "hostname": "secure-device",
        "model": "QuantClaw-Secure",
        "firmwareVersion": "1.0.0",
        "ssid": "secure-wifi",
        "ip": "192.168.1.101",
        "interfaces": [],
        "ttydEnabled": True,
        "ttydPort": 7681,
        "mdnsHost": "secure-device.local",
        "httpPort": 80,
        "accessScope": "lan",
        "timestamp": payload_timestamp,
    }
    body = json_body(payload)
    signature = make_sign("POST", "/api/device/register", header_timestamp, body, "unit-secret")
    request = FakeRequest(
        body=body,
        headers={
            "content-type": "application/json",
            "x-timestamp": header_timestamp,
            "x-signature": signature,
        },
        path="/api/device/register",
        client_host="192.168.1.10",
    )

    with pytest.raises(InvalidTimestampError):
        await manager.validate_request("/api/device/register", request, body)


# =========================
# register_device / create_device
# =========================

@pytest.mark.asyncio
async def test_register_device_with_empty_body_returns_devices_list_in_insecure_mode():
    manager = make_manager(allow_insecure=True)
    request = FakeRequest(
        body=b"",
        path="/api/device/register",
        query="mac=AA:BB:CC:DD:EE:01",
    )

    result = await manager.register_device(request)

    assert result["totalKnownCount"] == 1
    assert manager.db_manager.register_calls == []
    assert manager.db_manager.devices_list_calls == [""]


@pytest.mark.asyncio
async def test_register_device_calls_database_and_pairing_snapshot():
    manager = make_manager(allow_insecure=True)
    body = json_body(
        {
            "mac": "AA:BB:CC:DD:EE:01",
            "hostname": "registered-device",
            "model": "QuantClaw-Test",
            "firmwareVersion": "1.0.0",
            "ssid": "unit-wifi",
            "ip": "192.168.1.101",
            "ttydEnabled": True,
            "ttydPort": 7681,
            "mdnsHost": "registered-device.local",
            "httpPort": 80,
            "accessScope": "lan",
        }
    )
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/register",
        client_host="192.168.1.10",
    )

    result = await manager.register_device(request)

    assert result["mac"] == "aa:bb:cc:dd:ee:01"
    assert result["isNew"] is True
    assert result["pairedCount"] >= 1

    assert len(manager.db_manager.register_calls) == 1
    mac, payload = manager.db_manager.register_calls[0]
    assert mac == "aa:bb:cc:dd:ee:01"
    assert payload["hostname"] == "registered-device"
    assert payload["ip"] == "192.168.1.101"

    assert len(manager.db_manager.pairing_calls) == 1
    pairing_mac, observed = manager.db_manager.pairing_calls[0]
    assert pairing_mac == "aa:bb:cc:dd:ee:01"
    assert "aa:bb:cc:dd:ee:01" in observed


@pytest.mark.asyncio
async def test_create_device_delegates_to_register_device():
    manager = make_manager(allow_insecure=True)
    body = json_body(
        {
            "mac": "AA:BB:CC:DD:EE:09",
            "hostname": "created-device",
            "ip": "192.168.1.109",
        }
    )
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/register",
    )

    result = await manager.create_device(request)

    assert result["mac"] == "aa:bb:cc:dd:ee:09"
    assert len(manager.db_manager.register_calls) == 1


# =========================
# process_heartbeat
# =========================

@pytest.mark.asyncio
async def test_process_heartbeat_with_empty_body_returns_devices_list_in_insecure_mode():
    manager = make_manager(allow_insecure=True)
    request = FakeRequest(
        body=b"",
        path="/api/device/heartbeat",
        query="mac=AA:BB:CC:DD:EE:01",
    )

    result = await manager.process_heartbeat(request)

    assert result["totalKnownCount"] == 1
    assert manager.db_manager.heartbeat_calls == []
    assert manager.db_manager.devices_list_calls == [""]


@pytest.mark.asyncio
async def test_process_heartbeat_updates_database_and_pairing_snapshot():
    manager = make_manager(allow_insecure=True)
    body = json_body(
        {
            "mac": "AA:BB:CC:DD:EE:01",
            "hostname": "heartbeat-device",
            "firmwareVersion": "1.0.1",
            "ssid": "heartbeat-wifi",
            "ip": "192.168.1.111",
            "internetAvailable": True,
            "status": "online",
            "ttydEnabled": True,
            "ttydPort": 7681,
            "mdnsHost": "heartbeat-device.local",
            "httpPort": 80,
            "accessScope": "lan",
        }
    )
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/heartbeat",
        client_host="192.168.1.10",
    )

    result = await manager.process_heartbeat(request)

    assert result["nextHeartbeatIntervalSec"] == 60
    assert result["pairedCount"] >= 1

    assert len(manager.db_manager.heartbeat_calls) == 1
    mac, payload = manager.db_manager.heartbeat_calls[0]
    assert mac == "aa:bb:cc:dd:ee:01"
    assert payload["firmwareVersion"] == "1.0.1"
    assert payload["ssid"] == "heartbeat-wifi"
    assert payload["ip"] == "192.168.1.111"
    assert payload["internetAvailable"] is True
    assert payload["status"] == "online"

    assert len(manager.db_manager.pairing_calls) == 1


@pytest.mark.asyncio
async def test_process_heartbeat_returns_database_error_without_pairing_snapshot():
    manager = make_manager(allow_insecure=True)
    manager.db_manager.heartbeat_error = {
        "code": 1005,
        "message": "device not found",
        "data": None,
    }
    body = json_body(
        {
            "mac": "AA:BB:CC:DD:EE:88",
            "ip": "192.168.1.188",
            "internetAvailable": True,
            "status": "online",
        }
    )
    request = FakeRequest(
        body=body,
        headers={"content-type": "application/json"},
        path="/api/device/heartbeat",
    )

    result = await manager.process_heartbeat(request)

    assert result["code"] == 1005
    assert result["message"] == "device not found"
    assert len(manager.db_manager.heartbeat_calls) == 1
    assert manager.db_manager.pairing_calls == []
