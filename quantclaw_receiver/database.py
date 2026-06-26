"""
QuantClaw 数据库操作模块 — DEPRECATED FACADE

⚠️ DEPRECATED: canonical 实现位于 `app.utils.quantclaw_receiver.database`。
   此处保留 legacy psycopg2 直连实现，仅为兼容 `main.py` 与历史测试。
   Phase-3 将随 `main.py` 迁移一并删除。详见 `docs/adr/0001-architecture-unification.md`。

封装所有与PostgreSQL数据库的交互，提供线程安全的数据库访问。
"""

from __future__ import annotations

import psycopg2
import psycopg2.extras
from psycopg2 import sql
from psycopg2.pool import ThreadedConnectionPool
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from .config import QuantClawConfig
from .exceptions import DatabaseError
from .utils import (
    ONLINE_HEARTBEAT_TIMEOUT_SEC,
    as_bool,
    as_int,
    format_server_time,
    row_to_device,
    server_time_str,
)


DEVICE_COLUMNS = {
    "user_id": "INTEGER NOT NULL DEFAULT 1",
    "phone": "VARCHAR(20) NOT NULL DEFAULT ''",
    "device_name": "VARCHAR(100) NOT NULL DEFAULT ''",
    "mac": "VARCHAR(17) NOT NULL",
    "hostname": "VARCHAR(128) NOT NULL DEFAULT ''",
    "model": "VARCHAR(128) NOT NULL DEFAULT ''",
    "firmware_version": "VARCHAR(64) NOT NULL DEFAULT ''",
    "ip": "VARCHAR(64) NOT NULL DEFAULT ''",
    "ssid": "VARCHAR(128) NOT NULL DEFAULT ''",
    "internet_available": "BOOLEAN NOT NULL DEFAULT FALSE",
    "status": "device_status NOT NULL DEFAULT 'registered'",
    "heartbeat_interval_sec": "INTEGER NOT NULL DEFAULT 60",
    "ttyd_enabled": "BOOLEAN NOT NULL DEFAULT FALSE",
    "ttyd_port": "INTEGER NOT NULL DEFAULT 7681",
    "mdns_host": "VARCHAR(128) NOT NULL DEFAULT ''",
    "http_port": "INTEGER NOT NULL DEFAULT 80",
    "access_scope": "VARCHAR(32) NOT NULL DEFAULT 'lan'",
    "interfaces_json": "TEXT",
    "device_secret": "VARCHAR(100) NOT NULL DEFAULT ''",
    "is_quant": "BOOLEAN NOT NULL DEFAULT FALSE",
    "paired_at": "TIMESTAMPTZ",
    "first_seen_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "last_seen_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "created_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
    "updated_at": "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
}

TIMESTAMPTZ_DEVICE_COLUMNS = ("paired_at", "first_seen_at", "last_seen_at", "created_at", "updated_at")


