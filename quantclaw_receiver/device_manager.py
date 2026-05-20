"""
QuantClaw 核心设备管理类

提供统一的设备管理接口，整合数据库操作和UDP接收器。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import Request

from .config import QuantClawConfig
from .database import DatabaseManager
from .exceptions import (
    InvalidJsonError, InvalidSignatureError, InvalidTimestampError,
    MissingFieldError, QuantClawError
)
from .udp_receiver import UDPBroadcastReceiver
from .utils import (
    HEARTBEAT_FIELDS, REGISTER_FIELDS, client_ip_from_headers,
    first_value, make_sign, normalize_payload_defaults, normalize_signature,
    parse_text_body, parse_utc_timestamp, pick
)


logger = logging.getLogger("quantclaw.manager")


class QuantClawDeviceManager:
    """
    QuantClaw 设备管理器
    
    提供设备注册、心跳处理、设备列表查询等核心功能。
    完全兼容原脚本的所有行为和数据格式。
    """
    
    def __init__(self, config: Optional[QuantClawConfig] = None):
        """
        初始化设备管理器
        
        Args:
            config: 配置对象，如不提供则使用默认配置
        """
        self.config = config or QuantClawConfig()
        self.config.validate()
        
        self.db_manager = DatabaseManager(self.config)
        self.udp_receiver = UDPBroadcastReceiver(self.config, self.db_manager)
        
        logger.info("QuantClaw 设备管理器已初始化")
        logger.info(f"数据库: PostgreSQL {self.config.pg_host}:{self.config.pg_port}/{self.config.pg_dbname}")
        logger.info(f"UDP接收器: {'启用' if self.config.udp_enabled else '禁用'}")
    
    async def startup(self) -> None:
        """启动设备管理器（在FastAPI lifespan中调用）"""
        self.db_manager.ensure_schema()
        if self.config.udp_enabled:
            self.udp_receiver.start()
        logger.info("QuantClaw 设备管理器已启动")
    
    async def shutdown(self) -> None:
        """关闭设备管理器（在FastAPI lifespan中调用）"""
        self.udp_receiver.stop()
        logger.info("QuantClaw 设备管理器已关闭")
    
    async def validate_request(self, path: str, request: Request, body_bytes: bytes) -> dict[str, Any]:
        """
        验证并解析HTTP请求
        
        Args:
            path: 请求路径
            request: FastAPI Request对象
            body_bytes: 请求体字节
            
        Returns:
            解析并标准化后的请求载荷
            
        Raises:
            QuantClawError: 请求验证失败时抛出
        """
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

        # 合并查询参数
        from urllib.parse import parse_qs, urlparse
        query = parse_qs(urlparse(str(request.url)).query, keep_blank_values=True)
        for k, v in query.items():
            payload.setdefault(k, first_value(v))

        # 签名验证
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
            
            import hmac
            if not any(hmac.compare_digest(expected, sig) for expected in expected_sigs):
                logger.warning(
                    "[签名诊断] paths=%s timestamp=%s body_sha256=%s got=%s",
                    candidate_paths, ts_header,
                    hashlib.sha256(body_raw).hexdigest(),
                    sig[:12],
                )
                raise InvalidSignatureError()

        # 标准化载荷
        _, payload = normalize_payload_defaults(path, payload, client_ip)

        # 验证必填字段
        if not self.config.allow_insecure:
            fields = REGISTER_FIELDS if path == "/api/device/register" else HEARTBEAT_FIELDS
            for k in fields:
                if k not in payload:
                    raise MissingFieldError(k)

        return payload
    
    async def register_device(self, request: Request) -> dict[str, Any]:
        """
        处理设备注册请求
        
        Args:
            request: FastAPI Request对象
            
        Returns:
            注册结果
        """
        body_bytes = await request.body()
        client_ip = request.client.host if request.client else "127.0.0.1"

        if body_bytes:
            logger.info("[注册请求] from %s | body=%s", 
                       client_ip, body_bytes.decode("utf-8", errors="replace")[:2000])
        else:
            query = str(request.url.query)
            if query:
                logger.info("[注册请求] from %s | query=%s", client_ip, query[:500])

        # 空请求体且允许不安全模式时，返回设备列表
        if not body_bytes and self.config.allow_insecure:
            return await self.get_devices_list()

        payload = await self.validate_request("/api/device/register", request, body_bytes)
        mac_norm = payload["mac"]

        logger.info(
            "[已接收注册] from %s | MAC=%s observed=%s host=%s model=%s fw=%s ip=%s ssid=%s",
            client_ip, mac_norm, payload.get("_observedMacs", []),
            payload.get("hostname", ""), payload.get("model", ""),
            payload.get("firmwareVersion", ""), payload.get("ip", ""),
            payload.get("ssid", ""),
        )

        # 注册设备
        register_data = self.db_manager.register_device(mac_norm, payload)
        
        # 获取配对快照
        pairing_data = self.db_manager.get_pairing_snapshot(mac_norm, payload.get("_observedMacs", []))
        
        # 合并结果
        result = {**register_data, **pairing_data}
        
        return result
    
    async def get_registration_status(self, device_id: str) -> dict[str, Any]:
        """
        获取设备注册状态
        
        Args:
            device_id: 设备MAC地址
            
        Returns:
            设备注册状态
        """
        return self.db_manager.get_registration_status(device_id)
    
    async def process_heartbeat(self, request: Request) -> dict[str, Any]:
        """
        处理设备心跳请求
        
        Args:
            request: FastAPI Request对象
            
        Returns:
            心跳处理结果
        """
        body_bytes = await request.body()
        client_ip = request.client.host if request.client else "127.0.0.1"

        if body_bytes:
            logger.info("[心跳请求] from %s | body=%s", 
                       client_ip, body_bytes.decode("utf-8", errors="replace")[:2000])

        # 空请求体且允许不安全模式时，返回设备列表
        if not body_bytes and self.config.allow_insecure:
            return await self.get_devices_list()

        payload = await self.validate_request("/api/device/heartbeat", request, body_bytes)
        mac_norm = payload["mac"]

        logger.info(
            "[已接收心跳] from %s | MAC=%s observed=%s fw=%s ip=%s ssid=%s status=%s internet=%s",
            client_ip, mac_norm, payload.get("_observedMacs", []),
            payload.get("firmwareVersion", ""), payload.get("ip", ""),
            payload.get("ssid", ""), payload.get("status", ""),
            payload.get("internetAvailable", ""),
        )

        # 处理心跳
        hb_err, hb_data = self.db_manager.process_heartbeat(mac_norm, payload)
        
        if hb_err is not None:
            return hb_err
        
        # 获取配对快照
        pairing_data = self.db_manager.get_pairing_snapshot(mac_norm, payload.get("_observedMacs", []))
        
        # 合并结果
        result = {**hb_data, **pairing_data}
        
        return result
    
    async def get_heartbeat_status(self, device_id: str) -> dict[str, Any]:
        """
        获取设备心跳状态
        
        Args:
            device_id: 设备MAC地址
            
        Returns:
            设备心跳状态
        """
        return self.db_manager.get_heartbeat_status(device_id)
    
    async def create_device(self, request: Request) -> dict[str, Any]:
        """
        创建设备（与register_device功能相同，为了API兼容性）
        
        Args:
            request: FastAPI Request对象
            
        Returns:
            创建设备结果
        """
        return await self.register_device(request)
    
    async def get_devices_list(self) -> dict[str, Any]:
        """
        获取所有设备列表
        
        Returns:
            设备列表
        """
        return self.db_manager.get_devices_list()
    
    async def health_check(self) -> dict[str, Any]:
        """
        健康检查
        
        Returns:
            健康状态信息
        """
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
