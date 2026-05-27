"""
QuantClaw 工具函数模块

包含所有通用的工具函数，如签名验证、数据解析、MAC地址处理等。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import socket
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from .exceptions import InvalidMacError


MAC_RE = re.compile(r"^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")
MAC_FIND_RE = re.compile(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}")

REGISTER_FIELDS = (
    "mac", "hostname", "model", "firmwareVersion", "ssid", "ip",
    "interfaces", "ttydEnabled", "ttydPort", "mdnsHost", "httpPort",
    "accessScope", "timestamp",
)

HEARTBEAT_FIELDS = (
    "mac", "firmwareVersion", "ssid", "ip", "internetAvailable", "status",
    "interfaces", "ttydEnabled", "ttydPort", "mdnsHost", "httpPort",
    "accessScope", "timestamp",
)

ONLINE_HEARTBEAT_TIMEOUT_SEC = 180


def make_sign(method: str, path: str, timestamp: str, body_bytes: bytes, secret: str) -> str:
    """生成HMAC-SHA256签名"""
    body_sha256 = hashlib.sha256(body_bytes).hexdigest()
    payload = f"{method}\n{path}\n{timestamp}\n{body_sha256}"
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def normalize_signature(sig: str) -> str:
    """标准化签名格式"""
    sig = sig.strip()
    if sig.lower().startswith("sha256="):
        sig = sig.split("=", 1)[1]
    return sig.lower()


def parse_utc_timestamp(s: str) -> Optional[datetime]:
    """解析UTC时间戳字符串"""
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def normalize_mac(mac: Any) -> Optional[str]:
    """标准化MAC地址格式"""
    if not isinstance(mac, str):
        return None
    cleaned = mac.strip().replace("-", ":").replace(" ", "").replace("_", "").replace(".", "")
    if not MAC_RE.match(cleaned):
        cleaned2 = ":".join(cleaned[i:i+2] for i in range(0, len(cleaned), 2))
        if len(cleaned) == 12 and MAC_RE.match(cleaned2):
            cleaned = cleaned2
        else:
            return None
    mac_norm = cleaned.lower()
    if mac_norm == "00:00:00:00:00:00":
        return None
    return mac_norm


def mac_from_ip(ip: str) -> str:
    """从IP地址生成虚拟MAC地址"""
    digest = hashlib.sha1(ip.encode("utf-8")).digest()
    parts = bytearray(digest[:6])
    parts[0] = (parts[0] | 0x02) & 0xFE
    return ":".join(f"{x:02x}" for x in parts)


def extract_macs(value: Any) -> list[str]:
    """从任意值中提取所有MAC地址"""
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(value)
    macs: list[str] = []
    seen: set[str] = set()
    for match in MAC_FIND_RE.findall(text):
        mac = normalize_mac(match)
        if mac is not None and mac not in seen:
            seen.add(mac)
            macs.append(mac)
    return macs


def server_time_str() -> str:
    """获取当前服务器时间字符串（UTC）"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_server_time(s: str) -> Optional[datetime]:
    """解析服务器时间字符串"""
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def as_bool(v: Any) -> int:
    """转换为布尔值的整数表示"""
    return 1 if parse_bool(v, False) else 0


def as_int(v: Any, default: int = 0) -> int:
    """安全转换为整数"""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def first_value(v: Any) -> Any:
    """获取列表的第一个值，或原值"""
    if isinstance(v, list):
        return v[0] if v else ""
    return v


def parse_bool(v: Any, default: bool = False) -> bool:
    """解析布尔值"""
    v = first_value(v)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "yes", "y", "online", "ok", "enabled", "enable"):
            return True
        if s in ("0", "false", "no", "n", "offline", "disabled", "disable", ""):
            return False
    return default


def pick(p: dict[str, Any], *names: str, default: Any = "") -> Any:
    """从字典中按优先级获取值"""
    for name in names:
        if name in p and p[name] not in (None, ""):
            return p[name]
    return default


def parse_text_body(body_bytes: bytes) -> dict[str, Any]:
    """解析文本请求体（支持JSON和表单格式）"""
    text = body_bytes.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        return {"payload": obj}
    except json.JSONDecodeError:
        pass
    parsed = parse_qs(text, keep_blank_values=True)
    if parsed:
        return {k: first_value(v) for k, v in parsed.items()}
    return {"payload": text}


def client_ip_from_headers(hdrs: dict[str, str], fallback: str) -> str:
    """从请求头中获取客户端IP"""
    for key in ("x-device-ip", "X-Device-IP", "x-forwarded-for", "X-Forwarded-For", "x-real-ip", "X-Real-IP"):
        val = hdrs.get(key)
        if val:
            return val.split(",")[0].strip()
    return fallback


