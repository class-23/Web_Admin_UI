"""
Unit tests for the current login/auth.py authentication helpers.

说明：
- 这个文件测的是当前 main.py 主线使用的 login/auth.py。
- 不依赖真实 PostgreSQL。
- 不需要启动 main.py。
- 不需要配置环境变量。
- 通过 FakeDB / FakeCursor 模拟 users 表查询。

运行：
    python -m pytest tests/test_main_auth_dependencies.py -q
"""

import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest
from fastapi import Response, HTTPException
from jose import jwt
from starlette.requests import Request

from login import auth


# =========================
# Fake DB
# =========================

class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.result = None
        self.closed = False
        self.executed = []

    def execute(self, sql, params=None):
        sql_text = str(sql)
        params = params or ()
        self.executed.append((sql_text, params))

        if "WHERE id = %s" in sql_text:
            user_id = int(params[0])
            self.result = self.db.users_by_id.get(user_id)
            return

        if "WHERE phone = %s" in sql_text:
            phone = params[0]
            self.result = self.db.users_by_phone.get(phone)
            return

        self.result = None

    def fetchone(self):
        return self.result

    def close(self):
        self.closed = True


class FakeDB:
    def __init__(self, users=None):
        self.users = users or []
        self.users_by_id = {int(u["id"]): u for u in self.users}
        self.users_by_phone = {u["phone"]: u for u in self.users}
        self.cursors = []

    def cursor(self, *args, **kwargs):
        cur = FakeCursor(self)
        self.cursors.append(cur)
        return cur


# =========================
# Helpers
# =========================

def make_user(
    user_id=1,
    phone="19900000001",
    username="unit_user",
    password_changed_at=None,
):
    return {
        "id": user_id,
        "phone": phone,
        "username": username,
        "password": "hashed-password",
        "password_changed_at": (
            password_changed_at
            if password_changed_at is not None
            else datetime.now(timezone.utc) - timedelta(days=1)
        ),
    }


def make_request(cookies=None, query=None, headers=None):
    """
    创建一个 Starlette Request，用于直接调用 login/auth.py 里的依赖函数。
    """
    raw_headers = []

    if cookies:
        cookie_value = "; ".join(f"{k}={v}" for k, v in cookies.items())
        raw_headers.append((b"cookie", cookie_value.encode("utf-8")))

    if headers:
        for key, value in headers.items():
            raw_headers.append((key.lower().encode("latin-1"), str(value).encode("latin-1")))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/devices",
        "headers": raw_headers,
        "query_string": urlencode(query or {}).encode("utf-8"),
        "server": ("testserver", 80),
        "scheme": "http",
        "client": ("testclient", 123),
    }
    return Request(scope)


def make_token(user_id=1, username="unit_user", expires_delta=timedelta(minutes=5)):
    return auth.create_access_token(
        {"sub": str(user_id), "username": username},
        expires_delta=expires_delta,
    )


def query_api_key():
    return auth.settings.QUERY_API_KEY


# =========================
# Password / token / cookie
# =========================

def test_password_hash_and_verify_success():
    password = "UnitTest123"
    hashed = auth.get_password_hash(password)

    assert hashed != password
    assert auth.verify_password(password, hashed) is True
    assert auth.verify_password("WrongPassword123", hashed) is False


def test_get_password_hash_rejects_password_over_bcrypt_byte_limit():
    long_password = "a" * 73

    with pytest.raises(ValueError) as exc:
        auth.get_password_hash(long_password)

    assert "72" in str(exc.value)


def test_create_access_token_can_be_decoded():
    token = make_token(user_id=7, username="token_user")

    payload = jwt.decode(
        token,
        auth.config.SECRET_KEY,
        algorithms=[auth.config.ALGORITHM],
    )

    assert payload["sub"] == "7"
    assert payload["username"] == "token_user"
    assert "iat" in payload
    assert "exp" in payload


def test_set_auth_cookie_writes_httponly_cookie():
    response = Response()
    token = auth.set_auth_cookie(response, {"sub": "1", "username": "cookie_user"})

    set_cookie = response.headers.get("set-cookie")

    assert token
    assert auth.config.AUTH_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie


