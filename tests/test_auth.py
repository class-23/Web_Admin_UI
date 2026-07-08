"""
认证服务测试
"""
import pytest
from app.services.auth_service import AuthService
from app.schemas.auth import UserCreate
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token


class TestPasswordHashing:

    def test_hash_and_verify(self):
        password = "my_secure_password"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes(self):
        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        assert h1 != h2


class TestJWTToken:

    def test_create_and_decode_token(self):
        data = {"sub": "1", "username": "testuser"}
        token = create_access_token(data)
        assert token is not None

        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["username"] == "testuser"

    def test_invalid_token_returns_none(self):
        assert decode_access_token("invalid.token.here") is None

    def test_expired_token(self):
        from datetime import timedelta
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-1))
        assert decode_access_token(token) is None


class TestSchemaValidation:

    def test_username_strips_whitespace(self):
        from app.schemas.auth import UserCreate, LoginRequest

        uc = UserCreate(username="  testuser  ", email="test@example.com", password="password123")
        assert uc.username == "testuser"

        lr = LoginRequest(username="  admin  ", password="admin123")
        assert lr.username == "admin"


class TestAuthService:

    def test_register_user(self, db):
        user_create = UserCreate(username="newuser", email="new@example.com", password="password123")
        user = AuthService.register(db, user_create)
        assert user.id is not None
        assert user.username == "newuser"
        assert user.role == "user"
        assert user.is_active is True
        assert verify_password("password123", user.password_hash)

    def test_register_duplicate_username(self, db, test_user):
        user_create = UserCreate(username="testuser", email="other@example.com", password="pass123")
        with pytest.raises(ValueError, match="用户名已存在"):
            AuthService.register(db, user_create)

    def test_register_duplicate_email(self, db, test_user):
        user_create = UserCreate(username="otheruser", email="test@example.com", password="pass123")
        with pytest.raises(ValueError, match="邮箱已被注册"):
            AuthService.register(db, user_create)

    def test_login_by_username(self, db, test_user):
        result = AuthService.login(db, "testuser", "password123")
        assert result is not None
        assert "access_token" in result
        assert result["token_type"] == "bearer"

    def test_login_by_email(self, db, test_user):
        result = AuthService.login(db, "test@example.com", "password123")
        assert result is not None
        assert result["user"].username == "testuser"

    def test_login_wrong_password(self, db, test_user):
        assert AuthService.login(db, "testuser", "wrong_password") is None

    def test_login_nonexistent_user(self, db):
        assert AuthService.login(db, "nobody", "password") is None

    def test_login_disabled_user(self, db):
        from app.models.user import User
        user = User(
            username="disabled",
            email="disabled@example.com",
            password_hash=get_password_hash("password123"),
            is_active=False,
        )
        db.add(user)
        db.commit()

        with pytest.raises(ValueError, match="账号已被禁用"):
            AuthService.login(db, "disabled", "password123")

    def test_login_updates_last_login(self, db, test_user):
        assert test_user.last_login_at is None
        AuthService.login(db, "testuser", "password123")
        db.refresh(test_user)
        assert test_user.last_login_at is not None

    def test_forgot_password_existing_email(self, db, test_user):
        token = AuthService.forgot_password(db, "test@example.com")
        assert token is not None
        payload = decode_access_token(token)
        assert payload["purpose"] == "reset"

    def test_forgot_password_nonexistent_email(self, db):
        token = AuthService.forgot_password(db, "no@example.com")
        assert token is None

    def test_reset_password_success(self, db, test_user):
        token = AuthService.forgot_password(db, "test@example.com")
        assert AuthService.reset_password(db, token, "newpassword123") is True
        db.refresh(test_user)
        assert verify_password("newpassword123", test_user.password_hash)

    def test_reset_password_invalid_token(self, db):
        with pytest.raises(ValueError, match="无效的重置链接"):
            AuthService.reset_password(db, "invalid.token", "newpass123")

    def test_reset_password_wrong_purpose(self, db, test_user):
        login_token = create_access_token({"sub": str(test_user.id), "purpose": "login"})
        with pytest.raises(ValueError, match="无效的重置链接"):
            AuthService.reset_password(db, login_token, "newpass123")


class TestAuthEndpoints:

    def test_register_endpoint(self, app_client):
        resp = app_client.post("/api/auth/register", json={
            "username": "apiuser",
            "email": "api@example.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "apiuser"
        assert data["email"] == "api@example.com"
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_duplicate_endpoint(self, app_client, test_user):
        resp = app_client.post("/api/auth/register", json={
            "username": "testuser",
            "email": "dup@example.com",
            "password": "password123",
        })
        assert resp.status_code == 400
        assert "用户名已存在" in resp.json()["detail"]

    def test_login_by_username_endpoint(self, app_client, test_user):
        resp = app_client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "testuser"

    def test_login_by_email_endpoint(self, app_client, test_user):
        resp = app_client.post("/api/auth/login", json={
            "username": "test@example.com",
            "password": "password123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "test@example.com"

    def test_login_wrong_credentials(self, app_client, test_user):
        resp = app_client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_me_endpoint(self, app_client, test_user):
        login_resp = app_client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "password123",
        })
        token = login_resp.json()["access_token"]

        resp = app_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    def test_me_without_token(self, app_client):
        resp = app_client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_register_validation_error(self, app_client):
        resp = app_client.post("/api/auth/register", json={
            "username": "ab",
            "email": "not-an-email",
            "password": "12",
        })
        assert resp.status_code == 422

    def test_forgot_password_endpoint(self, app_client, test_user):
        resp = app_client.post("/api/auth/forgot-password", json={
            "email": "test@example.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "reset_token" in data

    def test_forgot_password_nonexistent(self, app_client):
        resp = app_client.post("/api/auth/forgot-password", json={
            "email": "no@example.com",
        })
        assert resp.status_code == 404

    def test_reset_password_endpoint(self, app_client, test_user):
        forgot_resp = app_client.post("/api/auth/forgot-password", json={
            "email": "test@example.com",
        })
        token = forgot_resp.json()["reset_token"]

        resp = app_client.post("/api/auth/reset-password", json={
            "token": token,
            "new_password": "brandnew123",
        })
        assert resp.status_code == 200
        assert "密码已重置" in resp.json()["message"]

        login_resp = app_client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "brandnew123",
        })
        assert login_resp.status_code == 200

    def test_reset_password_invalid_token(self, app_client):
        resp = app_client.post("/api/auth/reset-password", json={
            "token": "invalid.token",
            "new_password": "newpass123",
        })
        assert resp.status_code == 400
