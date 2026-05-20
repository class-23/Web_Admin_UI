from typing import Optional
from login import config
import redis

_redis = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=config.REDIS_DB,
    decode_responses=True,
)


def store_code(phone: str, code: str):
    _redis.setex(f"sms_code:{phone}", config.VERIFICATION_CODE_EXPIRE_SECONDS, code)
    _redis.setex(f"sms_cooldown:{phone}", config.VERIFICATION_CODE_RESEND_SECONDS, "1")


def get_code(phone: str) -> Optional[str]:
    code = _redis.get(f"sms_code:{phone}")
    if code:
        _redis.delete(f"sms_code:{phone}")
    return code


def can_resend(phone: str) -> bool:
    return not _redis.exists(f"sms_cooldown:{phone}")


def clear_code(phone: str):
    _redis.delete(f"sms_code:{phone}")