def test_clear_auth_cookie_sets_delete_cookie_header():
    response = Response()
    auth.clear_auth_cookie(response)

    set_cookie = response.headers.get("set-cookie")

    assert auth.config.AUTH_COOKIE_NAME in set_cookie
    assert "Max-Age=0" in set_cookie or "expires=" in set_cookie.lower()


# =========================
# get_current_user_from_cookie
# =========================

def test_get_current_user_from_cookie_returns_none_without_cookie():
    request = make_request()
    db = FakeDB(users=[make_user()])

    user = auth.get_current_user_from_cookie(request, db)

    assert user is None


def test_get_current_user_from_cookie_returns_user_with_valid_cookie():
    db_user = make_user(user_id=1, phone="19900000001", username="cookie_user")
    db = FakeDB(users=[db_user])
    token = make_token(user_id=1, username="cookie_user")
    request = make_request(cookies={auth.config.AUTH_COOKIE_NAME: token})

    user = auth.get_current_user_from_cookie(request, db)

    assert user == db_user


def test_get_current_user_from_cookie_returns_none_when_password_changed_after_token_issue():
    changed_after_iat = datetime.now(timezone.utc) + timedelta(seconds=2)
    db_user = make_user(
        user_id=1,
        phone="19900000001",
        username="cookie_user",
        password_changed_at=changed_after_iat,
    )
    db = FakeDB(users=[db_user])
    token = make_token(user_id=1, username="cookie_user")
    request = make_request(cookies={auth.config.AUTH_COOKIE_NAME: token})

    user = auth.get_current_user_from_cookie(request, db)

    assert user is None


def test_get_current_user_from_cookie_returns_none_with_invalid_token():
    request = make_request(cookies={auth.config.AUTH_COOKIE_NAME: "invalid-token"})
    db = FakeDB(users=[make_user()])

    user = auth.get_current_user_from_cookie(request, db)

    assert user is None


# =========================
# require_auth
# =========================

def test_require_auth_missing_cookie_raises_401():
    request = make_request()
    response = Response()
    db = FakeDB(users=[make_user()])

    with pytest.raises(HTTPException) as exc:
        auth.require_auth(request, response, db=db)

    assert exc.value.status_code == 401
    assert "未登录" in exc.value.detail


def test_require_auth_invalid_token_raises_401_and_clears_cookie():
    request = make_request(cookies={auth.config.AUTH_COOKIE_NAME: "invalid-token"})
    response = Response()
    db = FakeDB(users=[make_user()])

    with pytest.raises(HTTPException) as exc:
        auth.require_auth(request, response, db=db)

    assert exc.value.status_code == 401
    assert "登录凭证无效" in exc.value.detail

    set_cookie = response.headers.get("set-cookie")
    assert auth.config.AUTH_COOKIE_NAME in set_cookie


def test_require_auth_returns_user_with_valid_cookie():
    db_user = make_user(user_id=1, phone="19900000001", username="auth_user")
    db = FakeDB(users=[db_user])
    token = make_token(user_id=1, username="auth_user")
    request = make_request(cookies={auth.config.AUTH_COOKIE_NAME: token})
    response = Response()

    user = auth.require_auth(request, response, db=db)

    assert user == db_user


def test_require_auth_raises_401_when_user_not_found():
    db = FakeDB(users=[])
    token = make_token(user_id=404, username="missing_user")
    request = make_request(cookies={auth.config.AUTH_COOKIE_NAME: token})
    response = Response()

    with pytest.raises(HTTPException) as exc:
        auth.require_auth(request, response, db=db)

    assert exc.value.status_code == 401
    assert "用户不存在" in exc.value.detail


def test_require_auth_raises_401_when_password_changed_after_token_issue():
    db_user = make_user(
        user_id=1,
        phone="19900000001",
        username="auth_user",
        password_changed_at=datetime.now(timezone.utc) + timedelta(seconds=2),
    )
    db = FakeDB(users=[db_user])
    token = make_token(user_id=1, username="auth_user")
    request = make_request(cookies={auth.config.AUTH_COOKIE_NAME: token})
    response = Response()

    with pytest.raises(HTTPException) as exc:
        auth.require_auth(request, response, db=db)

    assert exc.value.status_code == 401
    assert "密码已变更" in exc.value.detail


