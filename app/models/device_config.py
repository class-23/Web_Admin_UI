"""
设备配置模型（SQLite 配置库）
独立于主库，可随设备离线携带
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON
from app.core.database import SettingsBase


class DeviceConfig(SettingsBase):
    __tablename__ = "device_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, nullable=False, index=True)  # 无 FK，跨库引用
    llm_provider = Column(String(50), default="deepseek")
    llm_model = Column(String(100), default="deepseek-v3")
    api_key_encrypted = Column(Text)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2048)
    timeout_seconds = Column(Integer, default=30)
    wifi_ssid = Column(String(100))
    wifi_password_encrypted = Column(Text)
    language = Column(String(10), default="auto")
    system_prompt = Column(Text)
    skills_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<DeviceConfig(id={self.id}, device_id={self.device_id})>"
