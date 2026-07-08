import os

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DBNAME = os.getenv("PG_DBNAME", os.getenv("PG_NAME", "quantclaw"))
PG_POOL_MIN = int(os.getenv("PG_POOL_MIN", "2"))
PG_POOL_MAX = int(os.getenv("PG_POOL_MAX", "10"))

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

SECRET_KEY = "your-secret-key-for-jwt"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

VERIFICATION_CODE_EXPIRE_SECONDS = 300
VERIFICATION_CODE_RESEND_SECONDS = 60

SMS_API_URL = "https://data.tangledup-ai.com/api/send-sms"
SMS_TEMPLATE_CODE = "SMS_493295002"
SMS_SIGN_NAME = "叠加态科技云南"

AUTH_COOKIE_NAME = "auth_token"
AUTH_COOKIE_MAX_AGE = 2592000

# ---------- 微信开放平台 ----------
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")
WECHAT_REDIRECT_URI = os.getenv("WECHAT_REDIRECT_URI", "http://localhost:8082/api/wechat/callback")
WECHAT_QR_SIGN_SECRET = os.getenv("WECHAT_QR_SIGN_SECRET", "")
