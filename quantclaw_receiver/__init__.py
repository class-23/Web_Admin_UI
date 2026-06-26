"""
QuantClaw 设备管理服务封装模块 — DEPRECATED FACADE

⚠️ DEPRECATED: 此包为 legacy 接缝层，已迁移到 `app.utils.quantclaw_receiver`。
   本包保留仅为兼容 `main.py` 旧调用方与历史测试，新代码请直接 import canonical 路径。
   详见 `docs/adr/0001-architecture-unification.md`。

提供设备注册、心跳处理、设备列表查询等功能，
完全兼容原脚本的所有行为和数据格式。

使用示例:
    from quantclaw_receiver import QuantClawDeviceManager, QuantClawConfig
    
    # 使用默认配置
    device_manager = QuantClawDeviceManager()
    
    # 自定义配置
    config = QuantClawConfig(
        db_path="./my_devices.sqlite",
        udp_enabled=True,
        allow_insecure=True
    )
    device_manager = QuantClawDeviceManager(config)
"""

from .config import QuantClawConfig
from .database import DatabaseManager
from .device_manager import QuantClawDeviceManager
from .exceptions import (
    DatabaseError, DeviceNotFoundError, InvalidJsonError,
    InvalidMacError, InvalidSignatureError, InvalidTimestampError,
    MissingFieldError, QuantClawError
)
from .udp_receiver import UDPBroadcastReceiver
from .utils import (
    HEARTBEAT_FIELDS, REGISTER_FIELDS, extract_macs,
    make_sign, normalize_mac, normalize_signature,
    parse_utc_timestamp, server_time_str
)

__all__ = [
    "QuantClawConfig",
    "DatabaseManager",
    "QuantClawDeviceManager",
    "QuantClawError",
    "InvalidJsonError",
    "MissingFieldError",
    "InvalidSignatureError",
    "InvalidTimestampError",
    "DeviceNotFoundError",
    "DatabaseError",
    "InvalidMacError",
    "UDPBroadcastReceiver",
    "make_sign",
    "normalize_signature",
    "parse_utc_timestamp",
    "normalize_mac",
    "extract_macs",
    "server_time_str",
    "REGISTER_FIELDS",
    "HEARTBEAT_FIELDS",
]

__version__ = "1.0.0"