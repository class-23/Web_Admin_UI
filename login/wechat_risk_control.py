"""
微信登录风控组件
"""


class WeChatRiskControl:
    """
    微信登录风控引擎。
    基于 login_audit_log 表对登录行为进行实时检测。
    """

    @staticmethod
    def check_rate_limit(db, openid: str, ip: str) -> dict:
        """
        对指定 openid 和 IP 进行速率检测。
        返回: {"blocked": bool, "reason": str, "retry_after": int}
        """
        cur = db.cursor()

        # R11: openid 级别限流（5分钟内失败 >= 5 次）
        cur.execute(
            "SELECT COUNT(*) FROM login_audit_log "
            "WHERE openid = %s AND created_at > NOW() - INTERVAL '5 minutes' "
            "AND status IN ('failed', 'rate_limited')",
            (openid,)
        )
        openid_failures = cur.fetchone()[0]

        if openid_failures >= 5:
            cur.close()
            return {
                "blocked": True,
                "reason": f"openid 短时高频失败 ({openid_failures}次)",
                "retry_after": 900,  # 15 分钟
            }

        # R12: IP 级别限流（1小时内失败 >= 20 次）
        cur.execute(
            "SELECT COUNT(*) FROM login_audit_log "
            "WHERE ip = %s AND created_at > NOW() - INTERVAL '1 hour' "
            "AND status = 'failed'",
            (ip,)
        )
        ip_failures = cur.fetchone()[0]

        if ip_failures >= 20:
            cur.close()
            return {
                "blocked": True,
                "reason": f"IP 短时高频失败 ({ip_failures}次)",
                "retry_after": 1800,  # 30 分钟
            }

        cur.close()
        return {"blocked": False, "reason": "", "retry_after": 0}

    @staticmethod
    def detect_anomaly(db, openid: str, user_id: int, ip: str) -> dict:
        """
        检测异常行为模式。
        返回: {"anomaly": bool, "alerts": [str]}
        """
        alerts = []

        # R13: 同一 openid 从多个 IP 扫码
        cur = db.cursor()
        cur.execute(
            "SELECT DISTINCT ip FROM login_audit_log "
            "WHERE openid = %s AND created_at > NOW() - INTERVAL '10 minutes'"
            "AND method = 'wechat_scan'",
            (openid,)
        )
        ips = [row[0] for row in cur.fetchall()]
        if len(ips) >= 3:
            alerts.append(f"同一 openid 在 10 分钟内从 {len(ips)} 个不同 IP 扫码")

        # R14: 异地登录检测（仅针对已绑定用户）
        if user_id:
            cur.execute(
                "SELECT ip FROM login_audit_log "
                "WHERE user_id = %s AND method = 'wechat_scan' "
                "AND status = 'success' ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            )
            last_ip = cur.fetchone()
            if last_ip and last_ip[0] != ip:
                alerts.append(f"异地登录: 上次IP={last_ip[0]}, 本次IP={ip}")

        cur.close()
        return {"anomaly": len(alerts) > 0, "alerts": alerts}
