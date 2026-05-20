import re
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator


class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[dict] = None


class RegisterRequest(BaseModel):
    phone: str
    username: str
    code: str
    secret_key: str
    password: str
    confirm_password: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确，请输入中国大陆11位手机号")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 20:
            raise ValueError("用户名长度必须在3-20个字符之间")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("验证码必须是6位数字")
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v):
        if not re.match(r"^[a-zA-Z0-9]+$", v):
            raise ValueError("密钥只能包含数字和字母")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("密码长度至少为8位")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含小写字母")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含大写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v

    @model_validator(mode="after")
    def validate_passwords_match(self):
        pw = self.password
        cpw = self.confirm_password
        if pw != cpw:
            raise ValueError("两次输入的密码不一致")
        return self


class LoginRequest(BaseModel):
    account: str
    password: str


class SendCodeRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确，请输入中国大陆11位手机号")
        return v


class ForgotPasswordSendCodeRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确，请输入中国大陆11位手机号")
        return v


class ForgotPasswordVerifyRequest(BaseModel):
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确，请输入中国大陆11位手机号")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v):
        if not re.match(r"^\d{6}$", v):
            raise ValueError("验证码必须是6位数字")
        return v


class ResetPasswordRequest(BaseModel):
    reset_token: str
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("密码长度至少为8位")
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须包含字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        if not re.search(r"[^a-zA-Z0-9]", v):
            raise ValueError("密码必须包含特殊符号")
        return v

    @model_validator(mode="after")
    def validate_passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class TokenVerifyRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError("密码长度至少为8位")
        if not re.search(r"[a-z]", v):
            raise ValueError("密码必须包含小写字母")
        if not re.search(r"[A-Z]", v):
            raise ValueError("密码必须包含大写字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须包含数字")
        return v

    @model_validator(mode="after")
    def validate_passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("两次输入的新密码不一致")
        return self
