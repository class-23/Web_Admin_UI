"""
设备相关 Schema
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class DeviceRegister(BaseModel):
    """设备注册请求"""
    mac: str = Field(..., description="MAC地址")
    hostname: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    ssid: Optional[str] = None
    ip: Optional[str] = None
    interfaces: Optional[List[dict]] = None
    ttyd_enabled: bool = False
    ttyd_port: int = 7681
    mdns_host: Optional[str] = None
    http_port: int = 80
    access_scope: str = "lan"
    timestamp: Optional[str] = None
    pair_code: Optional[str] = Field(None, description="配对码")
    secret: Optional[str] = Field(None, description="设备密钥")


class DeviceResponse(BaseModel):
    """设备响应"""
    id: int
    user_id: Optional[int] = None
    device_name: Optional[str] = None
    mac_address: str
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    model: Optional[str] = None
    firmware_version: Optional[str] = None
    status: str
    is_quant: bool = False
    paired_at: Optional[datetime] = None
    last_heartbeat_at: Optional[datetime] = None
    registered_at: datetime

    class Config:
        from_attributes = True


class DeviceConfigUpdate(BaseModel):
    """设备配置更新请求"""
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    language: Optional[str] = None
    system_prompt: Optional[str] = None


class DeviceConfigResponse(BaseModel):
    """设备配置响应"""
    llm_provider: str
    llm_model: str
    api_key: Optional[str] = None
    temperature: float
    max_tokens: int
    wifi_ssid: Optional[str] = None
    wifi_password: Optional[str] = None
    language: str
    system_prompt: Optional[str] = None
    skills: Optional[dict] = None


class PairCodeResponse(BaseModel):
    """配对码响应"""
    pair_code: str
    expires_in: int


class HeartbeatRequest(BaseModel):
    """心跳请求"""
    mac: str
    ip: Optional[str] = None
    status: str = "online"
    internet_available: bool = True
    firmware_version: Optional[str] = None
    ssid: Optional[str] = None
    interfaces: Optional[List[dict]] = None
    ttyd_enabled: bool = False
    ttyd_port: int = 7681
    mdns_host: Optional[str] = None
    http_port: int = 80
    access_scope: str = "lan"
    uptime_seconds: Optional[int] = None
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None
