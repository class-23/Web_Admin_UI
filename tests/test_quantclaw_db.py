"""
DatabaseManager 集成测试
验证 SQLAlchemy 版本的 DatabaseManager 操作 Device 模型
"""
import pytest
from datetime import datetime

from app.utils.quantclaw_receiver.config import QuantClawConfig
from app.utils.quantclaw_receiver.database import DatabaseManager
from app.models.device import Device
from app.models.device_config import DeviceConfig

from tests.conftest import TestMainSession, TestSettingsSession


@pytest.fixture
def db_manager():
    config = QuantClawConfig()
    config.heartbeat_allow_implicit = True
    config.heartbeat_interval_sec = 60
    config.next_heartbeat_interval_sec = 60
    return DatabaseManager(config, lambda: TestMainSession(), lambda: TestSettingsSession())


class TestRegisterDevice:
    def test_register_new_device(self, db_manager, db):
        payload = {
            "hostname": "test-device",
            "model": "rpi5",
            "firmwareVersion": "2.0.0",
            "ip": "192.168.1.100",
            "ssid": "MyWiFi",
            "httpPort": 8080,
            "ttydEnabled": True,
            "ttydPort": 7681,
            "mdnsHost": "test.local",
            "accessScope": "lan",
        }
        result = db_manager.register_device("aa:bb:cc:dd:ee:ff", payload)

        assert result["mac"] == "aa:bb:cc:dd:ee:ff"
        assert result["isNew"] is True
        assert "serverTime" in result

        device = db.query(Device).filter(Device.mac_address == "aa:bb:cc:dd:ee:ff").first()
        assert device is not None
        assert device.hostname == "test-device"
        assert device.firmware_version == "2.0.0"
        assert device.ip_address == "192.168.1.100"
        assert device.ssid == "MyWiFi"
        assert device.http_port == 8080
        assert device.ttyd_enabled is True
        assert device.ttyd_port == 7681
        assert device.mdns_host == "test.local"
        assert device.access_scope == "lan"

    def test_register_existing_device_updates(self, db_manager, db):
        payload1 = {"hostname": "old-name", "ip": "10.0.0.1"}
        db_manager.register_device("aa:bb:cc:dd:ee:ff", payload1)

        payload2 = {"hostname": "new-name", "ip": "10.0.0.2",
                      "firmwareVersion": "3.0", "ssid": "NewWiFi"}
        result = db_manager.register_device("aa:bb:cc:dd:ee:ff", payload2)

        assert result["isNew"] is False

        device = db.query(Device).filter(Device.mac_address == "aa:bb:cc:dd:ee:ff").first()
        assert device.hostname == "new-name"
        assert device.ip_address == "10.0.0.2"
        assert device.firmware_version == "3.0"


class TestProcessHeartbeat:
    def test_heartbeat_existing_device(self, db_manager, db):
        db_manager.register_device("aa:bb:cc:dd:ee:ff",
                                     {"hostname": "hb-device", "ip": "10.0.0.1",
                                      "firmwareVersion": "1.0"})

        payload = {
            "firmwareVersion": "1.1",
            "ip": "10.0.0.2",
            "ssid": "WiFi-5G",
            "internetAvailable": True,
            "status": "online",
            "ttydEnabled": False,
            "ttydPort": 7681,
            "mdnsHost": "hb.local",
            "httpPort": 80,
            "accessScope": "lan",
        }
        err, result = db_manager.process_heartbeat("aa:bb:cc:dd:ee:ff", payload)

        assert err is None
        assert result["nextHeartbeatIntervalSec"] == 60
        assert "serverTime" in result

        device = db.query(Device).filter(Device.mac_address == "aa:bb:cc:dd:ee:ff").first()
        assert device.ip_address == "10.0.0.2"
        assert device.ssid == "WiFi-5G"
        assert device.internet_available is True
        assert device.status == "online"

    def test_heartbeat_new_device_implicit_create(self, db_manager, db):
        payload = {
            "firmwareVersion": "2.0",
            "ip": "192.168.2.1",
            "ssid": "GuestWiFi",
            "internetAvailable": False,
            "status": "online",
            "ttydEnabled": True,
            "ttydPort": 7681,
            "mdnsHost": "new.local",
            "httpPort": 80,
            "accessScope": "lan",
        }
        err, result = db_manager.process_heartbeat("11:22:33:44:55:66", payload)

        assert err is None
        device = db.query(Device).filter(Device.mac_address == "11:22:33:44:55:66").first()
        assert device is not None
        assert device.ip_address == "192.168.2.1"

    def test_heartbeat_unknown_device_rejected(self, db, settings_db):
        config = QuantClawConfig()
        config.heartbeat_allow_implicit = False
        db_mgr = DatabaseManager(config, lambda: db, lambda: settings_db)

        payload = {"ip": "10.0.0.99"}
        err, result = db_mgr.process_heartbeat("ff:ee:dd:cc:bb:aa", payload)

        assert err is not None
        assert err["code"] == 1005
        assert result is None