def local_ipv4_addrs() -> set[str]:
    """获取本地IPv4地址列表"""
    addrs = {"127.0.0.1", "0.0.0.0"}
    try:
        host = socket.gethostname()
        addrs.update(x[4][0] for x in socket.getaddrinfo(host, None, socket.AF_INET))
    except OSError:
        pass
    return addrs


LOCAL_IPV4_ADDRS = local_ipv4_addrs()


def normalize_payload_defaults(path: str, payload: dict[str, Any], client_ip: str) -> tuple[str, dict[str, Any]]:
    """标准化请求载荷并设置默认值"""
    observed_macs = extract_macs(payload)
    p = {str(k): first_value(v) for k, v in payload.items()}
    
    ip = str(
        pick(p, "ip", "lastIp", "last_ip", "deviceIp", "device_ip", "clientIp")
        or client_ip
        or ""
    )
    
    if ip in LOCAL_IPV4_ADDRS and client_ip not in LOCAL_IPV4_ADDRS:
        ip = client_ip
    
    raw_mac = pick(p, "mac", "MAC", "deviceMac", "device_mac", "macAddress", "mac_address", "wlanMac", "ethMac", "id", default="")
    mac = normalize_mac(raw_mac)
    if mac is None:
        mac = mac_from_ip(ip or client_ip)
    
    if mac not in observed_macs:
        observed_macs.insert(0, mac)

    now = server_time_str()
    p["mac"] = mac
    p["_observedMacs"] = observed_macs
    p["timestamp"] = str(pick(p, "timestamp", "ts", "time", default=now))
    p["firmwareVersion"] = str(pick(p, "firmwareVersion", "firmware_version", "firmware", "version", default=""))
    p["ssid"] = str(pick(p, "ssid", "lastSsid", "last_ssid", default=""))
    p["ip"] = ip
    p["interfaces"] = p.get("interfaces") if isinstance(p.get("interfaces"), list) else []
    p["ttydEnabled"] = parse_bool(pick(p, "ttydEnabled", "ttyd_enabled", "ttyd", default=False), False)
    p["ttydPort"] = as_int(pick(p, "ttydPort", "ttyd_port", default=7681), 7681)
    p["mdnsHost"] = str(pick(p, "mdnsHost", "mdns_host", "mdns", default="quantclaw.local"))
    p["httpPort"] = as_int(pick(p, "httpPort", "http_port", "port", default=80), 80)
    p["accessScope"] = str(pick(p, "accessScope", "access_scope", default="lan"))

    if path == "/api/device/register":
        default_hostname = f"device-{ip.replace('.', '-')}" if ip else "device"
        p["hostname"] = str(pick(p, "hostname", "host", "name", default=default_hostname))
        p["model"] = str(pick(p, "model", "deviceModel", "device_model", default=""))
    else:
        p["internetAvailable"] = parse_bool(pick(p, "internetAvailable", "internet_available", "internet", default=True), True)
        p["status"] = str(pick(p, "status", "state", default="online"))

    return mac, p


def row_to_device(row: dict[str, Any], now: datetime) -> dict[str, Any]:
    """将数据库行转换为设备字典"""
    last_seen = parse_server_time(row["last_seen_at"])
    age = int((now - last_seen).total_seconds()) if last_seen is not None else None
    is_online = age is not None and age <= ONLINE_HEARTBEAT_TIMEOUT_SEC
    
    return {
        "mac": row["mac"],
        "hostname": row["hostname"],
        "model": row["model"],
        "firmwareVersion": row["firmware_version"],
        "lastIp": row["last_ip"],
        "lastSsid": row["last_ssid"],
        "internetAvailable": bool(row["internet_available"]),
        "status": row["status"],
        "lastSeenAt": row["last_seen_at"],
        "isOnline": is_online,
        "ttydEnabled": bool(row["ttyd_enabled"]),
        "ttydPort": row["ttyd_port"],
        "mdnsHost": row["mdns_host"],
        "httpPort": row["http_port"],
        "accessScope": row["access_scope"],
        "httpUrl": f"http://{row['last_ip']}:{row['http_port']}",
        "mdnsUrl": f"http://{row['mdns_host']}/" if row["mdns_host"] else "",
        "ttydUrl": f"http://{row['last_ip']}:{row['ttyd_port']}",
        "ssh": f"ssh quant@{row['last_ip']}",
        "sshMdns": f"ssh quant@{row['mdns_host']}" if row["mdns_host"] else "",
    }