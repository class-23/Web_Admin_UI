"""
QuantClaw 配置管理模块 — DEPRECATED FACADE

⚠️ DEPRECATED: 此 `QuantClawConfig` 含 legacy `pg_*` 字段（psycopg2 直连）。
   canonical 版本位于 `app.utils.quantclaw_receiver.config`（使用 SQLAlchemy session，
   字段集为 `db_path / heartbeat_interval_sec / udp_* / ...`，无 `pg_*`）。
   此文件保留以兼容 `main.py` 的 `QuantClawConfig(pg_host=...)` 调用；
   Phase-3 将迁移 `main.py` 后删除本文件。详见 `docs/adr/0001-architecture-unification.md`。

提供类型安全的配置类，支持从环境变量和命令行参数加载配置。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class QuantClawConfig:
    """QuantClaw 设备管理服务配置类"""
    
    # 安全配置
    # 注意: device_secret 已废弃，请使用 users 表的 miyao_key 字段替代
    device_secret: str = field(default="quant123456")
    max_skew_sec: int = field(default=300)
    allow_insecure: bool = field(default=True)
    
    # 心跳配置
    heartbeat_interval_sec: int = field(default=60)
    next_heartbeat_interval_sec: int = field(default=60)
    heartbeat_allow_implicit: bool = field(default=True)
    
    # PostgreSQL 数据库配置
    pg_host: str = field(default="localhost")
    pg_port: int = field(default=5432)
    pg_user: str = field(default="quant")
    pg_password: str = field(default="open123456")
    pg_dbname: str = field(default="quantclaw")
    
    # UDP配置
    udp_enabled: bool = field(default=True)
    udp_bind_port: int = field(default=12345)
    udp_response_port: int = field(default=12346)
    
    # 服务器配置
    host: str = field(default="0.0.0.0")
    port: int = field(default=8081)
    
    @classmethod
    def from_env(cls) -> QuantClawConfig:
        """从环境变量加载配置"""
        return cls(
            device_secret=os.environ.get("DEVICE_SECRET", "quant123456"),
            max_skew_sec=int(os.environ.get("MAX_SKEW_SEC", "300")),
            allow_insecure=os.environ.get("ALLOW_INSECURE", "true").lower() == "true",
            heartbeat_interval_sec=int(os.environ.get("HEARTBEAT_INTERVAL", "60")),
            next_heartbeat_interval_sec=int(os.environ.get("NEXT_HEARTBEAT_INTERVAL", "60")),
            heartbeat_allow_implicit=os.environ.get("HEARTBEAT_ALLOW_IMPLICIT", "true").lower() == "true",
            pg_host=os.environ.get("PG_HOST", "localhost"),
            pg_port=int(os.environ.get("PG_PORT", "5432")),
            pg_user=os.environ.get("PG_USER", "quant"),
            pg_password=os.environ.get("PG_PASSWORD", "open123456"),
            pg_dbname=os.environ.get("PG_DBNAME", "quantclaw"),
            udp_enabled=os.environ.get("UDP_ENABLED", "true").lower() == "true",
            udp_bind_port=int(os.environ.get("UDP_BIND_PORT", "12345")),
            udp_response_port=int(os.environ.get("UDP_RESPONSE_PORT", "12346")),
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8081")),
        )
    
    def validate(self) -> None:
        """验证配置有效性"""
        if self.max_skew_sec < 0:
            raise ValueError("max_skew_sec 不能为负数")
        if self.heartbeat_interval_sec < 1:
            raise ValueError("heartbeat_interval_sec 必须大于0")
        if self.next_heartbeat_interval_sec < 1:
            raise ValueError("next_heartbeat_interval_sec 必须大于0")
        if self.udp_bind_port < 1 or self.udp_bind_port > 65535:
            raise ValueError("udp_bind_port 必须在1-65535之间")
        if self.udp_response_port < 1 or self.udp_response_port > 65535:
            raise ValueError("udp_response_port 必须在1-65535之间")
        if self.port < 1 or self.port > 65535:
            raise ValueError("port 必须在1-65535之间")