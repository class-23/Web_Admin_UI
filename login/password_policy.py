import re

PASSWORD_MAX_BYTES = 72
PASSWORD_MAX_BYTES_MESSAGE = (
    "密码最多支持72字节（约72个英文字符，包含中文或其他特殊字符时上限更低）"
)


def get_password_utf8_length(password: str) -> int:
    return len(password.encode("utf-8"))


def validate_password_max_bytes(password: str) -> str:
    if get_password_utf8_length(password) > PASSWORD_MAX_BYTES:
        raise ValueError(PASSWORD_MAX_BYTES_MESSAGE)
    return password


def validate_register_password(password: str) -> str:
    validate_password_max_bytes(password)
    if len(password) < 8:
        raise ValueError("密码长度至少为8位")
    if not re.search(r"[a-z]", password):
        raise ValueError("密码必须包含小写字母")
    if not re.search(r"[A-Z]", password):
        raise ValueError("密码必须包含大写字母")
    if not re.search(r"\d", password):
        raise ValueError("密码必须包含数字")
    return password


def validate_reset_password(password: str) -> str:
    validate_password_max_bytes(password)
    if len(password) < 8:
        raise ValueError("密码长度至少为8位")
    if not re.search(r"[a-zA-Z]", password):
        raise ValueError("密码必须包含字母")
    if not re.search(r"\d", password):
        raise ValueError("密码必须包含数字")
    if not re.search(r"[^a-zA-Z0-9]", password):
        raise ValueError("密码必须包含特殊符号")
    return password


def validate_change_password(password: str) -> str:
    validate_password_max_bytes(password)
    if len(password) < 8:
        raise ValueError("密码长度至少为8位")
    if not re.search(r"[a-z]", password):
        raise ValueError("密码必须包含小写字母")
    if not re.search(r"[A-Z]", password):
        raise ValueError("密码必须包含大写字母")
    if not re.search(r"\d", password):
        raise ValueError("密码必须包含数字")
    return password
