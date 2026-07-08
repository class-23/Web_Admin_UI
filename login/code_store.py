import time
from typing import Optional
from login import config

_codes: dict[str, tuple[str, float]] = {}       # phone -> (code, expire_at)
_cooldowns: dict[str, float] = {}                # phone -> cooldown_expire_at


def _clean_expired():
    """清理过期的验证码和冷却记录。"""
    now = time.time()
    expired_phones = [p for p, (_, exp) in _codes.items() if exp <= now]
    for p in expired_phones:
        del _codes[p]
    expired_cooldowns = [p for p, exp in _cooldowns.items() if exp <= now]
    for p in expired_cooldowns:
        del _cooldowns[p]


def store_code(phone: str, code: str):
    _clean_expired()
    expire_at = time.time() + config.VERIFICATION_CODE_EXPIRE_SECONDS
    _codes[phone] = (code, expire_at)
    cooldown_at = time.time() + config.VERIFICATION_CODE_RESEND_SECONDS
    _cooldowns[phone] = cooldown_at


def get_code(phone: str) -> Optional[str]:
    _clean_expired()
    entry = _codes.get(phone)
    if entry is None:
        return None
    code, expire_at = entry
    if expire_at <= time.time():
        del _codes[phone]
        return None
    del _codes[phone]
    return code


def peek_code(phone: str) -> Optional[str]:
    """只读取验证码，不消费（不删除）"""
    _clean_expired()
    entry = _codes.get(phone)
    if entry is None:
        return None
    code, expire_at = entry
    if expire_at <= time.time():
        del _codes[phone]
        return None
    return code


def can_resend(phone: str) -> bool:
    _clean_expired()
    cd = _cooldowns.get(phone)
    if cd is None:
        return True
    if cd <= time.time():
        del _cooldowns[phone]
        return True
    return False


def clear_code(phone: str):
    _codes.pop(phone, None)
