class UserRoles:
    """用户权限常量定义"""
    REGULAR = "role_usr_8f7d"  # 普通用户 - 本网站可登录
    ADMIN = "role_adm_3k9p"    # 管理员用户 - 本网站不可登录
    SPECIAL = "role_spv_7m2x"  # 特殊权限用户 - 本网站可登录

    @classmethod
    def can_login_here(cls, role: str) -> bool:
        """判断是否允许在本网站登录"""
        return role in (cls.REGULAR, cls.SPECIAL)
