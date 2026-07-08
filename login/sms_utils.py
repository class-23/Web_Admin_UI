from typing import Tuple
import requests
from login import config


def send_sms(phone: str, code: str) -> Tuple[bool, str]:
    data = {
        "phone_number": phone,
        "code": code,
        "template_code": config.SMS_TEMPLATE_CODE,
        "sign_name": config.SMS_SIGN_NAME,
    }
    try:
        response = requests.post(config.SMS_API_URL, json=data, timeout=30)
        result = response.json()
        status = result.get("status", "")
        message = result.get("message", "")
        print(f"[短信发送] 手机号: {phone}, 验证码: {code}, 返回: {result}")
        if status == "success":
            return True, "验证码已发送"
        else:
            return False, f"短信发送失败: {message}"
    except Exception as e:
        print(f"[短信发送异常] 手机号: {phone}, 验证码: {code}, 错误: {e}")
        return False, f"短信发送异常: {str(e)}"
