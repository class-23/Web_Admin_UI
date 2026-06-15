"""
Unit tests for the current quantclaw_receiver/database.py database layer.

说明：
- 这个文件测的是当前 main.py 主线使用的 quantclaw_receiver/database.py。
- 不连接真实 PostgreSQL。
- 不需要启动 main.py。
- 使用 FakeConnectionPool / FakeConnection / FakeCursor 模拟 PostgreSQL 行为。
- 重点测试 DatabaseManager 自身的数据库封装逻辑、register、heartbeat、列表、配对快照、状态查询和健康检查。

运行：
    python -m pytest tests/test_main_quantclaw_database.py -q
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg2
import pytest

from quantclaw_receiver.config import QuantClawConfig
from quantclaw_receiver.exceptions import DatabaseError
import quantclaw_receiver.database as db_module


# =========================
# Fake PostgreSQL layer
# =========================

class FakeDBState:
    def __init__(self):
        self.devices: dict[str, dict] = {}
        self.next_id = 1
        self.pool = None
        self.fail_getconn = False
        self.fail_prepare = False
        self.fail_next_execute = False
        self.schema_column_type = "timestamp with time zone"

    def new_device_id(self) -> int:
        value = self.next_id
        self.next_id += 1
        return value


class FakeCursor:
    def __init__(self, conn: "FakeConnection", cursor_factory=None):
        self.conn = conn
        self.state = conn.state
        self.cursor_factory = cursor_factory
        self.result = None
        self.results = None
        self.closed = False
        self.executed: list[tuple[str, object]] = []

    def execute(self, query, params=None):
        sql_text = str(query)
        sql_norm = " ".join(sql_text.lower().split())
        params = params or ()
        self.executed.append((sql_text, params))
        self.conn.executed.append((sql_text, params))

        if self.state.fail_next_execute:
            self.state.fail_next_execute = False
            raise psycopg2.OperationalError("fake execute failure")

        if sql_norm.startswith("set time zone"):
            self.result = None
            return

        if "information_schema.columns" in sql_norm:
            self.result = (self.state.schema_column_type,)
            return

        if "select id from devices where mac = %s and user_id = %s" in sql_norm:
            mac = params[0]
            row = self.state.devices.get(mac)
            self.result = (row["id"],) if row else None
            return

        if "insert into devices" in sql_norm:
            self._handle_insert(sql_norm, params)
            return

        if "update devices set" in sql_norm:
            self._handle_update(sql_norm, params)
            self.result = None
            return

        if "select mac, phone, hostname, model, firmware_version, ip, ssid" in sql_norm and "from devices" in sql_norm:
            self._handle_select_devices(sql_norm, params)
            return

        if "select mac, last_seen_at, status, internet_available, ip from devices where mac = %s" in sql_norm:
            mac = params[0]
            row = self.state.devices.get(mac)
            self.result = self._public_row(row) if row else None
            return

        if "select count(*) as cnt from devices" in sql_norm:
            self.result = {"cnt": len(self.state.devices)}
            return

        # Schema DDL / index DDL / unknown SQL: record only.
        self.result = None

    def _handle_insert(self, sql_norm: str, params):
        is_upsert = "on conflict (mac) do update" in sql_norm

        if "values (%s, %s, %s, %s, %s, %s, %s, false, 'unknown'" in sql_norm:
            # register_device upsert
            (
                mac, phone, hostname, model, firmware, ip, ssid,
                heartbeat_interval_sec, ttyd_enabled, ttyd_port, mdns_host,
                http_port, access_scope, first_seen_at, last_seen_at,
                created_at, updated_at, user_id,
            ) = params

            if is_upsert and mac in self.state.devices:
                row = self.state.devices[mac]
                if phone != "":
                    row["phone"] = phone
                row.update({
                    "hostname": hostname,
                    "model": model,
                    "firmware_version": firmware,
                    "ip": ip,
                    "ssid": ssid,
                    "ttyd_enabled": bool(ttyd_enabled),
                    "ttyd_port": ttyd_port,
                    "mdns_host": mdns_host,
                    "http_port": http_port,
                    "access_scope": access_scope,
                    "heartbeat_interval_sec": heartbeat_interval_sec,
                    "last_seen_at": last_seen_at,
                    "updated_at": updated_at,
                })
                self.result = (False,)  # is_new = False
                return

            self.state.devices[mac] = {
                "id": self.state.new_device_id(),
                "user_id": user_id,
                "phone": phone,
                "hostname": hostname,
                "model": model,
                "firmware_version": firmware,
                "ip": ip,
                "ssid": ssid,
                "internet_available": False,
                "status": "unknown",
                "heartbeat_interval_sec": heartbeat_interval_sec,
                "ttyd_enabled": bool(ttyd_enabled),
                "ttyd_port": ttyd_port,
                "mdns_host": mdns_host,
                "http_port": http_port,
                "access_scope": access_scope,
                "first_seen_at": first_seen_at,
                "last_seen_at": last_seen_at,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            self.result = (True,) if is_upsert else None
            return

        if "values (%s, %s, '', '', %s, %s, %s, %s, %s, 60" in sql_norm:
            # process_heartbeat implicit upsert
            (
                mac, phone, firmware, ip, ssid, internet_available, status,
                ttyd_enabled, ttyd_port, mdns_host, http_port, access_scope,
                first_seen_at, last_seen_at, created_at, updated_at, user_id,
            ) = params

            if is_upsert and mac in self.state.devices:
                row = self.state.devices[mac]
                if phone != "":
                    row["phone"] = phone
                row.update({
                    "firmware_version": firmware,
                    "ip": ip,
                    "ssid": ssid,
                    "internet_available": bool(internet_available),
                    "status": status,
                    "ttyd_enabled": bool(ttyd_enabled),
                    "ttyd_port": ttyd_port,
                    "mdns_host": mdns_host,
                    "http_port": http_port,
                    "access_scope": access_scope,
                    "last_seen_at": last_seen_at,
                    "updated_at": updated_at,
                })
                return

            self.state.devices[mac] = {
                "id": self.state.new_device_id(),
                "user_id": user_id,
                "phone": phone,
                "hostname": "",
                "model": "",
                "firmware_version": firmware,
                "ip": ip,
                "ssid": ssid,
                "internet_available": bool(internet_available),
                "status": status,
                "heartbeat_interval_sec": 60,
                "ttyd_enabled": bool(ttyd_enabled),
                "ttyd_port": ttyd_port,
                "mdns_host": mdns_host,
                "http_port": http_port,
                "access_scope": access_scope,
                "first_seen_at": first_seen_at,
                "last_seen_at": last_seen_at,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            return

        raise AssertionError(f"Unhandled INSERT SQL: {sql_norm}\nparams={params!r}")

    def _handle_update(self, sql_norm: str, params):
        if "heartbeat_interval_sec = %s" in sql_norm:
            # register_device update
            (
                phone_candidate, phone_value, hostname, model, firmware, ip, ssid,
                ttyd_enabled, ttyd_port, mdns_host, http_port, access_scope,
                heartbeat_interval_sec, last_seen_at, updated_at, mac, user_id,
            ) = params

            row = self.state.devices[mac]
            if phone_candidate != "":
                row["phone"] = phone_value
            row.update(
                {
                    "hostname": hostname,
                    "model": model,
                    "firmware_version": firmware,
                    "ip": ip,
                    "ssid": ssid,
                    "ttyd_enabled": bool(ttyd_enabled),
                    "ttyd_port": ttyd_port,
                    "mdns_host": mdns_host,
                    "http_port": http_port,
                    "access_scope": access_scope,
                    "heartbeat_interval_sec": heartbeat_interval_sec,
                    "last_seen_at": last_seen_at,
                    "updated_at": updated_at,
                }
            )
            return

        if "internet_available = %s" in sql_norm:
            # process_heartbeat update
            (
                phone_candidate, phone_value, last_seen_at, ip, ssid,
                internet_available, status, firmware, ttyd_enabled, ttyd_port,
                mdns_host, http_port, access_scope, updated_at, mac, user_id,
            ) = params

            row = self.state.devices[mac]
            if phone_candidate != "":
                row["phone"] = phone_value
            row.update(
                {
                    "last_seen_at": last_seen_at,
                    "ip": ip,
                    "ssid": ssid,
                    "internet_available": bool(internet_available),
                    "status": status,
                    "firmware_version": firmware,
                    "ttyd_enabled": bool(ttyd_enabled),
                    "ttyd_port": ttyd_port,
                    "mdns_host": mdns_host,
                    "http_port": http_port,
                    "access_scope": access_scope,
                    "updated_at": updated_at,
                }
            )
            return

        raise AssertionError(f"Unhandled UPDATE SQL: {sql_norm}\nparams={params!r}")

    def _handle_select_devices(self, sql_norm: str, params):
        rows = list(self.state.devices.values())

        if "where phone = %s" in sql_norm:
            phone = params[0]
            rows = [row for row in rows if row.get("phone") == phone]
        elif "where access_scope = 'lan'" in sql_norm:
            rows = [row for row in rows if row.get("access_scope") == "lan"]
        elif "where mac = %s" in sql_norm:
            mac = params[0]
            row = self.state.devices.get(mac)
            self.result = self._public_row(row) if row else None
            return

        def _sort_last_seen(row):
            value = row.get("last_seen_at")
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value.timestamp()
            if isinstance(value, str):
                try:
                    normalized = value.replace("Z", "+00:00")
                    parsed = datetime.fromisoformat(normalized)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=timezone.utc)
                    return parsed.timestamp()
                except ValueError:
                    return 0
            return 0

        rows.sort(key=_sort_last_seen, reverse=True)
        self.results = [self._public_row(row) for row in rows]
        self.result = self.results[0] if self.results else None

    def _public_row(self, row):
        if row is None:
            return None
        return {
            "mac": row["mac"] if "mac" in row else next((m for m, r in self.state.devices.items() if r is row), ""),
            "phone": row.get("phone", ""),
            "hostname": row.get("hostname", ""),
            "model": row.get("model", ""),
            "firmware_version": row.get("firmware_version", ""),
            "ip": row.get("ip", ""),
            "ssid": row.get("ssid", ""),
            "internet_available": row.get("internet_available", False),
            "status": row.get("status", "unknown"),
            "ttyd_enabled": row.get("ttyd_enabled", False),
            "ttyd_port": row.get("ttyd_port", 7681),
            "mdns_host": row.get("mdns_host", ""),
            "http_port": row.get("http_port", 80),
            "access_scope": row.get("access_scope", "lan"),
            "last_seen_at": row.get("last_seen_at"),
            "created_at": row.get("created_at"),
        }

    def fetchone(self):
        return self.result

    def fetchall(self):
        return self.results or []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, state: FakeDBState):
        self.state = state
        self.executed: list[tuple[str, object]] = []
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self, *args, **kwargs):
        return FakeCursor(self, cursor_factory=kwargs.get("cursor_factory"))

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakePool:
    def __init__(self, state: FakeDBState, *args, **kwargs):
        self.state = state
        self.args = args
        self.kwargs = kwargs
        self.connections = [FakeConnection(state)]
        self.getconn_calls = 0
        self.putconn_calls = 0
        self.last_putconn = None
        state.pool = self

    def getconn(self):
        self.getconn_calls += 1
        if self.state.fail_getconn:
            raise psycopg2.OperationalError("fake getconn failure")
        return self.connections[0]

    def putconn(self, conn):
        self.putconn_calls += 1
        self.last_putconn = conn


@pytest.fixture
def fake_state(monkeypatch):
    state = FakeDBState()

    def fake_pool_factory(*args, **kwargs):
        return FakePool(state, *args, **kwargs)

    monkeypatch.setattr(db_module, "ThreadedConnectionPool", fake_pool_factory)
    return state


def make_config(**overrides):
    defaults = {
        "pg_host": "localhost",
        "pg_port": 5432,
        "pg_user": "postgres",
        "pg_password": "postgres",
        "pg_dbname": "quantclaw",
        "heartbeat_interval_sec": 60,
        "next_heartbeat_interval_sec": 60,
        "heartbeat_allow_implicit": True,
    }
    defaults.update(overrides)
    return QuantClawConfig(**defaults)


def make_manager(fake_state, **overrides):
    return db_module.DatabaseManager(make_config(**overrides))


def register_payload(**overrides):
    payload = {
        "hostname": "unit-device",
        "model": "QuantClaw-Test",
        "firmwareVersion": "1.0.0",
        "ip": "192.168.1.100",
        "ssid": "unit-wifi",
        "phone": "13708800655",
        "ttydEnabled": True,
        "ttydPort": 7681,
        "mdnsHost": "unit-device.local",
        "httpPort": 80,
        "accessScope": "lan",
        "_observedMacs": ["aa:bb:cc:dd:ee:01", "11:22:33:44:55:66"],
    }
    payload.update(overrides)
    return payload


def heartbeat_payload(**overrides):
    payload = {
        "firmwareVersion": "1.0.1",
        "ip": "192.168.1.101",
        "ssid": "heartbeat-wifi",
        "phone": "13708800655",
        "internetAvailable": True,
        "status": "online",
        "ttydEnabled": True,
        "ttydPort": 7681,
        "mdnsHost": "heartbeat-device.local",
        "httpPort": 80,
        "accessScope": "lan",
        "_observedMacs": ["aa:bb:cc:dd:ee:01", "11:22:33:44:55:66"],
    }
    payload.update(overrides)
    return payload


# =========================
# Initialization / with_db
# =========================

def test_init_creates_threaded_connection_pool_with_config(fake_state):
    manager = make_manager(fake_state, pg_host="db.local", pg_port=5544, pg_user="u", pg_password="p", pg_dbname="d")

    pool = fake_state.pool
    assert pool is not None
    assert pool.kwargs["host"] == "db.local"
    assert pool.kwargs["port"] == 5544
    assert pool.kwargs["user"] == "u"
    assert pool.kwargs["password"] == "p"
    assert pool.kwargs["dbname"] == "d"
    assert manager._schema_initialized is False


def test_ensure_schema_runs_schema_setup_once_and_commits(fake_state):
    manager = make_manager(fake_state)

    manager.ensure_schema()
    manager.ensure_schema()

    conn = fake_state.pool.connections[0]
    executed_sql = "\n".join(sql for sql, _ in conn.executed)

    assert manager._schema_initialized is True
    assert fake_state.pool.getconn_calls == 1
    assert fake_state.pool.putconn_calls == 1
    assert conn.commits == 1
    assert "CREATE TABLE IF NOT EXISTS devices" in executed_sql
    assert "CREATE INDEX IF NOT EXISTS idx_devices_status" in executed_sql


def test_prepare_connection_sets_timezone_and_closes_cursor(fake_state):
    manager = make_manager(fake_state)
    conn = fake_state.pool.connections[0]

    manager._prepare_connection(conn)

    assert any("SET TIME ZONE 'UTC'" in sql for sql, _ in conn.executed)


def test_with_db_returns_result_and_returns_connection(fake_state):
    manager = make_manager(fake_state)

    result = manager.with_db(lambda conn: "ok")

    assert result == "ok"
    assert fake_state.pool.putconn_calls >= 1


def test_with_db_converts_psycopg2_error_to_database_error(fake_state):
    manager = make_manager(fake_state)

    def boom(conn):
        raise psycopg2.OperationalError("boom")

    with pytest.raises(DatabaseError) as exc:
        manager.with_db(boom)

    assert "数据库错误" in str(exc.value)
    assert fake_state.pool.putconn_calls >= 1


# =========================
# register_device
# =========================

def test_register_device_inserts_new_device_and_returns_metadata(fake_state):
    manager = make_manager(fake_state)

    result = manager.register_device("aa:bb:cc:dd:ee:01", register_payload())

    row = fake_state.devices["aa:bb:cc:dd:ee:01"]

    assert result["mac"] == "aa:bb:cc:dd:ee:01"
    assert result["isNew"] is True
    assert result["heartbeatIntervalSec"] == 60
    assert result["observedMacs"] == ["aa:bb:cc:dd:ee:01", "11:22:33:44:55:66"]
    assert result["pairedCandidateMacs"] == ["11:22:33:44:55:66"]

    assert row["phone"] == "13708800655"
    assert row["hostname"] == "unit-device"
    assert row["model"] == "QuantClaw-Test"
    assert row["firmware_version"] == "1.0.0"
    assert row["ip"] == "192.168.1.100"
    assert row["ssid"] == "unit-wifi"
    assert row["status"] == "unknown"
    assert row["internet_available"] is False
    assert row["ttyd_enabled"] is True
    assert row["ttyd_port"] == 7681


def test_register_device_updates_existing_device_and_preserves_phone_when_blank(fake_state):
    manager = make_manager(fake_state)
    manager.register_device("aa:bb:cc:dd:ee:01", register_payload(phone="13708800655"))

    result = manager.register_device(
        "aa:bb:cc:dd:ee:01",
        register_payload(
            phone="",
            hostname="updated-device",
            firmwareVersion="2.0.0",
            ip="192.168.1.200",
            ttydEnabled=False,
        ),
    )

    row = fake_state.devices["aa:bb:cc:dd:ee:01"]

    assert result["isNew"] is False
    assert row["phone"] == "13708800655"
    assert row["hostname"] == "updated-device"
    assert row["firmware_version"] == "2.0.0"
    assert row["ip"] == "192.168.1.200"
    assert row["ttyd_enabled"] is False


def test_register_device_truncates_long_fields(fake_state):
    manager = make_manager(fake_state)
    manager.register_device(
        "aa:bb:cc:dd:ee:01",
        register_payload(
            phone="1" * 30,
            hostname="h" * 200,
            model="m" * 200,
            firmwareVersion="f" * 100,
            ip="i" * 100,
            ssid="s" * 200,
            mdnsHost="d" * 200,
            accessScope="a" * 100,
        ),
    )

    row = fake_state.devices["aa:bb:cc:dd:ee:01"]

    assert len(row["phone"]) == 20
    assert len(row["hostname"]) == 128
    assert len(row["model"]) == 128
    assert len(row["firmware_version"]) == 64
    assert len(row["ip"]) == 64
    assert len(row["ssid"]) == 128
    assert len(row["mdns_host"]) == 128
    assert len(row["access_scope"]) == 32


# =========================
# process_heartbeat
# =========================

def test_process_heartbeat_updates_existing_device(fake_state):
    manager = make_manager(fake_state)
    manager.register_device("aa:bb:cc:dd:ee:01", register_payload())

    error, data = manager.process_heartbeat("aa:bb:cc:dd:ee:01", heartbeat_payload())

    row = fake_state.devices["aa:bb:cc:dd:ee:01"]

    assert error is None
    assert data["nextHeartbeatIntervalSec"] == 60
    assert data["observedMacs"] == ["aa:bb:cc:dd:ee:01", "11:22:33:44:55:66"]
    assert data["pairedCandidateMacs"] == ["11:22:33:44:55:66"]

    assert row["status"] == "online"
    assert row["internet_available"] is True
    assert row["firmware_version"] == "1.0.1"
    assert row["ip"] == "192.168.1.101"
    assert row["ssid"] == "heartbeat-wifi"
    assert row["ttyd_enabled"] is True


def test_process_heartbeat_implicitly_creates_unknown_device_when_allowed(fake_state):
    manager = make_manager(fake_state, heartbeat_allow_implicit=True)

    error, data = manager.process_heartbeat("aa:bb:cc:dd:ee:02", heartbeat_payload())

    row = fake_state.devices["aa:bb:cc:dd:ee:02"]

    assert error is None
    assert data["nextHeartbeatIntervalSec"] == 60
    assert row["hostname"] == ""
    assert row["model"] == ""
    assert row["status"] == "online"
    assert row["internet_available"] is True


def test_process_heartbeat_rejects_unknown_device_when_implicit_disabled(fake_state):
    manager = make_manager(fake_state, heartbeat_allow_implicit=False)

    error, data = manager.process_heartbeat("aa:bb:cc:dd:ee:03", heartbeat_payload())

    assert error == {"code": 1005, "message": "device not found", "data": None}
    assert data is None
    assert "aa:bb:cc:dd:ee:03" not in fake_state.devices


# =========================
# list / pairing
# =========================

def test_get_devices_list_returns_all_devices_and_online_counts(fake_state):
    manager = make_manager(fake_state)
    manager.register_device("aa:bb:cc:dd:ee:01", register_payload(phone="13708800655"))
    manager.process_heartbeat("aa:bb:cc:dd:ee:01", heartbeat_payload(phone="13708800655"))

    manager.register_device("aa:bb:cc:dd:ee:02", register_payload(phone="18800000000", ip="192.168.1.102"))
    fake_state.devices["aa:bb:cc:dd:ee:02"]["last_seen_at"] = datetime.now(timezone.utc) - timedelta(seconds=999)

    result = manager.get_devices_list()

    assert result["totalKnownCount"] == 2
    assert result["pairedCount"] == 1
    assert result["pairCount"] == 1
    assert result["paired_count"] == 1
    assert len(result["devices"]) == 2
    assert len(result["pairedDevices"]) == 1
    assert result["pairedDevices"][0]["mac"] == "aa:bb:cc:dd:ee:01"


def test_get_devices_list_filters_by_phone(fake_state):
    manager = make_manager(fake_state)
    manager.register_device("aa:bb:cc:dd:ee:01", register_payload(phone="13708800655"))
    manager.register_device("aa:bb:cc:dd:ee:02", register_payload(phone="18800000000", ip="192.168.1.102"))

    result = manager.get_devices_list(user_phone="13708800655")

    assert result["totalKnownCount"] == 1
    assert result["devices"][0]["mac"] == "aa:bb:cc:dd:ee:01"


def test_get_pairing_snapshot_excludes_self_loopback_and_stale_devices(fake_state):
    manager = make_manager(fake_state)

    manager.register_device("aa:bb:cc:dd:ee:01", register_payload(ip="192.168.1.101"))
    manager.process_heartbeat("aa:bb:cc:dd:ee:01", heartbeat_payload(ip="192.168.1.101"))

    manager.register_device("aa:bb:cc:dd:ee:02", register_payload(ip="192.168.1.102"))
    manager.process_heartbeat("aa:bb:cc:dd:ee:02", heartbeat_payload(ip="192.168.1.102"))

    manager.register_device("aa:bb:cc:dd:ee:03", register_payload(ip="127.0.0.1"))
    manager.process_heartbeat("aa:bb:cc:dd:ee:03", heartbeat_payload(ip="127.0.0.1"))

    manager.register_device("aa:bb:cc:dd:ee:04", register_payload(ip="192.168.1.104"))
    fake_state.devices["aa:bb:cc:dd:ee:04"]["last_seen_at"] = datetime.now(timezone.utc) - timedelta(seconds=999)

    result = manager.get_pairing_snapshot(
        "aa:bb:cc:dd:ee:01",
        observed_macs=["aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:99"],
    )

    paired_macs = {device["mac"] for device in result["pairedDevices"]}

    assert "aa:bb:cc:dd:ee:01" not in paired_macs
    assert "aa:bb:cc:dd:ee:02" in paired_macs
    assert "aa:bb:cc:dd:ee:03" not in paired_macs
    assert "aa:bb:cc:dd:ee:04" not in paired_macs
    assert "aa:bb:cc:dd:ee:99" in paired_macs
    assert result["observedMacs"] == ["aa:bb:cc:dd:ee:01", "aa:bb:cc:dd:ee:99"]


# =========================
# status / health
# =========================

def test_get_registration_status_returns_not_registered_for_missing_device(fake_state):
    manager = make_manager(fake_state)

    result = manager.get_registration_status("aa:bb:cc:dd:ee:ff")

    assert result == {"registered": False, "device": None}


def test_get_registration_status_returns_device_for_existing_device(fake_state):
    manager = make_manager(fake_state)
    manager.register_device("aa:bb:cc:dd:ee:01", register_payload())
    manager.process_heartbeat("aa:bb:cc:dd:ee:01", heartbeat_payload())

    result = manager.get_registration_status("aa:bb:cc:dd:ee:01")

    assert result["registered"] is True
    assert result["device"]["mac"] == "aa:bb:cc:dd:ee:01"
    assert result["device"]["isOnline"] is True


def test_get_heartbeat_status_returns_unknown_for_missing_device(fake_state):
    manager = make_manager(fake_state)

    result = manager.get_heartbeat_status("aa:bb:cc:dd:ee:ff")

    assert result == {"online": False, "lastSeenAt": None, "status": "unknown"}


def test_get_heartbeat_status_returns_online_and_age_for_recent_device(fake_state):
    manager = make_manager(fake_state)
    manager.register_device("aa:bb:cc:dd:ee:01", register_payload())
    manager.process_heartbeat("aa:bb:cc:dd:ee:01", heartbeat_payload())

    result = manager.get_heartbeat_status("aa:bb:cc:dd:ee:01")

    assert result["online"] is True
    assert result["status"] == "online"
    assert result["internetAvailable"] is True
    assert result["lastIp"] == "192.168.1.101"
    assert isinstance(result["secondsSinceLastHeartbeat"], int)


def test_get_heartbeat_status_returns_offline_for_stale_device(fake_state):
    manager = make_manager(fake_state)
    manager.register_device("aa:bb:cc:dd:ee:01", register_payload())
    manager.process_heartbeat("aa:bb:cc:dd:ee:01", heartbeat_payload())
    fake_state.devices["aa:bb:cc:dd:ee:01"]["last_seen_at"] = datetime.now(timezone.utc) - timedelta(seconds=999)

    result = manager.get_heartbeat_status("aa:bb:cc:dd:ee:01")

    assert result["online"] is False
    assert result["status"] == "online"


def test_health_check_returns_connected_and_device_count(fake_state):
    manager = make_manager(fake_state)
    manager.register_device("aa:bb:cc:dd:ee:01", register_payload())

    result = manager.health_check()

    assert result["connected"] is True
    assert result["device_count"] == 1
    assert result["path"] == "postgresql://localhost:5432/quantclaw"


def test_health_check_returns_error_when_database_fails(fake_state):
    manager = make_manager(fake_state)

    def broken_with_db(fn):
        raise DatabaseError("fake database error")

    manager.with_db = broken_with_db

    result = manager.health_check()

    assert result["connected"] is False
    assert "fake database error" in result["error"]
