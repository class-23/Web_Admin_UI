"""
微信普通 access_token 管理器（用于调用微信服务端 API）
"""
import time
import httpx
from login import config


class WeChatAccessTokenManager:
    """
    微信普通 access_token 管理器
    有效期 2 小时，建议在应用启动时获取并定时刷新
    """

    _access_token = None
    _expires_at = 0

    @classmethod
    def get_token(cls) -> str:
        """获取有效的 access_token，如过期则自动刷新"""
        if cls._access_token and time.time() < cls._expires_at - 300:
            # 未过期（提前5分钟刷新）
            return cls._access_token
        return cls._refresh_token()

    @classmethod
    def _refresh_token(cls) -> str:
        """刷新 access_token"""
        if not config.WECHAT_APPID or not config.WECHAT_SECRET:
            print("[WeChat] APPID 或 APPSECRET 未配置")
            return cls._access_token or ""

        url = (
            "https://api.weixin.qq.com/cgi-bin/token"
            f"?grant_type=client_credential"
            f"&appid={config.WECHAT_APPID}"
            f"&secret={config.WECHAT_SECRET}"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except Exception as e:
            print(f"[WeChat] 刷新 access_token 失败: {e}")
            return cls._access_token or ""

        if "errcode" in data and data["errcode"] != 0:
            print(f"[WeChat] 刷新 access_token 错误: {data}")
            return cls._access_token or ""

        cls._access_token = data["access_token"]
        cls._expires_at = time.time() + data["expires_in"]
        print(f"[WeChat] access_token 已刷新，有效期 {data['expires_in']} 秒")
        return cls._access_token
