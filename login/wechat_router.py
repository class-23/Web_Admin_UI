"""
微信登录 API 路由
"""
import secrets
import time
import hmac
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, Body
from fastapi.responses import RedirectResponse
from jose import jwt, JWTError
from pydantic import BaseModel
import psycopg2.extras

from login import config
from login.auth import create_access_token, set_auth_cookie
from login.code_store import get_code
from login.database import get_db
from login.limiter import limiter
from login.schemas import ApiResponse
from login.wechat_service import WeChatService

logger = logging.getLogger(__name__)

router = APIRouter()
wechat_service = WeChatService()


def _top_redirect_html(url: str, message: str = "登录成功", auth_token: str = None):
    """
    生成一个 HTML 页面，在顶级窗口（top）进行跳转。

    由于 WxLogin JS SDK 将二维码嵌入在 iframe 中，微信回调 redirect_uri 时，
    跳转只会在 iframe 内发生，父级页面没有变化，导致用户体验差。

    解决方案：让回调接口返回一个 HTML 页面，用 JS 在 top.window 中跳转，
    这样整个浏览器窗口会切换到目标 URL。

    auth_token: 可选。如果提供，会在返回的 HTMLResponse 上直接设置 cookie，
               而不是用共享的 response 对象（避免被新对象覆盖丢失）。
    """
    from fastapi.responses import HTMLResponse
    safe_url = url.replace('"', '&quot;')
    html_response = HTMLResponse(
        content=f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{message}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif; background: #f7fafc; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }}
.box {{ text-align: center; padding: 40px; }}
.spinner {{ width: 40px; height: 40px; border: 3px solid #e2e8f0; border-top-color: #07c160; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.msg {{ color: #4a5568; font-size: 16px; }}
</style>
</head>
<body>
<div class="box">
<div class="spinner"></div>
<div class="msg">{message}</div>
</div>
<script>
(function() {{
  var targetUrl = "{safe_url}";
  // 检测当前是否在新窗口(window.open 打开的)，而不是 iframe 内
  // window.opener 存在 = window.open 弹窗
  // 弹窗模式：通知主页面 + 关闭当前弹窗
  // iframe 模式（如 WxLogin SDK 内嵌）：通知父页面 + 顶层跳转
  function go() {{
    var isPopup = !!(window.opener);

    if (isPopup) {{
      // 弹窗模式：通知主窗口 + 关闭自己
      try {{
        if (!window.opener.closed) {{
          window.opener.postMessage({{
            type: 'wechat_login_callback',
            action: 'redirect',
            url: targetUrl
          }}, '*');
        }}
      }} catch (e) {{}}
      // 直接尝试关闭弹窗
      try {{
        window.close();
        return;
      }} catch (e) {{}}
      // 如果 close() 被禁用，跳转到 about:blank（兜底）
      try {{
        setTimeout(function() {{
          window.location.replace('about:blank');
        }}, 100);
      }} catch (e) {{}}
    }} else {{
      // iframe 模式：用 postMessage 通知父 + top 跳转
      try {{
        if (window.parent && window.parent !== window.self) {{
          window.parent.postMessage({{
            type: 'wechat_login_callback',
            action: 'redirect',
            url: targetUrl
          }}, '*');
        }}
      }} catch (e) {{}}
      try {{
        if (window.top && window.top !== window.self) {{
          window.top.postMessage({{
            type: 'wechat_login_callback',
            action: 'redirect',
            url: targetUrl
          }}, '*');
        }}
      }} catch (e) {{}}
      try {{ window.location.replace(targetUrl); return; }} catch (e) {{}}
      try {{ window.location.href = targetUrl; return; }} catch (e) {{}}
    }}
  }}

  go();
  setTimeout(go, 100);
  setTimeout(go, 500);
  setTimeout(go, 1500);
}})();
</script>
</body>
</html>""",
        status_code=200,
    )

    # 直接在新的 HTMLResponse 上设置 cookie（而不是用 callback 函数开头的共享 response）
    if auth_token:
        html_response.set_cookie(
            key=config.AUTH_COOKIE_NAME,
            value=auth_token,
            max_age=config.AUTH_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            path="/",
            secure=False,
        )
    return html_response


def _top_redirect_html_with_cookie(url: str, bind_token: str, message: str = "首次登录"):
    """
    带 cookie 设置的顶级窗口跳转 HTML。

    解决 URL 参数丢失问题：把 bind_token 同时写入 cookie，
    让前端轮询跳转时无需依赖 URL 参数。
    """
    from fastapi.responses import HTMLResponse
    safe_url = url.replace('"', '&quot;')
    safe_token = bind_token.replace('"', '')
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{message}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif; background: #f7fafc; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }}
.box {{ text-align: center; padding: 40px; }}
.spinner {{ width: 40px; height: 40px; border: 3px solid #e2e8f0; border-top-color: #07c160; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.msg {{ color: #4a5568; font-size: 16px; }}
</style>
</head>
<body>
<div class="box">
<div class="spinner"></div>
<div class="msg">{message}</div>
</div>
<script>
(function() {{
  // 把 bind_token 写入 cookie（备用方案，让 main.py 从 cookie 取）
  try {{
    document.cookie = "wechat_bind_token={safe_token}; path=/; max-age=600; SameSite=Lax";
  }} catch (e) {{}}

  var targetUrl = "{safe_url}";
  function go() {{
    try {{
      if (window.top && window.top !== window.self) {{
        try {{ window.top.location.replace(targetUrl); return; }} catch (e) {{}}
        try {{ window.top.location.href = targetUrl; return; }} catch (e2) {{}}
      }}
    }} catch (e) {{}}
    try {{ window.location.replace(targetUrl); }} catch (e3) {{}}
    window.location.href = targetUrl;
  }}
  go();
  setTimeout(go, 500);
  setTimeout(go, 1500);
}})();
</script>
</body>
</html>""",
        status_code=200,
    )
    from fastapi.responses import HTMLResponse
    safe_url = url.replace('"', '&quot;')
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{message}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif; background: #f7fafc; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }}
.box {{ text-align: center; padding: 40px; }}
.spinner {{ width: 40px; height: 40px; border: 3px solid #e2e8f0; border-top-color: #07c160; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 20px; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
.msg {{ color: #4a5568; font-size: 16px; }}
</style>
</head>
<body>
<div class="box">
<div class="spinner"></div>
<div class="msg">{message}</div>
</div>
<script>
(function() {{
  var targetUrl = "{safe_url}";
  function go() {{
    try {{
      if (window.top && window.top !== window.self) {{
        try {{ window.top.location.replace(targetUrl); return; }} catch (e) {{}}
        try {{ window.top.location.href = targetUrl; return; }} catch (e2) {{}}
      }}
    }} catch (e) {{}}
    try {{ window.location.replace(targetUrl); }} catch (e3) {{}}
    window.location.href = targetUrl;
  }}
  go();
  setTimeout(go, 500);
  setTimeout(go, 1500);
}})();
</script>
</body>
</html>""",
        status_code=200,
    )


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP（优先 X-Forwarded-For 头）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


# QR session 签名密钥
QR_SIGN_SECRET = config.WECHAT_QR_SIGN_SECRET or secrets.token_hex(32)

# 内存 QR session 存储（生产环境建议替换为 Redis）
_qr_sessions: dict[str, dict] = {}


# ==============================================================
# 辅助函数
# ==============================================================

def _sign_qr_data(session_id: str, state: str, device_fp: str, timestamp: int) -> str:
    """对 QR session 数据进行 HMAC-SHA256 签名，防止篡改"""
    message = f"{session_id}|{state}|{device_fp}|{timestamp}"
    return hmac.new(
        QR_SIGN_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:16]


def _log_login_audit(
    db,
    openid: str,
    user_id: Optional[int],
    ip: str,
    status: str,
    method: str,
    reason: str = "",
):
    """记录登录审计日志"""
    try:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO login_audit_log "
            "(openid, user_id, ip, status, method, reason, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW())",
            (openid, user_id, ip, status, method, reason)
        )
        db.commit()
        cur.close()
    except Exception as e:
        logger.error(f"[WeChat] 审计日志写入失败: {e}")


# ==============================================================
# Request/Response Models
# ==============================================================

class WechatBindRequest(BaseModel):
    bind_token: str
    phone: str
    code: str


class QrSessionRequest(BaseModel):
    device_fp: str


# ==============================================================
# API 路由
# ==============================================================


@router.post("/wechat/qr-session", summary="创建微信扫码 session")
@limiter.limit("30/minute")
def create_qr_session(
    request: Request,
    req: QrSessionRequest,
    db = Depends(get_db),
):
    """
    生成扫码 session，绑定设备指纹和 IP。
    """
    device_fp = req.device_fp
    ip = _get_client_ip(request)

    if not device_fp:
        return ApiResponse(code=400, message="缺少设备指纹")

    session_id = secrets.token_hex(16)
    state = f"wx_{secrets.token_hex(8)}_{device_fp}"
    now_ts = int(time.time())
    signature = _sign_qr_data(session_id, state, device_fp, now_ts)

    _qr_sessions[session_id] = {
        "state": state,
        "device_fp": device_fp,
        "ip": ip,
        "created_at": now_ts,
        "signature": signature,
        "status": "pending",
        "scanned_at": None,
        "confirmed_at": None,
    }

    return ApiResponse(code=0, message="success", data={
        "session_id": session_id,
        "state": state,
        "signature": signature,
        "expires_in": 120,
    })


@router.get("/wechat/qr-session/{session_id}/status", summary="轮询扫码状态")
@limiter.limit("60/minute")
def poll_qr_status(
    session_id: str,
    request: Request,
    device_fp: str = Query(...),
    signature: str = Query(...),
    db = Depends(get_db),
):
    """
    前端轮询接口，获取当前扫码状态。
    """
    session_data = _qr_sessions.get(session_id)
    if not session_data:
        return ApiResponse(code=404, message="session 不存在")

    expected_sig = _sign_qr_data(
        session_id, session_data["state"],
        device_fp, session_data["created_at"]
    )
    if not hmac.compare_digest(expected_sig, signature):
        return ApiResponse(code=403, message="签名校验失败")

    if session_data["device_fp"] != device_fp:
        return ApiResponse(code=403, message="设备指纹不匹配")

    if time.time() - session_data["created_at"] > 180:
        _qr_sessions.pop(session_id, None)
        return ApiResponse(code=200, message="二维码已过期", data={"status": "expired"})

    return ApiResponse(code=0, message="success", data={
        "status": session_data["status"],
        "redirect_url": session_data.get("redirect_url"),
        "bind_token": session_data.get("bind_token"),  # 同时返回 bind_token，前端可直接使用
    })


@router.get("/wechat/callback", summary="微信登录回调")
@limiter.limit("30/minute")
def wechat_callback(
    request: Request,
    response: Response,
    code: str = Query(...),
    state: str = Query(None),
    db = Depends(get_db),
):
    """
    微信扫码登录回调处理。
    """
    client_ip = _get_client_ip(request)

    # Step 1: 校验 state 格式
    if not state or not state.startswith("wx_"):
        logger.warning(f"[WeChat] 无效的 state 参数: ip={client_ip}")
        return RedirectResponse(url="/login?error=invalid_request", status_code=302)

    state_parts = state.split("_")
    if len(state_parts) < 3:
        logger.warning(f"[WeChat] state 格式异常: ip={client_ip}")
        return RedirectResponse(url="/login?error=invalid_request", status_code=302)

    request_device_fp = state_parts[-1]
    logger.info(f"[WeChat] 收到回调: ip={client_ip}, state_prefix={state[:12]}")

    # 根据 state 找到对应的 session_id，并标记为 scanned（前端轮询可感知）
    for sid, sdata in _qr_sessions.items():
        if sdata.get("state") == state:
            sdata["status"] = "scanned"
            sdata["scanned_at"] = int(time.time())
            break

    # Step 2: IP 级滑动窗口速率限制
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM login_audit_log "
        "WHERE ip = %s AND created_at > NOW() - INTERVAL '1 minute' "
        "AND status IN ('failed', 'rate_limited')",
        (client_ip,)
    )
    ip_1min_failures = cur.fetchone()[0]
    if ip_1min_failures >= 3:
        logger.warning(f"[WeChat] IP 1 分钟内失败 {ip_1min_failures} 次: ip={client_ip}")
        _log_login_audit(db, openid="", user_id=None,
                         ip=client_ip, status="rate_limited", method="wechat_scan",
                         reason=f"IP 1min rate limit: {ip_1min_failures}")
        cur.close()
        return RedirectResponse(url="/login?error=rate_limited", status_code=302)

    cur.execute(
        "SELECT COUNT(*) FROM login_audit_log "
        "WHERE ip = %s AND created_at > NOW() - INTERVAL '1 hour' "
        "AND status IN ('failed', 'rate_limited')",
        (client_ip,)
    )
    ip_1h_failures = cur.fetchone()[0]
    cur.close()
    if ip_1h_failures >= 20:
        logger.warning(f"[WeChat] IP 1 小时内失败 {ip_1h_failures} 次: ip={client_ip}")
        return RedirectResponse(url="/login?error=rate_limited", status_code=302)

    # Step 3: 用 code 换取 access_token
    token_data = wechat_service.exchange_code_for_token(code)
    if not token_data:
        logger.warning(f"[WeChat] 换取 token 失败: ip={client_ip}, code={code[:6]}...")
        _log_login_audit(db, openid="", user_id=None,
                         ip=client_ip, status="failed", method="wechat_scan",
                         reason="exchange_code_failed")
        return RedirectResponse(url="/login?error=auth_failed", status_code=302)

    openid = token_data["openid"]
    unionid = token_data.get("unionid", "")
    logger.info(f"[WeChat] 换取 token 成功: openid={openid[:8]}..., unionid_provided={bool(unionid)}")

    # Step 4: 获取微信用户信息
    user_info = wechat_service.get_user_info(token_data["access_token"], openid)

    # Step 5: openid 级速率限制
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM login_audit_log "
        "WHERE openid = %s AND created_at > NOW() - INTERVAL '5 minutes' "
        "AND status IN ('failed', 'rate_limited')",
        (openid,)
    )
    recent_failures = cur.fetchone()[0]
    cur.close()

    if recent_failures >= 5:
        logger.warning(f"[WeChat] openid 短时高频失败: openid={openid[:8]}..., failures={recent_failures}")
        _log_login_audit(db, openid=openid, user_id=None,
                         ip=client_ip, status="rate_limited", method="wechat_scan",
                         reason=f"openid rate limit: {recent_failures}")
        return RedirectResponse(url="/login?error=rate_limited", status_code=302)

    # Step 5.5: 风控评分
    risk_score = 0
    risk_factors = []

    if request_device_fp and len(request_device_fp) < 8:
        risk_score += 20
        risk_factors.append("device_fp_too_short")

    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT ip) FROM login_audit_log "
        "WHERE openid = %s AND created_at > NOW() - INTERVAL '30 minutes'"
        "AND status = 'success'",
        (openid,)
    )
    distinct_ips = cur.fetchone()[0]
    if distinct_ips >= 3:
        risk_score += 15
        risk_factors.append("multi_ip_in_30min")

    cur.execute(
        "SELECT COUNT(DISTINCT openid) FROM login_audit_log "
        "WHERE ip = %s AND created_at > NOW() - INTERVAL '5 minutes' "
        "AND method = 'wechat_scan'",
        (client_ip,)
    )
    distinct_openids = cur.fetchone()[0]
    cur.close()
    if distinct_openids >= 10:
        risk_score += 25
        risk_factors.append("mass_scan_from_single_ip")

    if risk_score >= 40:
        logger.warning(f"[WeChat] 风控拦截: openid={openid[:8]}..., score={risk_score}, factors={risk_factors}")
        _log_login_audit(db, openid=openid, user_id=None,
                         ip=client_ip, status="rate_limited", method="wechat_scan",
                         reason=f"risk_score_{risk_score}:{','.join(risk_factors)}")
        return RedirectResponse(url="/login?error=risk_blocked", status_code=302)

    # Step 6: 判断用户是否已绑定
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM users WHERE wechat_info->>'openid' = %s",
        (openid,)
    )
    user = cur.fetchone()
    cur.close()

    if user:
        # 已绑定 → 更新 wechat_info 并直接登录
        try:
            existing_info = user["wechat_info"] or {}
        except (TypeError, KeyError):
            existing_info = {}

        updated_wechat_info = {**existing_info, **{
            "nickname": user_info.get("nickname", existing_info.get("nickname", "")),
            "headimgurl": user_info.get("headimgurl", existing_info.get("headimgurl", "")),
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "token_expires_at": int(time.time()) + token_data["expires_in"],
            "last_login_at": datetime.now(timezone.utc).isoformat(),
        }}

        cur = db.cursor()
        cur.execute(
            "UPDATE users SET wechat_info = %s, last_login_at = NOW(), "
            "updated_at = NOW() WHERE id = %s",
            (psycopg2.extras.Json(updated_wechat_info), user["id"])
        )
        db.commit()
        cur.close()

        set_auth_cookie(response, {"sub": str(user["id"]), "username": user["username"]})
        # 同时创建一个 JWT token 传给 HTMLResponse 函数，避免共享 response 上的 cookie 被新对象覆盖
        from login.auth import create_access_token
        auth_token = create_access_token({"sub": str(user["id"]), "username": user["username"]})

        _log_login_audit(db, openid=openid, user_id=user["id"],
                         ip=client_ip, status="success", method="wechat_scan")

        # 标记 session 为"已绑定"（前端轮询可感知并触发跳转）
        for sid, sdata in _qr_sessions.items():
            if sdata.get("state") == state:
                sdata["status"] = "bound"
                sdata["confirmed_at"] = int(time.time())
                sdata["redirect_url"] = "/"
                break

        logger.info(f"[WeChat] 登录成功: user_id={user['id']}, openid={openid[:8]}...")
        # 由于 WxLogin 二维码是嵌入在 iframe 中，服务端 302 重定向只在 iframe 内部生效
        # 这里返回一个 HTML 页面，让父窗口执行跳转；cookie 直接在新 HTMLResponse 上设置
        return _top_redirect_html("/", "登录成功，正在跳转…", auth_token=auth_token)

    else:
        # 未绑定 → 生成绑定临时令牌，跳转绑定页
        bind_token = wechat_service.create_bind_token(
            openid=openid,
            unionid=unionid,
            user_info=user_info,
            token_data=token_data,
        )
        redirect_url = f"/bind-wechat?bind_token={bind_token}"

        _log_login_audit(db, openid=openid, user_id=None,
                         ip=client_ip, status="need_bind", method="wechat_scan")

        # 标记 session 为"待绑定"（前端轮询可感知并触发跳转）
        for sid, sdata in _qr_sessions.items():
            if sdata.get("state") == state:
                sdata["status"] = "need_bind"
                sdata["confirmed_at"] = int(time.time())
                sdata["redirect_url"] = redirect_url
                sdata["bind_token"] = bind_token  # 同时保存 bind_token 用于 cookie 模式
                break

        logger.info(f"[WeChat] 未绑定，跳转绑定页: openid={openid[:8]}...")

        # 优先方案：cookie 模式 + 无 query 跳转（避免 URL 参数丢失）
        redirect_response = _top_redirect_html_with_cookie(
            url=redirect_url,
            bind_token=bind_token,
            message="首次登录，请绑定手机号…"
        )
        # 同时保留 HTML 跳转兜底（兼容 cookie 被禁用的情况）
        return redirect_response


@router.get("/wechat/check-phone", response_model=ApiResponse, summary="校验手机号是否已注册")
def wechat_check_phone(
    request: Request,
    phone: str = Query(..., description="待校验的手机号"),
    db = Depends(get_db),
):
    """
    校验手机号是否已在系统中注册。
    用于微信绑定流程中，发送验证码前的前置校验。
    """
    if not re.match(r"^1[3-9]\d{9}$", phone):
        return ApiResponse(code=400, message="手机号格式不正确")

    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()
    cur.close()

    if user:
        return ApiResponse(code=0, message="手机号已注册", data={"registered": True})
    else:
        return ApiResponse(
            code=404,
            message="请使用你在本网站注册的手机号来绑定该微信号",
            data={"registered": False}
        )


@router.post("/wechat/bind", response_model=ApiResponse, summary="微信账号绑定手机号")
@limiter.limit("10/minute")
def wechat_bind(
    request: Request,
    response: Response,
    req: WechatBindRequest,
    db = Depends(get_db),
):
    """
    微信用户首次登录绑定手机号。
    """
    ip = _get_client_ip(request)

    # Step 1: 验证 bind_token（短 key 模式）
    bind_data = wechat_service.consume_bind_token(req.bind_token)
    if not bind_data:
        return ApiResponse(code=400, message="绑定令牌已过期，请重新扫码")

    openid = bind_data["openid"]
    unionid = bind_data.get("unionid", "")
    nickname = bind_data.get("nickname", "")
    headimgurl = bind_data.get("headimgurl", "")

    # Step 2: 验证短信验证码
    # 验证码验证：开发万能验证码 888888 直接通过
    # 从 login.routers.auth_router 引入 is_dev_bypass 工具函数
    from login.routers.auth_router import is_dev_bypass
    if not is_dev_bypass(req.code):
        stored_code = get_code(req.phone)
        if stored_code is None or stored_code != req.code:
            return ApiResponse(code=400, message="验证码无效或已过期")

    # Step 3: 验证手机号是否在本系统注册
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE phone = %s", (req.phone,))
    existing_user = cur.fetchone()

    if not existing_user:
        cur.close()
        return ApiResponse(
            code=404,
            message="请使用你在本网站注册的手机号来绑定该微信号"
        )

    # Step 4: 检查该 phone 用户本身的 wechat_info 是否已被其他 openid 绑定
    # 由于 users.phone 是 UNIQUE 约束，每个手机号最多对应一个用户，
    # 所以"手机号是否已被其他微信号绑定"实际上就是：
    # 这个用户（existing_user）的 wechat_info.openid 是否不是当前 openid
    # 限制：一个手机号只能绑定一个微信
    existing_wechat_info = existing_user.get("wechat_info") or {}
    existing_openid = None
    if isinstance(existing_wechat_info, dict):
        existing_openid = existing_wechat_info.get("openid")
    elif hasattr(existing_wechat_info, "get"):  # 兼容 JSON 类型
        existing_openid = existing_wechat_info.get("openid")

    if existing_openid and existing_openid != openid:
        cur.close()
        # 记录 audit log
        _log_login_audit(db, openid=openid, user_id=existing_user["id"],
                         ip=ip, status="failed", method="wechat_bind",
                         reason="phone_already_bound_to_other_wechat")
        return ApiResponse(
            code=409,
            message="该手机号已被其他微信账号绑定，请使用其他手机号或解除原绑定关系"
        )

    # Step 5: 检查该 openid 是否已被其他账号绑定
    # 限制：一个微信只能绑定一个手机号（已有逻辑）
    cur.execute(
        "SELECT id FROM users WHERE wechat_info->>'openid' = %s AND id != %s",
        (openid, existing_user["id"])
    )
    bound_user_by_openid = cur.fetchone()
    cur.close()

    if bound_user_by_openid:
        # 记录 audit log
        _log_login_audit(db, openid=openid, user_id=None,
                         ip=ip, status="failed", method="wechat_bind",
                         reason="wechat_already_bound_to_other_phone")
        return ApiResponse(code=409, message="该微信账号已被其他用户绑定，请使用其他微信账号或先解除原绑定关系")

    # Step 5: 构建 wechat_info 并绑定到已有用户
    wechat_info = {
        "openid": openid,
        "unionid": unionid,
        "nickname": nickname,
        "headimgurl": headimgurl,
        "access_token": bind_data.get("access_token", ""),
        "refresh_token": bind_data.get("refresh_token", ""),
        "token_expires_at": int(time.time()) + bind_data.get("expires_in", 7200),
        "bound_at": datetime.now(timezone.utc).isoformat(),
        "last_login_at": datetime.now(timezone.utc).isoformat(),
    }

    cur = db.cursor()
    cur.execute(
        "UPDATE users SET wechat_info = %s, updated_at = NOW() WHERE id = %s",
        (psycopg2.extras.Json(wechat_info), existing_user["id"])
    )
    db.commit()
    cur.close()

    # 数据库写入成功后，才真正消耗 token（防止 race condition）
    wechat_service.delete_bind_token(req.bind_token)

    # 记录审计日志
    _log_login_audit(db, openid=openid, user_id=existing_user["id"],
                     ip=ip, status="success", method="wechat_bind")

    logger.info(f"[WeChat] 绑定成功: user_id={existing_user['id']}, username={existing_user['username']}")

    # 直接返回 redirect（302）到 /，浏览器自动 follow
    # 这样可以避免前端 JS 跳转被浏览器拦截的问题
    # 关键：必须先创建 RedirectResponse，再直接在它上面 set_cookie！
    # 因为 FastAPI 共享 response 上的 cookie 不会被传递到返回的 RedirectResponse
    from fastapi.responses import RedirectResponse
    from login.auth import create_access_token
    redirect_response = RedirectResponse(url="/", status_code=302)
    auth_token = create_access_token({
        "sub": str(existing_user["id"]),
        "username": existing_user["username"]
    })
    redirect_response.set_cookie(
        key=config.AUTH_COOKIE_NAME,
        value=auth_token,
        max_age=config.AUTH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
        secure=False,
    )
    return redirect_response


@router.post("/wechat/rebind", summary="微信重新绑定（简化流程）")
@limiter.limit("3/day")
def wechat_rebind(
    request: Request,
    response: Response,
    openid: str = Body(...),
    new_phone: str = Body(...),
    code: str = Body(...),
    db = Depends(get_db),
):
    """
    微信重新绑定手机号（适合已登录用户更换绑定手机号）。
    """
    # 验证短信验证码
    stored_code = get_code(new_phone)
    if not stored_code or stored_code != code:
        return ApiResponse(code=400, message="验证码无效或已过期")

    # 校验新手机号是否已注册
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, wechat_info FROM users WHERE phone = %s", (new_phone,))
    target_user = cur.fetchone()
    cur.close()

    if not target_user:
        return ApiResponse(code=404, message="新手机号未注册")

    # 从原用户的 wechat_info 中获取完整信息
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT id, wechat_info FROM users WHERE wechat_info->>'openid' = %s",
        (openid,)
    )
    source_user = cur.fetchone()
    cur.close()

    if not source_user or not source_user["wechat_info"]:
        return ApiResponse(code=404, message="未找到原微信绑定信息")

    # 执行重新绑定
    wechat_info = source_user["wechat_info"]
    wechat_info["bound_at"] = datetime.now(timezone.utc).isoformat()
    wechat_info["last_login_at"] = datetime.now(timezone.utc).isoformat()

    cur = db.cursor()
    # 清除原用户的 wechat_info
    cur.execute(
        "UPDATE users SET wechat_info = NULL, updated_at = NOW() WHERE id = %s",
        (source_user["id"],)
    )
    # 绑定到新用户
    cur.execute(
        "UPDATE users SET wechat_info = %s, updated_at = NOW() WHERE id = %s",
        (psycopg2.extras.Json(wechat_info), target_user["id"])
    )
    db.commit()
    cur.close()

    return ApiResponse(code=0, message="重新绑定成功")


@router.post("/wechat/event", summary="接收微信事件推送")
async def wechat_event_handler(
    request: Request,
    db = Depends(get_db),
):
    """
    接收微信开放平台的事件推送。
    包括：用户资料变更、授权撤回、账号注销等。
    """
    import xml.etree.ElementTree as ET

    body = await request.body()
    root = ET.fromstring(body)

    event = root.findtext("Event", "")
    openid = root.findtext("OpenID", "")

    if event == "user_info_modified":
        logger.info(f"[WeChat] 用户资料变更: openid={openid}")

    elif event == "user_authorization_revoke":
        cur = db.cursor()
        cur.execute(
            "UPDATE users SET wechat_info = NULL, updated_at = NOW() "
            "WHERE wechat_info->>'openid' = %s",
            (openid,)
        )
        db.commit()
        cur.close()
        logger.info(f"[WeChat] 用户撤回授权: openid={openid}")

    elif event == "user_authorization_cancellation":
        cur = db.cursor()
        cur.execute(
            "UPDATE users SET wechat_info = NULL, updated_at = NOW() "
            "WHERE wechat_info->>'openid' = %s",
            (openid,)
        )
        db.commit()
        cur.close()
        logger.info(f"[WeChat] 用户注销: openid={openid}")

    return "success"
