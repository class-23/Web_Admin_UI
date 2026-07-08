
"""
QuantClaw 自定义异常模块

定义所有业务相关的异常类，提供统一的错误处理机制。
"""

from __future__ import annotations

from typing import Any, Optional


class QuantClawError(Exception):
    """QuantClaw 基础异常类"""
    
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"[{code}] {message}")
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {"code": self.code, "message": self.message, "data": self.data}


class InvalidJsonError(QuantClawError):
    """无效的JSON数据"""
    def __init__(self, message: str = "invalid json body"):
        super().__init__(1001, message)


class MissingFieldError(QuantClawError):
    """缺少必填字段"""
    def __init__(self, field: str):
        super().__init__(1001, f"missing required field: {field}")


class InvalidSignatureError(QuantClawError):
    """无效的签名"""
    def __init__(self):
        super().__init__(1003, "invalid signature")


class InvalidTimestampError(QuantClawError):
    """无效的时间戳"""
    def __init__(self, message: str = "timestamp invalid or expired"):
        super().__init__(1004, message)


class DeviceNotFoundError(QuantClawError):
    """设备未找到"""
    def __init__(self):
        super().__init__(1005, "device not found")


class DatabaseError(QuantClawError):
    """数据库操作错误"""
    def __init__(self, message: str = "internal database error"):
        super().__init__(1006, message)


class InvalidMacError(QuantClawError):
    """无效的MAC地址"""
    def __init__(self):
        super().__init__(1002, "invalid mac")