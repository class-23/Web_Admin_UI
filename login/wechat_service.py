"""
微信登录服务
"""
import time
import httpx
from typing import Optional
from datetime import datetime, timedelta, timezone

from login.auth import create_access_token
from login import config
import logging

logger = logging.getLogger(__name__)

# 微信绑定令牌全局存储（短 key → 完整数据）
# 生产环境建议使用 Redis 或数据库替换
_bind_token_store: dict[str, dict] = {}


class WeChatService:
    """微信登录服务"""

    @staticmethod
    def exchange_code_for_token(code: str) -> Optional[dict]:
        """
        通过 code 换取 access_token + openid + unionid
        """
        if not config.WECHAT_APPID or not config.WECHAT_SECRET:
            print("[WeChat] APPID 或 APPSECRET 未配置")
            return None

        url = (
            "https://api.weixin.qq.com/sns/oauth2/access_token"
            f"?appid={config.WECHAT_APPID}"
            f"&secret={config.WECHAT_SECRET}"
            f"&code={code}"
            "&grant_type=authorization_code"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except httpx.TimeoutException:
            print("[WeChat] 换取 token 超时")
            return None
        except Exception as e:
            print(f"[WeChat] 换取 token 请求失败: {e}")
            return None

        if "errcode" in data and data["errcode"] != 0:
            print(f"[WeChat] 换取 token 失败: errcode={data['errcode']}, errmsg={data.get('errmsg')}")
            return None

        return {
            "access_token": data["access_token"],
            "expires_in": data["expires_in"],
            "refresh_token": data["refresh_token"],
            "openid": data["openid"],
            "unionid": data.get("unionid", ""),
            "scope": data["scope"],
        }

    @staticmethod
    def get_user_info(access_token: str, openid: str) -> dict:
        """
        获取微信用户基本信息
        """
        url = (
            "https://api.weixin.qq.com/sns/userinfo"
            f"?access_token={access_token}"
            f"&openid={openid}"
            "&lang=zh_CN"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except Exception as e:
            print(f"[WeChat] 获取用户信息失败: {e}")
            return {}

        if "errcode" in data and data["errcode"] != 0:
            print(f"[WeChat] 获取用户信息失败: errcode={data['errcode']}, errmsg={data.get('errmsg')}")
            return {}

        return {
            "openid": data.get("openid", ""),
            "unionid": data.get("unionid", ""),
            "nickname": data.get("nickname", ""),
            "headimgurl": data.get("headimgurl", ""),
        }

    @staticmethod
    def create_bind_token(openid: str, unionid: str, user_info: dict, token_data: dict) -> str:
        """
        生成微信绑定临时令牌（10分钟有效）

        为避免 JWT 长字符串在 URL 中被截断（split at `.`），这里使用短 key，
        完整的数据（access_token, refresh_token 等）保存在内存 dict 中。
        """
        import secrets
        token_key = secrets.token_urlsafe(16)  # 22 字符短字符串，无 . 和特殊字符

        # 把完整数据存到全局缓存中
        _bind_token_store[token_key] = {
            "openid": openid,
            "unionid": unionid,
            "nickname": user_info.get("nickname", ""),
            "headimgurl": user_info.get("headimgurl", ""),
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_in": token_data["expires_in"],
            "scope": token_data.get("scope", ""),
            "expires_at": time.time() + 600,  # 10 分钟过期
        }

        logger.info(f"[WeChat] create_bind_token: key={token_key[:8]}...")
        return token_key

    @staticmethod
    def consume_bind_token(token_key: str) -> Optional[dict]:
        """
        根据短 token key 获取绑定数据（验证不消耗，由调用方在成功绑定后调用 delete_bind_token 真正清理）

        这样设计是为了：
        1. 同一 token 可以多次校验（防止 race condition）
        2. 真正的消耗时点是绑定成功写入数据库后
        3. 如果绑定中途失败，token 还在，用户可以重试
        """
        data = _bind_token_store.get(token_key)
        if not data:
            return None
        # 检查是否过期
        if time.time() > data.get("expires_at", 0):
            _bind_token_store.pop(token_key, None)
            return None
        return data

    @staticmethod
    def delete_bind_token(token_key: str) -> bool:
        """绑定成功后真正清理 token"""
        return _bind_token_store.pop(token_key, None) is not None

    @staticmethod
    def peek_bind_token(token_key: str) -> Optional[dict]:
        """
        仅查询绑定数据（不消费），用于绑页页面展示微信头像/昵称
        """
        data = _bind_token_store.get(token_key)
        if not data:
            return None
        if time.time() > data.get("expires_at", 0):
            _bind_token_store.pop(token_key, None)
            return None
        return data

    @staticmethod
    def refresh_user_token(refresh_token: str) -> Optional[dict]:
        """
        刷新网站授权 access_token（续期）
        """
        if not config.WECHAT_APPID:
            return None

        url = (
            "https://api.weixin.qq.com/sns/oauth2/refresh_token"
            f"?appid={config.WECHAT_APPID}"
            "&grant_type=refresh_token"
            f"&refresh_token={refresh_token}"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except Exception as e:
            print(f"[WeChat] 刷新 token 失败: {e}")
            return None

        if "errcode" in data and data["errcode"] != 0:
            print(f"[WeChat] 刷新 token 失败: {data}")
            return None

        return {
            "access_token": data["access_token"],
            "expires_in": data["expires_in"],
            "refresh_token": data["refresh_token"],
            "openid": data["openid"],
            "scope": data.get("scope", ""),
        }

    @staticmethod
    def verify_access_token(access_token: str, openid: str) -> bool:
        """
        检验授权凭证（access_token）是否有效
        """
        url = (
            "https://api.weixin.qq.com/sns/auth"
            f"?access_token={access_token}"
            f"&openid={openid}"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except Exception:
            return False

        return data.get("errcode") == 0
