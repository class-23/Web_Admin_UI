from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Response, Request, HTTPException, Depends
import psycopg2.extras
from login import config
from login.database import get_db
from login.password_policy import PASSWORD_MAX_BYTES_MESSAGE, validate_password_max_bytes
from login.time_utils import is_newer_than_issued_at
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    validate_password_max_bytes(password)
    try:
        return pwd_context.hash(password)
    except ValueError as exc:
        if "72 bytes" in str(exc):
            raise ValueError(PASSWORD_MAX_BYTES_MESSAGE) from exc
        raise


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({"iat": now})
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)


def set_auth_cookie(response: Response, token_data: dict) -> str:
    token = create_access_token(data=token_data)
    response.set_cookie(
        key=config.AUTH_COOKIE_NAME,
        value=token,
        max_age=config.AUTH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        secure=False,
    )
    return token


def clear_auth_cookie(response: Response):
    response.delete_cookie(
        key=config.AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=False,
    )


def get_current_user_from_cookie(request: Request, db):
    token = request.cookies.get(config.AUTH_COOKIE_NAME)
    if token is None:
        return None
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
        user = cur.fetchone()
        cur.close()
        if user is None:
            return None
        iat = payload.get("iat")
        if is_newer_than_issued_at(user["password_changed_at"], iat):
            return None
        return user
    except JWTError:
        return None


def require_auth(request: Request, response: Response, db = Depends(get_db)):
    token = request.cookies.get(config.AUTH_COOKIE_NAME)
    if token is None:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
    except JWTError:
        clear_auth_cookie(response)
        raise HTTPException(status_code=401, detail="登录凭证无效，请重新登录")

    user_id = payload.get("sub")
    if user_id is None:
        clear_auth_cookie(response)
        raise HTTPException(status_code=401, detail="登录凭证无效，请重新登录")

    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
    user = cur.fetchone()
    cur.close()
    if user is None:
        clear_auth_cookie(response)
        raise HTTPException(status_code=401, detail="用户不存在，请重新登录")

    iat = payload.get("iat")
    if is_newer_than_issued_at(user["password_changed_at"], iat):
        clear_auth_cookie(response)
        raise HTTPException(status_code=401, detail="密码已变更，请重新登录")

    return user


def require_auth_or_api_key(request: Request, response: Response, db=Depends(get_db)):
    """
    双重认证：优先 Cookie 登录，失败后尝试手机号 + API Key。
    支持 Header（X-API-Key / X-Phone）和 Query 参数（api_key / phone）两种方式。
    """
    # 1. 尝试 Cookie 认证
    token = request.cookies.get(config.AUTH_COOKIE_NAME)
    if token:
        try:
            payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
                user = cur.fetchone()
                cur.close()
                if user and not is_newer_than_issued_at(user["password_changed_at"], payload.get("iat")):
                    return user
        except JWTError:
            pass

    # 2. 尝试 API Key + 手机号
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    phone = request.headers.get("X-Phone") or request.query_params.get("phone")

    if not api_key or api_key != settings.QUERY_API_KEY:
        raise HTTPException(status_code=401, detail="认证失败：无效的 API Key")

    if not phone:
        raise HTTPException(status_code=400, detail="缺少手机号参数(phone)")

    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()
    cur.close()

    if user is None:
        raise HTTPException(status_code=404, detail="该手机号未注册")

    return user


async def verify_api_key_and_phone(
    request: Request,
    db=Depends(get_db),
):
    """
    Combined API Key + Phone 认证（用于 Swagger UI 单一认证按钮）
    """
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    phone = request.headers.get("X-Phone") or request.query_params.get("phone")

    if not api_key or api_key != settings.QUERY_API_KEY:
        raise HTTPException(status_code=401, detail="认证失败：无效的 API Key")

    if not phone:
        raise HTTPException(status_code=400, detail="缺少手机号参数(phone)")

    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()
    cur.close()

    if user is None:
        raise HTTPException(status_code=404, detail="该手机号未注册")

    return user
