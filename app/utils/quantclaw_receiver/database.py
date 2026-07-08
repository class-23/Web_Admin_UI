"""
QuantClaw 数据库操作模块

封装设备数据的持久化，基于 SQLAlchemy 操作 PostgreSQL 主库和 SQLite 配置库。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from .config import QuantClawConfig
from .exceptions import DatabaseError
from .utils import ONLINE_HEARTBEAT_TIMEOUT_SEC, as_bool, as_int, server_time_str

from app.models.device import Device
from app.models.device_config import DeviceConfig
from app.core.security import encrypt_sensitive_data, decrypt_sensitive_data

logger = logging.getLogger("QuantClaw")

_STATUS_FROM_QCR = {
    "unknown": "registered",
    "online": "online",
    "offline": "offline",
    "disconnected": "disconnected",
    "registered": "registered",
}


def _map_status(raw: str) -> str:
    s = (raw or "unknown").strip().lower()
    return _STATUS_FROM_QCR.get(s, "registered")


def _device_to_row(device: Device, now: datetime) -> dict[str, Any]:
    last_hb = device.last_heartbeat_at
    online_by_time = False
    if last_hb is not None:
        if last_hb.tzinfo is None:
            last_hb = last_hb.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        online_by_time = (now - last_hb).total_seconds() <= ONLINE_HEARTBEAT_TIMEOUT_SEC
    is_online = online_by_time
    interfaces = None
    if device.interfaces_json:
        try:
            interfaces = json.loads(device.interfaces_json)
        except (json.JSONDecodeError, TypeError):
            interfaces = None

    return {
        "id": device.id,
        "mac": device.mac_address,
        "hostname": device.hostname or "",
        "model": device.model or "",
        "firmwareVersion": device.firmware_version or "",
        "lastIp": device.ip_address or "",
        "lastSsid": device.ssid or "",
        "internetAvailable": device.internet_available or False,
        "status": device.status,
        "isOnline": is_online,
        "ttydEnabled": device.ttyd_enabled or False,
        "ttydPort": device.ttyd_port or 7681,
        "mdnsHost": device.mdns_host or "",
        "httpPort": device.http_port or 80,
        "accessScope": device.access_scope or "lan",
        "lastSeenAt": device.last_heartbeat_at.strftime("%Y-%m-%dT%H:%M:%SZ") if device.last_heartbeat_at else "",
        "firstSeenAt": device.registered_at.strftime("%Y-%m-%dT%H:%M:%SZ") if device.registered_at else "",
        "createdAt": device.registered_at.strftime("%Y-%m-%dT%H:%M:%SZ") if device.registered_at else "",
        "updatedAt": device.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ") if device.updated_at else "",
        "httpUrl": f"http://{device.ip_address}:{device.http_port}" if device.ip_address else "",
        "mdnsUrl": f"http://{device.mdns_host}.local" if device.mdns_host else "",
        "ttydUrl": f"http://{device.ip_address}:{device.ttyd_port}" if device.ip_address else "",
        "ssh": "",
        "sshMdns": "",
        "interfaces": interfaces,
    }


def _apply_device_fields(device: Device, payload: dict[str, Any], is_new: bool,
                         config: QuantClawConfig, st: str) -> None:
    device.hostname = str(payload.get("hostname", ""))[:128] if is_new or "hostname" in payload else device.hostname
    device.model = str(payload.get("model", ""))[:128] if is_new or "model" in payload else device.model

    if "firmwareVersion" in payload:
        device.firmware_version = str(payload["firmwareVersion"])[:64]

    if "ip" in payload:
        device.ip_address = str(payload["ip"])[:64]

    if "ssid" in payload:
        device.ssid = str(payload["ssid"])[:128]

    if "internetAvailable" in payload:
        device.internet_available = as_bool(payload.get("internetAvailable"))

    if "status" in payload:
        device.status = _map_status(str(payload.get("status", "")))

    if "ttydEnabled" in payload:
        device.ttyd_enabled = as_bool(payload.get("ttydEnabled"))

    if "ttydPort" in payload:
        device.ttyd_port = as_int(payload.get("ttydPort"), 7681)

    if "mdnsHost" in payload:
        device.mdns_host = str(payload["mdnsHost"])[:128]

    if "httpPort" in payload:
        device.http_port = as_int(payload.get("httpPort"), 80)

    if "accessScope" in payload:
        device.access_scope = str(payload["accessScope"])[:32]

    if "interfaces" in payload and payload["interfaces"] is not None:
        device.interfaces_json = json.dumps(payload["interfaces"], ensure_ascii=False)

    device.heartbeat_interval_sec = config.heartbeat_interval_sec
    device.last_heartbeat_at = datetime.now(timezone.utc)
    device.updated_at = datetime.now(timezone.utc)


class DatabaseManager:

    def __init__(self, config: QuantClawConfig,
                 session_factory: Callable[[], Session],
                 settings_session_factory: Optional[Callable[[], Session]] = None):
        self.config = config
        self._session_factory = session_factory
        self._settings_session_factory = settings_session_factory

    # ------------------------------------------------------------------
    # 设备注册
    # ------------------------------------------------------------------
    def register_device(self, mac: str, payload: dict[str, Any]) -> dict[str, Any]:
        st = server_time_str()
        db = self._session_factory()
        try:
            device = db.query(Device).filter(Device.mac_address == mac).first()
            is_new = device is None
            now = datetime.now(timezone.utc)

            if is_new:
                device = Device(
                    mac_address=mac,
                    status="registered",
                    registered_at=now,
                )
                db.add(device)
                db.flush()

            _apply_device_fields(device, payload, is_new, self.config, st)
            db.commit()
            db.refresh(device)

            observed = payload.get("_observedMacs", [])
            return {
                "mac": mac,
                "isNew": is_new,
                "heartbeatIntervalSec": self.config.heartbeat_interval_sec,
                "serverTime": st,
                "observedMacs": observed,
                "pairedCandidateMacs": [x for x in observed if x != mac],
            }
        except Exception as e:
            db.rollback()
            logger.error(f"设备注册失败 mac={mac}: {e}")
            raise DatabaseError(f"设备注册失败: {str(e)}") from e
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 设备心跳
    # ------------------------------------------------------------------
    def process_heartbeat(self, mac: str, payload: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
        st = server_time_str()
        db = self._session_factory()
        try:
            device = db.query(Device).filter(Device.mac_address == mac).first()
            now = datetime.now(timezone.utc)

            if not device:
                if not self.config.heartbeat_allow_implicit:
                    return {"code": 1005, "message": "device not found", "data": None}, None

                device = Device(
                    mac_address=mac,
                    registered_at=now,
                    status="registered",
                )
                db.add(device)
                db.flush()

            _apply_device_fields(device, payload, False, self.config, st)
            db.commit()

            observed = payload.get("_observedMacs", [])
            return None, {
                "nextHeartbeatIntervalSec": self.config.next_heartbeat_interval_sec,
                "serverTime": st,
                "observedMacs": observed,
                "pairedCandidateMacs": [x for x in observed if x != mac],
            }
        except Exception as e:
            db.rollback()
            logger.error(f"心跳处理失败 mac={mac}: {e}")
            raise DatabaseError(f"心跳处理失败: {str(e)}") from e
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 配对快照
    # ------------------------------------------------------------------
    def get_pairing_snapshot(self, self_mac: str,
                             observed_macs: Optional[list[str]] = None) -> dict[str, Any]:
        """获取配对发现快照：返回 LAN 候选设备 + 观察到的 MAC"""
        db = self._session_factory()
        try:
            rows = (
                db.query(Device)
                .filter(Device.access_scope == "lan")
                .order_by(Device.last_heartbeat_at.desc())
                .all()
            )
            now = datetime.now(timezone.utc)
            devices = [_device_to_row(d, now) for d in rows]
            paired_devices = [
                d for d in devices
                if d["mac"] != self_mac
                and d["lastIp"]
                and not d["lastIp"].startswith("127.")
            ]

            known_macs = {d["mac"] for d in devices}
            for mac in observed_macs or []:
                if mac == self_mac or mac in known_macs:
                    continue
                paired_devices.append({
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
                    "interfaces": None,
                })

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
        except Exception as e:
            logger.error(f"获取配对快照失败: {e}")
            raise DatabaseError(f"获取配对快照失败: {str(e)}") from e
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 设备列表
    # ------------------------------------------------------------------
    def get_devices_list(self) -> dict[str, Any]:
        db = self._session_factory()
        try:
            rows = db.query(Device).order_by(Device.last_heartbeat_at.desc()).all()
            now = datetime.now(timezone.utc)
            device_list = [_device_to_row(d, now) for d in rows]
            online = [d for d in device_list if d["isOnline"]]

            return {
                "scanMode": "loop",
                "scanIntervalSec": 5,
                "pairedCount": len(online),
                "pairCount": len(online),
                "paired_count": len(online),
                "totalKnownCount": len(device_list),
                "pairedDevices": online,
                "devices": device_list,
            }
        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            raise DatabaseError(f"获取设备列表失败: {str(e)}") from e
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 注册状态
    # ------------------------------------------------------------------
    def get_registration_status(self, device_id: str) -> dict[str, Any]:
        db = self._session_factory()
        try:
            device = db.query(Device).filter(Device.mac_address == device_id).first()
            if not device:
                return {"registered": False, "device": None}

            now = datetime.now(timezone.utc)
            return {"registered": True, "device": _device_to_row(device, now)}
        except Exception as e:
            logger.error(f"查询注册状态失败 mac={device_id}: {e}")
            raise DatabaseError(f"查询注册状态失败: {str(e)}") from e
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 心跳状态
    # ------------------------------------------------------------------
    def get_heartbeat_status(self, device_id: str) -> dict[str, Any]:
        db = self._session_factory()
        try:
            device = db.query(Device).filter(Device.mac_address == device_id).first()
            if not device:
                return {"online": False, "lastSeenAt": None, "status": "unknown"}

            now = datetime.now(timezone.utc)
            age = None
            if device.last_heartbeat_at:
                last_hb = device.last_heartbeat_at
                if last_hb.tzinfo is None:
                    last_hb = last_hb.replace(tzinfo=timezone.utc)
                age = int((now - last_hb).total_seconds())
            is_online = age is not None and age <= ONLINE_HEARTBEAT_TIMEOUT_SEC

            return {
                "online": is_online,
                "lastSeenAt": device.last_heartbeat_at.strftime("%Y-%m-%dT%H:%M:%SZ") if device.last_heartbeat_at else None,
                "status": device.status,
                "internetAvailable": device.internet_available or False,
                "lastIp": device.ip_address or "",
                "secondsSinceLastHeartbeat": age,
            }
        except Exception as e:
            logger.error(f"查询心跳状态失败 mac={device_id}: {e}")
            raise DatabaseError(f"查询心跳状态失败: {str(e)}") from e
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    def health_check(self) -> dict[str, Any]:
        try:
            db = self._session_factory()
            try:
                cnt = db.query(Device).count()
                return {"connected": True, "device_count": cnt}
            finally:
                db.close()
        except Exception as e:
            return {"connected": False, "error": str(e)}

    # ------------------------------------------------------------------
    # 设备配置 (SQLite 配置库)
    # ------------------------------------------------------------------
    def get_device_config(self, device_id: int) -> dict[str, Any]:
        if not self._settings_session_factory:
            return self._default_config()

        sdb = self._settings_session_factory()
        try:
            config = sdb.query(DeviceConfig).filter(DeviceConfig.device_id == device_id).first()
            if not config:
                return self._default_config()

            result = {
                "llm_provider": config.llm_provider,
                "llm_model": config.llm_model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "wifi_ssid": config.wifi_ssid,
                "language": config.language,
                "system_prompt": config.system_prompt,
                "skills": config.skills_json,
            }

            if config.api_key_encrypted:
                try:
                    result["api_key"] = decrypt_sensitive_data(config.api_key_encrypted)
                except Exception:
                    result["api_key"] = None
            else:
                result["api_key"] = None

            if config.wifi_password_encrypted:
                try:
                    result["wifi_password"] = decrypt_sensitive_data(config.wifi_password_encrypted)
                except Exception:
                    result["wifi_password"] = None
            else:
                result["wifi_password"] = None

            return result
        finally:
            sdb.close()

    def update_device_config(self, device_id: int, config_data: dict[str, Any]) -> dict[str, Any]:
        if not self._settings_session_factory:
            return {"status": "error", "message": "settings database not available"}

        sdb = self._settings_session_factory()
        try:
            config = sdb.query(DeviceConfig).filter(DeviceConfig.device_id == device_id).first()
            if not config:
                config = DeviceConfig(device_id=device_id)
                sdb.add(config)

            if "llm_provider" in config_data:
                config.llm_provider = config_data["llm_provider"]
            if "llm_model" in config_data:
                config.llm_model = config_data["llm_model"]
            if "api_key" in config_data:
                config.api_key_encrypted = encrypt_sensitive_data(config_data["api_key"]) if config_data["api_key"] else None
            if "temperature" in config_data:
                config.temperature = config_data["temperature"]
            if "max_tokens" in config_data:
                config.max_tokens = config_data["max_tokens"]
            if "wifi_ssid" in config_data:
                config.wifi_ssid = config_data["wifi_ssid"]
            if "wifi_password" in config_data:
                config.wifi_password_encrypted = encrypt_sensitive_data(config_data["wifi_password"]) if config_data["wifi_password"] else None
            if "language" in config_data:
                config.language = config_data["language"]
            if "system_prompt" in config_data:
                config.system_prompt = config_data["system_prompt"]

            sdb.commit()
            return {"status": "updated", "message": "配置已保存，设备下次心跳时将拉取最新配置"}
        except Exception as e:
            sdb.rollback()
            logger.error(f"更新设备配置失败 device_id={device_id}: {e}")
            raise DatabaseError(f"更新设备配置失败: {str(e)}") from e
        finally:
            sdb.close()

    @staticmethod
    def _default_config() -> dict[str, Any]:
        return {
            "llm_provider": "deepseek",
            "llm_model": "deepseek-v3",
            "api_key": None,
            "temperature": 0.7,
            "max_tokens": 2048,
            "wifi_ssid": None,
            "wifi_password": None,
            "language": "auto",
        }
