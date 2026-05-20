"""
设备模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    device_name = Column(String(100))
    mac_address = Column(String(17), unique=True, nullable=False, index=True)
    ip_address = Column(String(45))
    hostname = Column(String(100))
    model = Column(String(50), default="rpi5")
    firmware_version = Column(String(50))
    ssid = Column(String(100))
    access_scope = Column(String(20), default="local")
    internet_available = Column(Boolean, default=False)
    http_port = Column(Integer, default=80)
    ttyd_enabled = Column(Boolean, default=False)
    ttyd_port = Column(Integer, default=7681)
    mdns_host = Column(String(100))
    interfaces_json = Column(Text, nullable=True)
    status = Column(Enum("registered", "online", "offline", "disconnected", name="device_status"), default="registered")
    heartbeat_interval_sec = Column(Integer, default=60)
    is_quant = Column(Boolean, default=False)
    device_secret = Column(String(100))
    paired_at = Column(DateTime, nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系（DeviceConfig 在 SQLite 配置库，无跨库 relationship）
    user = relationship("User", backref="devices")
    heartbeat_logs = relationship("HeartbeatLog", backref="device", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Device(id={self.id}, mac='{self.mac_address}')>"