# =========================
# require_auth_or_api_key
# =========================

def test_require_auth_or_api_key_prefers_valid_cookie_auth():
    db_user = make_user(user_id=1, phone="19900000001", username="cookie_user")
    db = FakeDB(users=[db_user])
    token = make_token(user_id=1, username="cookie_user")
    request = make_request(cookies={auth.config.AUTH_COOKIE_NAME: token})
    response = Response()

    user = auth.require_auth_or_api_key(request, response, db=db)

    assert user == db_user


def test_require_auth_or_api_key_accepts_query_api_key_and_phone():
    db_user = make_user(user_id=2, phone="19900000002", username="api_user")
    db = FakeDB(users=[db_user])
    request = make_request(
        query={
            "api_key": query_api_key(),
            "phone": "19900000002",
        }
    )
    response = Response()

    user = auth.require_auth_or_api_key(request, response, db=db)

    assert user == db_user


def test_require_auth_or_api_key_accepts_header_api_key_and_phone():
    db_user = make_user(user_id=3, phone="19900000003", username="header_api_user")
    db = FakeDB(users=[db_user])
    request = make_request(
        headers={
            "X-API-Key": query_api_key(),
            "X-Phone": "19900000003",
        }
    )
    response = Response()

    user = auth.require_auth_or_api_key(request, response, db=db)

    assert user == db_user


def test_require_auth_or_api_key_rejects_wrong_api_key():
    db = FakeDB(users=[make_user(phone="19900000001")])
    request = make_request(
        query={
            "api_key": "wrong-key",
            "phone": "19900000001",
        }
    )
    response = Response()

    with pytest.raises(HTTPException) as exc:
        auth.require_auth_or_api_key(request, response, db=db)

    assert exc.value.status_code == 401
    assert "无效的 API Key" in exc.value.detail


def test_require_auth_or_api_key_rejects_missing_phone():
    db = FakeDB(users=[make_user(phone="19900000001")])
    request = make_request(query={"api_key": query_api_key()})
    response = Response()

    with pytest.raises(HTTPException) as exc:
        auth.require_auth_or_api_key(request, response, db=db)

    assert exc.value.status_code == 400
    assert "缺少手机号" in exc.value.detail


def test_require_auth_or_api_key_rejects_unregistered_phone():
    db = FakeDB(users=[])
    request = make_request(
        query={
            "api_key": query_api_key(),
            "phone": "19900000999",
        }
    )
    response = Response()

    with pytest.raises(HTTPException) as exc:
        auth.require_auth_or_api_key(request, response, db=db)

    assert exc.value.status_code == 404
    assert "未注册" in exc.value.detail


def test_require_auth_or_api_key_falls_back_to_api_key_when_cookie_is_invalid():
    db_user = make_user(user_id=4, phone="19900000004", username="fallback_user")
    db = FakeDB(users=[db_user])
    request = make_request(
        cookies={auth.config.AUTH_COOKIE_NAME: "invalid-token"},
        query={
            "api_key": query_api_key(),
            "phone": "19900000004",
        },
    )
    response = Response()

    user = auth.require_auth_or_api_key(request, response, db=db)

    assert user == db_user


# =========================
# verify_api_key_and_phone
# =========================

def test_verify_api_key_and_phone_accepts_query_params():
    db_user = make_user(user_id=5, phone="19900000005", username="verify_user")
    db = FakeDB(users=[db_user])
    request = make_request(
        query={
            "api_key": query_api_key(),
            "phone": "19900000005",
        }
    )

    user = asyncio.run(auth.verify_api_key_and_phone(request, db=db))

    assert user == db_user


def test_verify_api_key_and_phone_rejects_invalid_api_key():
    db = FakeDB(users=[make_user(phone="19900000001")])
    request = make_request(
        query={
            "api_key": "wrong-key",
            "phone": "19900000001",
        }
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.verify_api_key_and_phone(request, db=db))

    assert exc.value.status_code == 401


def test_verify_api_key_and_phone_rejects_unregistered_phone():
    db = FakeDB(users=[])
    request = make_request(
        headers={
            "X-API-Key": query_api_key(),
            "X-Phone": "19900000999",
        }
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth.verify_api_key_and_phone(request, db=db))

    assert exc.value.status_code == 404
