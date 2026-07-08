"""
设备端点集成测试
验证 register/heartbeat/status/health 端点的端到端行为
"""
import json
import pytest
from fastapi.testclient import TestClient

from app.utils.quantclaw_receiver.config import QuantClawConfig
from app.utils.quantclaw_receiver.device_manager import QuantClawDeviceManager
from app.core.database import get_db, get_settings_db
from app.core.dependencies import get_current_user
from tests.conftest import TestMainSession, TestSettingsSession


def _build_app(manager, db, settings_db, user=None):
    from app.app_factory import create_app
    app = create_app()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_get_settings_db():
        try:
            yield settings_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings_db] = override_get_settings_db
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    app.state.device_manager = manager
    return app


@pytest.fixture
def manager():
    config = QuantClawConfig()
    config.allow_insecure = True
    config.heartbeat_allow_implicit = True
    return QuantClawDeviceManager(
        config,
        session_factory=lambda: TestMainSession(),
        settings_session_factory=lambda: TestSettingsSession(),
    )


@pytest.fixture
def client(manager, db, settings_db, test_user):
    app = _build_app(manager, db, settings_db, user=test_user)
    with TestClient(app) as c:
        yield c


class TestDeviceRegister:
    def test_register_new_device(self, client, db):
        payload = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "hostname": "test-device",
            "model": "rpi5",
            "firmwareVersion": "2.0.0",
            "ip": "192.168.1.100",
            "ssid": "MyWiFi",
            "ttydEnabled": True,
            "ttydPort": 7681,
            "mdnsHost": "test.local",
            "httpPort": 80,
            "accessScope": "lan",
            "interfaces": "eth0",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        resp = client.post("/api/device/register", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["mac"] == "aa:bb:cc:dd:ee:ff"
        assert data["isNew"] is True
        assert "serverTime" in data

    def test_register_duplicate_updates(self, client, db):
        payload = {"mac": "aa:bb:cc:dd:ee:ff", "hostname": "v1",
                     "ip": "10.0.0.1", "firmwareVersion": "1.0",
                     "ssid": "wifi", "ttydEnabled": False, "ttydPort": 7681,
                     "mdnsHost": "a.local", "httpPort": 80, "accessScope": "lan",
                     "interfaces": "eth0", "timestamp": "2024-01-01T00:00:00Z"}
        client.post("/api/device/register", json=payload)

        payload2 = {**payload, "hostname": "v2", "firmwareVersion": "2.0"}
        resp = client.post("/api/device/register", json=payload2)
        assert resp.json()["isNew"] is False


class TestDeviceHeartbeat:
    def test_heartbeat_existing_device(self, client, db):
        reg = {"mac": "aa:bb:cc:dd:ee:ff", "hostname": "hb-test",
               "ip": "10.0.0.1", "firmwareVersion": "1.0",
               "ssid": "wifi", "ttydEnabled": False, "ttydPort": 7681,
               "mdnsHost": "hb.local", "httpPort": 80, "accessScope": "lan",
               "interfaces": "eth0", "timestamp": "2024-01-01T00:00:00Z"}
        client.post("/api/device/register", json=reg)

        hb = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "firmwareVersion": "1.1",
            "ip": "10.0.0.2",
            "ssid": "WiFi-5G",
            "internetAvailable": True,
            "status": "online",
            "ttydEnabled": True,
            "ttydPort": 7681,
            "mdnsHost": "hb.local",
            "httpPort": 80,
            "accessScope": "lan",
            "interfaces": "wlan0",
            "timestamp": "2024-01-01T00:00:00Z",
        }
        resp = client.post("/api/device/heartbeat", json=hb)
        assert resp.status_code == 200
        data = resp.json()
        assert "nextHeartbeatIntervalSec" in data
        assert "serverTime" in data


class TestDeviceStatusEndpoints:
    def test_get_devices_list(self, client):
        resp = client.get("/api/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert "devices" in data["data"]

    def test_health_check(self, client):
        resp = client.get("/api/receiver/health")
        assert resp.status_code == 200

    def test_registration_status(self, client):
        reg = {"mac": "cc:dd:ee:ff:00:11", "hostname": "stat-test",
               "ip": "10.0.0.1", "firmwareVersion": "1.0",
               "ssid": "wifi", "ttydEnabled": False, "ttydPort": 7681,
               "mdnsHost": "s.local", "httpPort": 80, "accessScope": "lan",
               "interfaces": "eth0", "timestamp": "2024-01-01T00:00:00Z"}
        client.post("/api/device/register", json=reg)

        resp = client.get("/api/device/cc:dd:ee:ff:00:11/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["registered"] is True

    def test_heartbeat_status(self, client):
        reg = {"mac": "dd:ee:ff:00:11:22", "hostname": "hbstat",
               "ip": "10.0.0.2", "firmwareVersion": "1.0",
               "ssid": "wifi", "ttydEnabled": False, "ttydPort": 7681,
               "mdnsHost": "h.local", "httpPort": 80, "accessScope": "lan",
               "interfaces": "eth0", "timestamp": "2024-01-01T00:00:00Z"}
        client.post("/api/device/register", json=reg)

        resp = client.get("/api/device/dd:ee:ff:00:11:22/heartbeat")
        assert resp.status_code == 200
        data = resp.json()
        assert "online" in data
