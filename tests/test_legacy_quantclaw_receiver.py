import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from quantclaw_receiver.config import QuantClawConfig
from quantclaw_receiver.device_manager import QuantClawDeviceManager
from quantclaw_receiver.utils import format_server_time, parse_server_time, row_to_device


class TestLegacyQuantClawReceiver:

    def test_startup_initializes_schema_before_udp(self):
        manager = QuantClawDeviceManager.__new__(QuantClawDeviceManager)
        manager.config = QuantClawConfig(udp_enabled=False)
        manager.db_manager = MagicMock()
        manager.udp_receiver = MagicMock()

        asyncio.run(manager.startup())

        manager.db_manager.ensure_schema.assert_called_once()
        manager.udp_receiver.start.assert_not_called()

    def test_parse_and_format_server_time_support_database_datetime(self):
        dt = datetime(2026, 5, 20, 15, 30, 0, tzinfo=timezone.utc)
        parsed = parse_server_time(dt)
        assert parsed == dt
        assert format_server_time(dt) == "2026-05-20T15:30:00Z"

    def test_row_to_device_marks_recent_heartbeat_online(self):
        now = datetime(2026, 5, 20, 15, 30, 0, tzinfo=timezone.utc)
        row = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "hostname": "dev",
            "model": "rpi5",
            "firmware_version": "1.0",
            "ip": "10.0.0.1",
            "ssid": "wifi",
            "internet_available": True,
            "status": "offline",
            "ttyd_enabled": False,
            "ttyd_port": 7681,
            "mdns_host": "",
            "http_port": 80,
            "access_scope": "lan",
            "last_seen_at": (now - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        device = row_to_device(row, now)
        assert device["isOnline"] is True

    def test_row_to_device_marks_timed_out_device_offline_even_if_status_online(self):
        now = datetime(2026, 5, 20, 15, 30, 0, tzinfo=timezone.utc)
        row = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "hostname": "dev",
            "model": "rpi5",
            "firmware_version": "1.0",
            "ip": "10.0.0.1",
            "ssid": "wifi",
            "internet_available": True,
            "status": "online",
            "ttyd_enabled": False,
            "ttyd_port": 7681,
            "mdns_host": "",
            "http_port": 80,
            "access_scope": "lan",
            "last_seen_at": (now - timedelta(seconds=181)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        device = row_to_device(row, now)
        assert device["status"] == "online"
        assert device["isOnline"] is False