class DatabaseManager:
    """数据库管理器，提供线程安全的数据库操作"""

    def __init__(self, config: QuantClawConfig):
        self.config = config
        self._pool = ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=config.pg_host,
            port=config.pg_port,
            user=config.pg_user,
            password=config.pg_password,
            dbname=config.pg_dbname,
        )
        self._schema_initialized = False

    def ensure_schema(self) -> None:
        """确保旧版设备表 schema 已初始化，可供 main.py 旧路径直接使用。"""
        if self._schema_initialized:
            return

        conn = self._pool.getconn()
        try:
            cur = conn.cursor()
            cur.execute("SET TIME ZONE 'UTC'")
            self._ensure_device_status_enum(cur)
            self._ensure_devices_table(cur)
            self._ensure_devices_columns(cur)
            self._ensure_devices_indexes(cur)
            conn.commit()
            cur.close()
            self._schema_initialized = True
        except psycopg2.Error:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def _ensure_device_status_enum(self, cur) -> None:
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'device_status') THEN
                    CREATE TYPE device_status AS ENUM ('registered', 'online', 'offline', 'disconnected', 'unknown');
                END IF;
            END
            $$;
            """
        )

    def _ensure_devices_table(self, cur) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL DEFAULT 1,
                phone VARCHAR(20) NOT NULL DEFAULT '',
                device_name VARCHAR(100) NOT NULL DEFAULT '',
                mac VARCHAR(17) NOT NULL,
                hostname VARCHAR(128) NOT NULL DEFAULT '',
                model VARCHAR(128) NOT NULL DEFAULT '',
                firmware_version VARCHAR(64) NOT NULL DEFAULT '',
                ip VARCHAR(64) NOT NULL DEFAULT '',
                ssid VARCHAR(128) NOT NULL DEFAULT '',
                internet_available BOOLEAN NOT NULL DEFAULT FALSE,
                status device_status NOT NULL DEFAULT 'registered',
                heartbeat_interval_sec INTEGER NOT NULL DEFAULT 60,
                ttyd_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                ttyd_port INTEGER NOT NULL DEFAULT 7681,
                mdns_host VARCHAR(128) NOT NULL DEFAULT '',
                http_port INTEGER NOT NULL DEFAULT 80,
                access_scope VARCHAR(32) NOT NULL DEFAULT 'lan',
                interfaces_json TEXT,
                device_secret VARCHAR(100) NOT NULL DEFAULT '',
                is_quant BOOLEAN NOT NULL DEFAULT FALSE,
                paired_at TIMESTAMPTZ,
                first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

    def _ensure_devices_columns(self, cur) -> None:
        for column_name, column_definition in DEVICE_COLUMNS.items():
            cur.execute(
                sql.SQL("ALTER TABLE devices ADD COLUMN IF NOT EXISTS {column_name} {column_definition}").format(
                    column_name=sql.Identifier(column_name),
                    column_definition=sql.SQL(column_definition),
                )
            )

        for column_name in TIMESTAMPTZ_DEVICE_COLUMNS:
            cur.execute(
                """
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'devices'
                  AND column_name = %s
                """,
                (column_name,),
            )
            row = cur.fetchone()
            if row and row[0] == "timestamp without time zone":
                cur.execute(
                    sql.SQL(
                        """
                        ALTER TABLE devices
                        ALTER COLUMN {column_name}
                        TYPE TIMESTAMPTZ
                        USING {column_name} AT TIME ZONE 'UTC'
                        """
                    ).format(column_name=sql.Identifier(column_name))
                )

        cur.execute("ALTER TABLE devices ALTER COLUMN mac SET NOT NULL")
        cur.execute("ALTER TABLE devices ALTER COLUMN user_id SET DEFAULT 1")

    def _ensure_devices_indexes(self, cur) -> None:
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS devices_mac_unique ON devices (mac)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_user_last_seen ON devices (user_id, last_seen_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_status ON devices (status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_devices_phone ON devices (phone)")

    def _prepare_connection(self, conn) -> None:
        cur = conn.cursor()
        try:
            cur.execute("SET TIME ZONE 'UTC'")
        finally:
            cur.close()

    def with_db(self, fn: Callable[[Any], Any]) -> Any:
        """线程安全的数据库操作包装器"""
        self.ensure_schema()
        conn = self._pool.getconn()
        try:
            self._prepare_connection(conn)
            return fn(conn)
        except psycopg2.Error as e:
            raise DatabaseError(f"数据库错误: {str(e)}") from e
        finally:
            self._pool.putconn(conn)

    def register_device(self, mac: str, payload: dict[str, Any]) -> dict[str, Any]:
        """注册设备"""
        st = server_time_str()

        def _register(conn) -> dict[str, Any]:
            cur = conn.cursor()
            ttyd = as_bool(payload.get("ttydEnabled"))
            ttyd_port = as_int(payload.get("ttydPort"), 7681)
            http_port = as_int(payload.get("httpPort"), 80)

            phone = str(payload.get("phone", ""))[:20]

            cur.execute(
                """
                INSERT INTO devices (
                  mac, phone, hostname, model, firmware_version, ip, ssid,
                  internet_available, status, heartbeat_interval_sec,
                  ttyd_enabled, ttyd_port, mdns_host, http_port, access_scope,
                  first_seen_at, last_seen_at, created_at, updated_at, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, 'unknown', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (mac) DO UPDATE SET
                  phone = CASE WHEN EXCLUDED.phone = '' THEN devices.phone ELSE EXCLUDED.phone END,
                  hostname = EXCLUDED.hostname,
                  model = EXCLUDED.model,
                  firmware_version = EXCLUDED.firmware_version,
                  ip = EXCLUDED.ip,
                  ssid = EXCLUDED.ssid,
                  ttyd_enabled = EXCLUDED.ttyd_enabled,
                  ttyd_port = EXCLUDED.ttyd_port,
                  mdns_host = EXCLUDED.mdns_host,
                  http_port = EXCLUDED.http_port,
                  access_scope = EXCLUDED.access_scope,
                  heartbeat_interval_sec = EXCLUDED.heartbeat_interval_sec,
                  last_seen_at = EXCLUDED.last_seen_at,
                  updated_at = EXCLUDED.updated_at
                RETURNING (xmax = 0) AS is_new
                """,
                (
                    mac,
                    phone,
                    str(payload.get("hostname", ""))[:128],
                    str(payload.get("model", ""))[:128],
                    str(payload.get("firmwareVersion", ""))[:64],
                    str(payload.get("ip", ""))[:64],
                    str(payload.get("ssid", ""))[:128],
                    self.config.heartbeat_interval_sec,
                    ttyd,
                    ttyd_port,
                    str(payload.get("mdnsHost", ""))[:128],
                    http_port,
                    str(payload.get("accessScope", "lan"))[:32],
                    st, st, st, st, 1,
                ),
            )
            row = cur.fetchone()
            is_new = bool(row[0]) if row else True
            conn.commit()

            return {
                "mac": mac,
                "isNew": is_new,
                "heartbeatIntervalSec": self.config.heartbeat_interval_sec,
                "serverTime": st,
                "observedMacs": payload.get("_observedMacs", []),
                "pairedCandidateMacs": [x for x in payload.get("_observedMacs", []) if x != mac],
            }

        return self.with_db(_register)

    def process_heartbeat(self, mac: str, payload: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
        """处理设备心跳"""
        st = server_time_str()

        def _heartbeat(conn) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM devices WHERE mac = %s AND user_id = %s",
                (mac, 1),
            )
            exists = cur.fetchone() is not None
            ttyd = as_bool(payload.get("ttydEnabled"))
            ttyd_port = as_int(payload.get("ttydPort"), 7681)
            http_port = as_int(payload.get("httpPort"), 80)
            inet = as_bool(payload.get("internetAvailable"))

            phone = str(payload.get("phone", ""))[:20]

            if not exists:
                if not self.config.heartbeat_allow_implicit:
                    return {"code": 1005, "message": "device not found", "data": None}, None

                cur.execute(
                    """
                    INSERT INTO devices (
                      mac, phone, hostname, model, firmware_version, ip, ssid,
                      internet_available, status, heartbeat_interval_sec,
                      ttyd_enabled, ttyd_port, mdns_host, http_port, access_scope,
                      first_seen_at, last_seen_at, created_at, updated_at, user_id
                    ) VALUES (%s, %s, '', '', %s, %s, %s, %s, %s, 60, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (mac) DO UPDATE SET
                      phone = CASE WHEN EXCLUDED.phone = '' THEN devices.phone ELSE EXCLUDED.phone END,
                      firmware_version = EXCLUDED.firmware_version,
                      ip = EXCLUDED.ip,
                      ssid = EXCLUDED.ssid,
                      internet_available = EXCLUDED.internet_available,
                      status = EXCLUDED.status,
                      ttyd_enabled = EXCLUDED.ttyd_enabled,
                      ttyd_port = EXCLUDED.ttyd_port,
                      mdns_host = EXCLUDED.mdns_host,
                      http_port = EXCLUDED.http_port,
                      access_scope = EXCLUDED.access_scope,
                      last_seen_at = EXCLUDED.last_seen_at,
                      updated_at = EXCLUDED.updated_at
                    """,
                    (
                        mac,
                        phone,
                        str(payload.get("firmwareVersion", ""))[:64],
                        str(payload.get("ip", ""))[:64],
                        str(payload.get("ssid", ""))[:128],
                        inet,
                        str(payload.get("status", "unknown"))[:32],
                        ttyd, ttyd_port,
                        str(payload.get("mdnsHost", ""))[:128],
                        http_port,
                        str(payload.get("accessScope", "lan"))[:32],
                        st, st, st, st, 1,
                    ),
                )
                conn.commit()
            else:
                cur.execute(
                    """
                    UPDATE devices SET
                      phone = CASE WHEN %s = '' THEN phone ELSE %s END,
                      last_seen_at = %s, ip = %s, ssid = %s,
                      internet_available = %s, status = %s, firmware_version = %s,
                      ttyd_enabled = %s, ttyd_port = %s, mdns_host = %s, http_port = %s,
                      access_scope = %s, updated_at = %s
                    WHERE mac = %s AND user_id = %s
                    """,
                    (
                        phone, phone,
                        st,
                        str(payload.get("ip", ""))[:64],
                        str(payload.get("ssid", ""))[:128],
                        inet,
                        str(payload.get("status", "unknown"))[:32],
                        str(payload.get("firmwareVersion", ""))[:64],
                        ttyd, ttyd_port,
                        str(payload.get("mdnsHost", ""))[:128],
                        http_port,
                        str(payload.get("accessScope", "lan"))[:32],
                        st, mac, 1,
                    ),
                )
                conn.commit()

            return None, {
                "nextHeartbeatIntervalSec": self.config.next_heartbeat_interval_sec,
                "serverTime": st,
                "observedMacs": payload.get("_observedMacs", []),
                "pairedCandidateMacs": [x for x in payload.get("_observedMacs", []) if x != mac],
            }

        return self.with_db(_heartbeat)

    def get_devices_list(self, user_phone: str = "") -> dict[str, Any]:
        """获取设备列表，按用户手机号过滤"""
        def _scan(conn) -> dict[str, Any]:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if user_phone:
                cur.execute(
                    """
                    SELECT mac, phone, hostname, model, firmware_version, ip, ssid,
                           internet_available, status, ttyd_enabled, ttyd_port, mdns_host,
                           http_port, access_scope, last_seen_at
                    FROM devices
                    WHERE phone = %s
                    ORDER BY last_seen_at DESC
                    """,
                    (user_phone,),
                )
            else:
                cur.execute(
                    """
                    SELECT mac, phone, hostname, model, firmware_version, ip, ssid,
                           internet_available, status, ttyd_enabled, ttyd_port, mdns_host,
                           http_port, access_scope, last_seen_at
                    FROM devices
                    ORDER BY last_seen_at DESC
                    """,
                )
            rows = cur.fetchall()

            now = datetime.now(timezone.utc)
            device_list = [row_to_device(dict(row), now) for row in rows]
            online_devices = [d for d in device_list if d["isOnline"]]

            return {
                "scanMode": "loop",
                "scanIntervalSec": 5,
                "pairedCount": len(online_devices),
                "pairCount": len(online_devices),
                "paired_count": len(online_devices),
                "totalKnownCount": len(device_list),
                "pairedDevices": online_devices,
                "devices": device_list,
            }

        return self.with_db(_scan)

    def get_pairing_snapshot(self, self_mac: str, observed_macs: Optional[list[str]] = None) -> dict[str, Any]:
        """获取配对快照"""
        def _snapshot(conn) -> dict[str, Any]:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT mac, phone, hostname, model, firmware_version, ip, ssid,
                       internet_available, status, ttyd_enabled, ttyd_port, mdns_host,
                       http_port, access_scope, last_seen_at
                FROM devices
                WHERE access_scope = 'lan'
                ORDER BY last_seen_at DESC
                """
            )
            rows = cur.fetchall()

            now = datetime.now(timezone.utc)
            devices = [row_to_device(dict(row), now) for row in rows]
            paired_devices = [
                d for d in devices
                if d["mac"] != self_mac and d["lastIp"] and not d["lastIp"].startswith("127.")
            ]

            known_macs = {d["mac"] for d in devices}
            for mac in observed_macs or []:
                if mac == self_mac or mac in known_macs:
                    continue
                paired_devices.append(
                    {
                        "mac": mac,
                        "hostname": "",
                        "model": "",
                        "firmwareVersion": "",
                        "lastIp": "",
                        "lastSsid": "",
                        "internetAvailable": False,
                        "status": "observed",
                        "lastSeenAt": server_time_str(),
                        "isOnline": True,
                        "ttydEnabled": False,
                        "ttydPort": 7681,
                        "mdnsHost": "",
                        "httpPort": 80,
                        "accessScope": "lan",
                        "httpUrl": "",
                        "mdnsUrl": "",
                        "ttydUrl": "",
                        "ssh": "",
                        "sshMdns": "",
                    }
                )

            online_paired = [d for d in paired_devices if d["isOnline"]]

            return {
                "scanMode": "loop",
                "scanIntervalSec": 5,
                "observedMacs": observed_macs or [],
                "pairedCount": len(online_paired),
                "pairCount": len(online_paired),
                "paired_count": len(online_paired),
                "totalKnownCount": len(devices),
                "pairedDevices": online_paired,
                "devices": devices,
            }

        return self.with_db(_snapshot)

    def get_registration_status(self, device_id: str) -> dict[str, Any]:
        """获取设备注册状态"""
        def _get_status(conn) -> dict[str, Any]:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT mac, phone, hostname, model, firmware_version, ip, ssid,
                       internet_available, status, last_seen_at, created_at
                FROM devices
                WHERE mac = %s
                """,
                (device_id,),
            )
            row = cur.fetchone()

            if not row:
                return {"registered": False, "device": None}

            now = datetime.now(timezone.utc)
            device = row_to_device(dict(row), now)

            return {"registered": True, "device": device}

        return self.with_db(_get_status)

    def get_heartbeat_status(self, device_id: str) -> dict[str, Any]:
        """获取设备心跳状态"""
        def _get_status(conn) -> dict[str, Any]:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT mac, last_seen_at, status, internet_available, ip
                FROM devices
                WHERE mac = %s
                """,
                (device_id,),
            )
            row = cur.fetchone()

            if not row:
                return {"online": False, "lastSeenAt": None, "status": "unknown"}

            from .utils import parse_server_time
            last_seen = parse_server_time(row["last_seen_at"])
            now = datetime.now(timezone.utc)
            age = int((now - last_seen).total_seconds()) if last_seen is not None else None
            is_online = age is not None and age <= ONLINE_HEARTBEAT_TIMEOUT_SEC

            return {
                "online": is_online,
                "lastSeenAt": format_server_time(row["last_seen_at"]),
                "status": row["status"],
                "internetAvailable": bool(row["internet_available"]),
                "lastIp": row["ip"],
                "secondsSinceLastHeartbeat": age,
            }

        return self.with_db(_get_status)

    def delete_device(self, mac: str) -> dict[str, Any]:
        """删除指定 MAC 的设备"""
        def _delete(conn):
            cur = conn.cursor()
            cur.execute("DELETE FROM devices WHERE mac = %s", (mac,))
            conn.commit()
            return {"deleted": cur.rowcount > 0}
        return self.with_db(_delete)

    def health_check(self) -> dict[str, Any]:
        """数据库健康检查"""
        try:
            def _check(conn) -> dict[str, Any]:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT COUNT(*) as cnt FROM devices")
                row = cur.fetchone()
                return {"connected": True, "device_count": row["cnt"]}

            result = self.with_db(_check)
            return {
                "path": f"postgresql://{self.config.pg_host}:{self.config.pg_port}/{self.config.pg_dbname}",
                "connected": result["connected"],
                "device_count": result["device_count"],
            }
        except Exception as e:
            return {
                "path": f"postgresql://{self.config.pg_host}:{self.config.pg_port}/{self.config.pg_dbname}",
                "connected": False,
                "error": str(e),
            }
