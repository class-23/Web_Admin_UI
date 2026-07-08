class UserRoles:
    """用户权限常量定义"""
    REGULAR = "role_usr_8f7d"  # 普通用户 - 仅本网站可登录,不可登录管理员网站
    ADMIN = "role_adm_3k9p"    # 管理员用户 - 本网站与管理员网站均可登录

    # 所有合法角色白名单(系统只允许以下两种角色,严格控制登录权限边界)
    ALL_ROLES = (REGULAR, ADMIN)

    @classmethod
    def can_login_here(cls, role: str) -> bool:
        """判断是否允许在本网站登录(仅普通用户和管理员可以登录)"""
        return role in cls.ALL_ROLES