class TestGetDevicesList:
    def test_returns_all_devices(self, db_manager, db):
        db_manager.register_device("aa:bb:cc:dd:ee:ff",
                                     {"hostname": "d1", "ip": "10.0.0.1"})
        db_manager.register_device("11:22:33:44:55:66",
                                     {"hostname": "d2", "ip": "10.0.0.2"})

        result = db_manager.get_devices_list()
        assert result["totalKnownCount"] == 2
        assert len(result["devices"]) == 2
        macs = {d["mac"] for d in result["devices"]}
        assert macs == {"aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"}


class TestRegistrationStatus:
    def test_registered_device(self, db_manager):
        db_manager.register_device("aa:bb:cc:dd:ee:ff", {"ip": "10.0.0.1"})

        status = db_manager.get_registration_status("aa:bb:cc:dd:ee:ff")
        assert status["registered"] is True
        assert status["device"]["mac"] == "aa:bb:cc:dd:ee:ff"

    def test_unknown_device(self, db_manager):
        status = db_manager.get_registration_status("ff:ff:ff:ff:ff:ff")
        assert status["registered"] is False
        assert status["device"] is None


class TestHeartbeatStatus:
    def test_online_device(self, db_manager):
        db_manager.register_device("aa:bb:cc:dd:ee:ff", {"ip": "10.0.0.1"})
        status = db_manager.get_heartbeat_status("aa:bb:cc:dd:ee:ff")
        assert "online" in status
        assert "lastSeenAt" in status

    def test_unknown_device(self, db_manager):
        status = db_manager.get_heartbeat_status("ff:ff:ff:ff:ff:ff")
        assert status["online"] is False


class TestHealthCheck:
    def test_connected(self, db_manager, db):
        db_manager.register_device("aa:bb:cc:dd:ee:ff", {"ip": "10.0.0.1"})
        result = db_manager.health_check()
        assert result["connected"] is True
        assert result["device_count"] >= 1


class TestDeviceConfig:
    def test_get_default_config_when_none(self, db_manager):
        config = db_manager.get_device_config(999)
        assert config["llm_provider"] == "deepseek"
        assert config["llm_model"] == "deepseek-v3"

    def test_get_existing_config(self, db_manager, settings_db, db, test_user):
        device = Device(
            user_id=test_user.id,
            mac_address="aa:bb:cc:dd:ee:ff",
            ip_address="10.0.0.1",
            hostname="config-test",
            status="online",
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        cfg = DeviceConfig(device_id=device.id, llm_provider="openai",
                           llm_model="gpt-4", temperature=0.9)
        settings_db.add(cfg)
        settings_db.commit()

        result = db_manager.get_device_config(device.id)
        assert result["llm_provider"] == "openai"
        assert result["llm_model"] == "gpt-4"
        assert result["temperature"] == 0.9

    def test_update_config_creates_new(self, db_manager, settings_db, db, test_user):
        device = Device(
            user_id=test_user.id,
            mac_address="cc:dd:ee:ff:00:11",
            ip_address="10.0.0.3",
            hostname="update-test",
            status="online",
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        result = db_manager.update_device_config(device.id,
                                                   {"llm_provider": "anthropic",
                                                    "temperature": 0.5})
        assert result["status"] == "updated"

        config = db_manager.get_device_config(device.id)
        assert config["llm_provider"] == "anthropic"
        assert config["temperature"] == 0.5
