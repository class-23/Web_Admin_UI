"""
安全模块 — JWT 认证 + 密码哈希 + AES 加密
"""
import base64
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# AES 加密 — 用于设备配置中的 API 密钥等敏感字段

def encrypt_sensitive_data(plaintext: str) -> str:
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY 未配置")
    key = base64.b64decode(settings.ENCRYPTION_KEY)
    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(plaintext.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(iv + encrypted).decode("utf-8")


def decrypt_sensitive_data(encrypted_text: str) -> str:
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY 未配置")
    key = base64.b64decode(settings.ENCRYPTION_KEY)
    raw = base64.b64decode(encrypted_text)
    iv = raw[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypted = unpad(cipher.decrypt(raw[16:]), AES.block_size)
    return decrypted.decode("utf-8")
