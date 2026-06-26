"""
login/config.py — DEPRECATED FACADE / 接缝层

⚠️ DEPRECATED: 权威配置已迁移到 `app.core.config.settings`（基于 pydantic-settings）。
   本文件仅作为向后兼容的接缝，按以下规则转发：
     1) settings 中存在且**默认值与旧版完全一致**的字段 → 直接转发；
     2) settings 中存在但默认值不同的字段 → 仍读环境变量（保持旧行为）；
     3) settings 中不存在的字段（Redis / SMS / Cookie 等） → 保留 os.getenv 实现。
   Phase-2 将删除本文件，统一指向 `app.core.config.settings`。
   详见 `docs/adr/0001-architecture-unification.md`。
"""
import os
from app.core.config import settings as _settings

# ===== PostgreSQL — settings 默认值匹配，直接转发 =====
PG_HOST = _settings.PG_HOST                # 双方默认 "localhost"
PG_PORT = _settings.PG_PORT                # 双方默认 5432
PG_PASSWORD = _settings.PG_PASSWORD        # 双方默认 ""

# ===== PostgreSQL — settings 默认值不同，保留旧默认值（仅读 env） =====
# settings.PG_USER 默认 "quantclaw"，legacy 默认 "postgres"，行为差异需保留
PG_USER = os.getenv("PG_USER", "postgres")
# settings.PG_NAME 默认 "quantclaw_db"，legacy 默认 "quantclaw"，行为差异需保留
PG_DBNAME = os.getenv("PG_DBNAME", os.getenv("PG_NAME", "quantclaw"))

# ===== 连接池（settings 未覆盖） =====
PG_POOL_MIN = int(os.getenv("PG_POOL_MIN", "2"))
PG_POOL_MAX = int(os.getenv("PG_POOL_MAX", "10"))

# ===== Redis（settings 未覆盖） =====
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# ===== JWT — settings 默认值匹配，直接转发 =====
SECRET_KEY = _settings.JWT_SECRET          # 注意：双方默认值不同（见 ADR-0001 §6），
                                            #   但 env 覆盖后行为一致；env 未设时各自有 fallback
ALGORITHM = _settings.JWT_ALGORITHM         # 双方默认 "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _settings.JWT_EXPIRE_MINUTES  # 双方默认 1440

# ===== 验证码 TTL（settings 未覆盖） =====
VERIFICATION_CODE_EXPIRE_SECONDS = 300
VERIFICATION_CODE_RESEND_SECONDS = 60

# ===== SMS（settings 未覆盖） =====
SMS_API_URL = "https://data.tangledup-ai.com/api/send-sms"
SMS_TEMPLATE_CODE = "SMS_493295002"
SMS_SIGN_NAME = "叠加态科技云南"

# ===== Cookie（settings 未覆盖） =====
AUTH_COOKIE_NAME = "auth_token"
AUTH_COOKIE_MAX_AGE = 2592000
