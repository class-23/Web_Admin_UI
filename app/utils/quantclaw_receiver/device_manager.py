"""
QuantClaw 核心设备管理类

提供统一的设备管理接口，整合数据库操作和UDP接收器。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from .config import QuantClawConfig
from .database import DatabaseManager
from .exceptions import (
    InvalidJsonError, InvalidSignatureError, InvalidTimestampError,
    MissingFieldError, QuantClawError
)
from .udp_receiver import UDPBroadcastReceiver
from .utils import (
    HEARTBEAT_FIELDS, REGISTER_FIELDS, client_ip_from_headers,
    make_sign, normalize_payload_defaults, normalize_signature,
    parse_text_body, parse_utc_timestamp, pick
)

logger = logging.getLogger("quantclaw.manager")


def _first_value(v):
    if isinstance(v, list):
        return v[0] if v else ""
    return v


class QuantClawDeviceManager:

    def __init__(self, config: Optional[QuantClawConfig] = None,
                 session_factory: Optional[Callable[[], Session]] = None,
                 settings_session_factory: Optional[Callable[[], Session]] = None):
        self.config = config or QuantClawConfig()
        self.config.validate()

        self.db_manager = DatabaseManager(
            self.config, session_factory, settings_session_factory
        )
        self.udp_receiver = UDPBroadcastReceiver(self.config, self.db_manager)

        logger.info("QuantClaw 设备管理器已初始化")
        logger.info(f"UDP接收器: {'启用' if self.config.udp_enabled else '禁用'}")

    async def startup(self) -> None:
        if self.config.udp_enabled:
            self.udp_receiver.start()
        logger.info("QuantClaw 设备管理器已启动")

    async def shutdown(self) -> None:
        self.udp_receiver.stop()
        logger.info("QuantClaw 设备管理器已关闭")

    async def validate_request(self, path: str, request: Request,
                               body_bytes: bytes) -> dict[str, Any]:
        hdrs = {k: v for k, v in request.headers.items()}
        client_ip = client_ip_from_headers(hdrs, request.client.host if request.client else "127.0.0.1")

        ct = hdrs.get("content-type", "") or hdrs.get("Content-Type", "")
        if "application/json" in ct.lower():
            try:
                payload = json.loads(body_bytes.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise InvalidJsonError()
            if not isinstance(payload, dict):
                raise InvalidJsonError("body must be a json object")
        else:
            payload = parse_text_body(body_bytes)

        from urllib.parse import parse_qs, urlparse
        query = parse_qs(urlparse(str(request.url)).query, keep_blank_values=True)
        for k, v in query.items():
            payload.setdefault(k, _first_value(v))

        ts_header = hdrs.get("x-timestamp") or hdrs.get("X-Timestamp") or str(pick(payload, "timestamp", "ts", default=""))
        sig = normalize_signature(hdrs.get("x-signature") or hdrs.get("X-Signature", ""))

        if not self.config.allow_insecure:
            if not ts_header or not sig:
                raise QuantClawError(1001, "missing X-Timestamp or X-Signature")

            req_ts = parse_utc_timestamp(ts_header)
            if req_ts is None:
                raise InvalidTimestampError("invalid timestamp")

            now_dt = datetime.now(timezone.utc)
            skew = abs((now_dt - req_ts).total_seconds())
            if skew > self.config.max_skew_sec:
                raise InvalidTimestampError()

            if pick(payload, "timestamp", "ts", default="") != ts_header:
                raise InvalidTimestampError("timestamp mismatch")

            candidate_paths = (path,)
            body_raw = body_bytes
            expected_sigs = [
                make_sign("POST", candidate, ts_header, body_raw, self.config.device_secret)
                for candidate in candidate_paths
            ]

            if not any(hmac.compare_digest(expected, sig) for expected in expected_sigs):
                logger.warning(
                    "[签名诊断] paths=%s timestamp=%s body_sha256=%s got=%s",
                    candidate_paths, ts_header,
                    hashlib.sha256(body_raw).hexdigest(),
                    sig[:12],
                )
                raise InvalidSignatureError()

        _, payload = normalize_payload_defaults(path, payload, client_ip)

        if not self.config.allow_insecure:
            fields = REGISTER_FIELDS if path == "/api/device/register" else HEARTBEAT_FIELDS
            for k in fields:
                if k not in payload:
                    raise MissingFieldError(k)

        return payload

    async def register_device(self, request: Request) -> dict[str, Any]:
        body_bytes = await request.body()
        client_ip = request.client.host if request.client else "127.0.0.1"

        if not body_bytes and self.config.allow_insecure:
            return await self.get_devices_list()

        payload = await self.validate_request("/api/device/register", request, body_bytes)
        mac_norm = payload["mac"]

        logger.info(
            "[已接收注册] from %s | MAC=%s host=%s model=%s fw=%s ip=%s",
            client_ip, mac_norm, payload.get("hostname", ""),
            payload.get("model", ""), payload.get("firmwareVersion", ""),
            payload.get("ip", ""),
        )

        register_data = self.db_manager.register_device(mac_norm, payload)
        pairing_data = self.db_manager.get_pairing_snapshot(
            mac_norm, payload.get("_observedMacs", [])
        )
        return {**register_data, **pairing_data}

    async def get_registration_status(self, device_id: str) -> dict[str, Any]:
        return self.db_manager.get_registration_status(device_id)

    async def process_heartbeat(self, request: Request) -> dict[str, Any]:
        body_bytes = await request.body()
        client_ip = request.client.host if request.client else "127.0.0.1"

        if not body_bytes and self.config.allow_insecure:
            return await self.get_devices_list()

        payload = await self.validate_request("/api/device/heartbeat", request, body_bytes)
        mac_norm = payload["mac"]

        logger.info(
            "[已接收心跳] from %s | MAC=%s fw=%s ip=%s ssid=%s status=%s",
            client_ip, mac_norm, payload.get("firmwareVersion", ""),
            payload.get("ip", ""), payload.get("ssid", ""),
            payload.get("status", ""),
        )

        hb_err, hb_data = self.db_manager.process_heartbeat(mac_norm, payload)

        if hb_err is not None:
            return hb_err

        pairing_data = self.db_manager.get_pairing_snapshot(
            mac_norm, payload.get("_observedMacs", [])
        )
        return {**hb_data, **pairing_data}

    async def get_heartbeat_status(self, device_id: str) -> dict[str, Any]:
        return self.db_manager.get_heartbeat_status(device_id)

    async def create_device(self, request: Request) -> dict[str, Any]:
        return await self.register_device(request)

    async def get_devices_list(self) -> dict[str, Any]:
        return self.db_manager.get_devices_list()

    async def health_check(self) -> dict[str, Any]:
        db_status = self.db_manager.health_check()

        return {
            "status": "healthy" if db_status["connected"] else "degraded",
            "database": db_status,
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "allow_insecure": self.config.allow_insecure,
                "hmac_required": not self.config.allow_insecure,
                "udp_broadcast_receiver": {
                    "enabled": self.config.udp_enabled,
                    "listen_port": self.config.udp_bind_port,
                    "response_port": self.config.udp_response_port,
                }
            }
        }
