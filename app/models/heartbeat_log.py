"""
心跳日志模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, BigInteger, DateTime, ForeignKey
from app.core.database import Base


class HeartbeatLog(Base):
    __tablename__ = "heartbeat_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address = Column(String(45))
    status = Column(String(20))
    internet_available = Column(Boolean)
    uptime_seconds = Column(BigInteger)
    memory_usage = Column(Float)
    cpu_usage = Column(Float)
    reported_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<HeartbeatLog(id={self.id}, device_id={self.device_id})>"
