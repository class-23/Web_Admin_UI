"""
认证服务 — 注册、登录、密码重置
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
)
from app.schemas.auth import UserCreate


class AuthService:

    @staticmethod
    def register(db: Session, user_create: UserCreate) -> User:
        if db.query(User).filter(User.username == user_create.username).first():
            raise ValueError("用户名已存在")
        if db.query(User).filter(User.email == user_create.email).first():
            raise ValueError("邮箱已被注册")

        user = User(
            username=user_create.username,
            email=user_create.email,
            password_hash=get_password_hash(user_create.password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, login_id: str, password: str) -> Optional[dict]:
        """login_id 支持用户名或邮箱"""
        if "@" in login_id:
            user = db.query(User).filter(User.email == login_id).first()
        else:
            user = db.query(User).filter(User.username == login_id).first()

        if not user or not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            raise ValueError("账号已被禁用")

        user.last_login_at = datetime.now(timezone.utc)
        db.commit()

        access_token = create_access_token(data={"sub": str(user.id)})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user,
        }

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def forgot_password(db: Session, email: str) -> Optional[str]:
        """生成密码重置 token（15分钟有效）"""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        from datetime import timedelta
        token = create_access_token(
            data={"sub": str(user.id), "purpose": "reset"},
            expires_delta=timedelta(minutes=15),
        )
        return token

    @staticmethod
    def reset_password(db: Session, token: str, new_password: str) -> bool:
        """使用重置 token 更新密码"""
        payload = decode_access_token(token)
        if not payload:
            raise ValueError("无效的重置链接")
        if payload.get("purpose") != "reset":
            raise ValueError("无效的重置链接")

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("无效的重置链接")

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise ValueError("用户不存在")

        user.password_hash = get_password_hash(new_password)
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
