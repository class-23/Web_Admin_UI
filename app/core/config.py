"""
应用配置模块
从环境变量和 .env 文件加载配置
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量读取"""

    # 应用
    APP_NAME: str = "QuantClaw Admin UI"
    APP_PORT: int = 8081
    DEBUG: bool = False

    # PostgreSQL
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_USER: str = "quantclaw"
    PG_PASSWORD: str = ""
    PG_NAME: str = "quantclaw_db"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.PG_USER}:{self.PG_PASSWORD}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_NAME}"

    # JWT
    JWT_SECRET: str = "CHANGE_ME_RANDOM_STRING_AT_LEAST_32_CHARS"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # 设备密钥
    DEVICE_SECRET: str = "quant123456"

    # 签名校验
    ALLOW_INSECURE: bool = True
    MAX_SKEW_SEC: int = 300

    # 心跳配置
    HEARTBEAT_INTERVAL_SEC: int = 60
    NEXT_HEARTBEAT_INTERVAL_SEC: int = 60
    HEARTBEAT_ALLOW_IMPLICIT: bool = True

    # SSH
    SSH_HOST: str = "127.0.0.1"
    SSH_PORT: int = 22
    SSH_USERNAME: str = "root"
    SSH_PASSWORD: str = ""

    # QuantClaw
    QUANTCLAW_API_URL: str = ""
    QUANTCLAW_API_KEY: str = ""

    # UDP
    UDP_ENABLED: bool = True
    UDP_PORT: int = 12345
    UDP_RESPONSE_PORT: int = 12346

    # AES 加密（设备配置敏感字段）
    ENCRYPTION_KEY: str = ""

    # SQLite 配置库（设备配置独立存储）
    SETTINGS_DB_PATH: str = "runtime/settings.sqlite"

    @property
    def SETTINGS_DB_URL(self) -> str:
        return f"sqlite:///{self.SETTINGS_DB_PATH}"

    HOST_PORT: int = 3308

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
