import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

from quantclaw_receiver.config import QuantClawConfig
from quantclaw_receiver.device_manager import QuantClawDeviceManager
from quantclaw_receiver.utils import format_server_time, parse_server_time


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
