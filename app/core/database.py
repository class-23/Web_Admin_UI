"""
数据库连接模块
主库 PostgreSQL — 用户、认证
配置库 SQLite — 设备配置（独立存储，可离线携带）
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings

# ===== 主库（PostgreSQL）=====
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)


class Base(DeclarativeBase):
    """主库模型基类 — users 等"""
    pass


# ===== 配置库（SQLite）=====
_db_dir = os.path.dirname(settings.SETTINGS_DB_PATH)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)

settings_engine = create_engine(
    settings.SETTINGS_DB_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DEBUG,
)

SettingsSessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=settings_engine)


class SettingsBase(DeclarativeBase):
    """配置库模型基类 — device_configs 等"""
    pass


# ===== 依赖注入 =====

def get_db():
    """主库会话（FastAPI 依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings_db():
    """配置库会话（FastAPI 依赖注入）"""
    db = SettingsSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化所有数据库表结构"""
    Base.metadata.create_all(bind=engine)
    SettingsBase.metadata.create_all(bind=settings_engine)
