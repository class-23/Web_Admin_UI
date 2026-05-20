import random
from fastapi import APIRouter, Depends, HTTPException, Request, Response
import string
from login import config
from login.database import get_db
from login.schemas import RegisterRequest, LoginRequest, SendCodeRequest, ApiResponse
from login.schemas import ForgotPasswordSendCodeRequest, ForgotPasswordVerifyRequest, ResetPasswordRequest, TokenVerifyRequest
from login.schemas import ChangePasswordRequest
from login.auth import verify_password, get_password_hash, create_access_token
from login.auth import set_auth_cookie, clear_auth_cookie, get_current_user_from_cookie, require_auth
from login.code_store import store_code, get_code, can_resend, clear_code
from login.limiter import limiter
from login.sms_utils import send_sms
from jose import jwt, JWTError
from datetime import datetime, timedelta
import psycopg2.extras

router = APIRouter()


@router.post("/send-code", response_model=ApiResponse)
@limiter.limit("5/minute")
def send_code(request: Request, req: SendCodeRequest):
    phone = req.phone
    if not can_resend(phone):
        raise HTTPException(status_code=429, detail="请60秒后再获取验证码")

    code = ''.join(random.choices(string.digits, k=6))
    store_code(phone, code)
    success, msg = send_sms(phone, code)
    if not success:
        clear_code(phone)
        raise HTTPException(status_code=500, detail=msg)
    return ApiResponse(code=0, message=msg)


@router.post("/register", response_model=ApiResponse)
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest, db = Depends(get_db)):
    stored_code = get_code(req.phone)
    if stored_code is None or stored_code != req.code:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")

    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM users WHERE phone = %s", (req.phone,))
    if cur.fetchone():
        cur.close()
        raise HTTPException(status_code=409, detail="该手机号已注册")

    cur.execute("SELECT id FROM users WHERE username = %s", (req.username,))
    if cur.fetchone():
        cur.close()
        raise HTTPException(status_code=409, detail="该用户名已存在")

    hashed_pw = get_password_hash(req.password)
    cur.execute(
        "INSERT INTO users (phone, username, password, miyao_key) VALUES (%s,%s,%s,%s) RETURNING id",
        (req.phone, req.username, hashed_pw, req.secret_key)
    )
    db.commit()
    cur.close()
    return ApiResponse(code=0, message="注册成功")


@router.post("/login", response_model=ApiResponse)
@limiter.limit("5/minute")
def login(request: Request, response: Response, req: LoginRequest, db = Depends(get_db)):
    account = req.account

    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if account.isdigit() and len(account) == 11:
        cur.execute("SELECT * FROM users WHERE phone = %s", (account,))
    else:
        cur.execute("SELECT * FROM users WHERE username = %s", (account,))
    user = cur.fetchone()
    cur.close()

    if user is None or not verify_password(req.password, user["password"]):
        return ApiResponse(code=401, message="手机号/用户名或密码错误")

    set_auth_cookie(response, {"sub": str(user["id"]), "username": user["username"]})
    return ApiResponse(code=0, message="登录成功", data={"username": user["username"]})


@router.post("/forgot-password/send-code", response_model=ApiResponse)
@limiter.limit("5/minute")
def forgot_password_send_code(request: Request, req: ForgotPasswordSendCodeRequest, db = Depends(get_db)):
    phone = req.phone
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
    if cur.fetchone() is None:
        cur.close()
        raise HTTPException(status_code=400, detail="该手机号未注册")
    cur.close()
    if not can_resend(phone):
        raise HTTPException(status_code=429, detail="请60秒后再获取验证码")
    code = ''.join(random.choices(string.digits, k=6))
    store_code(phone, code)
    success, msg = send_sms(phone, code)
    if not success:
        clear_code(phone)
        raise HTTPException(status_code=500, detail=msg)
    return ApiResponse(code=0, message=msg)


@router.post("/forgot-password/verify", response_model=ApiResponse)
@limiter.limit("5/minute")
def forgot_password_verify(request: Request, req: ForgotPasswordVerifyRequest, db = Depends(get_db)):
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE phone = %s", (req.phone,))
    user = cur.fetchone()
    cur.close()
    if user is None:
        raise HTTPException(status_code=400, detail="该手机号未注册")
    stored_code = get_code(req.phone)
    if stored_code is None or stored_code != req.code:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    reset_token = create_access_token(
        data={"sub": str(user["id"]), "phone": req.phone, "purpose": "reset_password"},
        expires_delta=timedelta(minutes=10)
    )
    return ApiResponse(code=0, message="验证通过", data={"reset_token": reset_token})


@router.post("/forgot-password/reset", response_model=ApiResponse)
@limiter.limit("5/minute")
def forgot_password_reset(request: Request, req: ResetPasswordRequest, db = Depends(get_db)):
    try:
        payload = jwt.decode(req.reset_token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        if payload.get("purpose") != "reset_password":
            raise HTTPException(status_code=400, detail="无效的重置令牌")
        phone = payload.get("phone")
        if phone is None:
            raise HTTPException(status_code=400, detail="无效的重置令牌")
    except JWTError:
        raise HTTPException(status_code=400, detail="重置令牌无效或已过期")
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()
    if user is None:
        cur.close()
        raise HTTPException(status_code=400, detail="用户不存在")
    hashed = get_password_hash(req.password)
    cur.execute(
        "UPDATE users SET password = %s, password_changed_at = NOW(), updated_at = NOW() WHERE phone = %s",
        (hashed, phone)
    )
    db.commit()
    cur.close()
    return ApiResponse(code=0, message="密码重置成功")


@router.post("/verify_token", response_model=ApiResponse)
@limiter.limit("30/minute")
def verify_token(request: Request, req: TokenVerifyRequest):
    try:
        payload = jwt.decode(req.token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        username = payload.get("username", "")
        exp = payload.get("exp", 0)
        from datetime import datetime
        expires_at = datetime.utcfromtimestamp(exp).isoformat() if exp else ""
        return ApiResponse(code=0, message="令牌有效", data={"valid": True, "username": username, "expires_at": expires_at})
    except JWTError:
        return ApiResponse(code=0, message="令牌有效", data={"valid": False})


@router.post("/logout", response_model=ApiResponse)
def logout(response: Response):
    clear_auth_cookie(response)
    return ApiResponse(code=0, message="已退出登录")


@router.get("/current_user", response_model=ApiResponse)
@limiter.limit("30/minute")
def current_user(request: Request, db = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if user is None:
        return ApiResponse(code=0, message="未登录", data=None)
    return ApiResponse(code=0, message="成功", data={"username": user["username"], "is_admin": False})


@router.post("/change_password", response_model=ApiResponse)
@limiter.limit("5/minute")
def change_password(request: Request, response: Response, req: ChangePasswordRequest, user = Depends(require_auth), db = Depends(get_db)):
    if not verify_password(req.old_password, user["password"]):
        raise HTTPException(status_code=400, detail="旧密码不正确")

    if req.old_password == req.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")

    hashed = get_password_hash(req.new_password)
    cur = db.cursor()
    cur.execute(
        "UPDATE users SET password = %s, password_changed_at = NOW(), updated_at = NOW() WHERE id = %s",
        (hashed, user["id"])
    )
    db.commit()
    cur.close()
    clear_auth_cookie(response)

    return ApiResponse(code=0, message="密码修改成功，请重新登录", data={"username": user["username"]})
