"""
QuantClaw UDP广播接收器模块 — DEPRECATED FACADE

⚠️ DEPRECATED: canonical 实现位于 `app.utils.quantclaw_receiver.udp_receiver`。
   本文件保留仅为兼容历史测试，Phase-3 删除。详见 `docs/adr/0001-architecture-unification.md`。

处理设备发送的UDP广播消息，支持设备注册和心跳。
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from typing import Any, Optional

from .config import QuantClawConfig
from .database import DatabaseManager
from .utils import extract_macs, first_value, normalize_mac, parse_bool, as_int, pick, server_time_str


logger = logging.getLogger("quantclaw.udp")


class UDPBroadcastReceiver:
    """UDP广播接收器，处理设备的广播注册和心跳消息"""
    
    def __init__(self, config: QuantClawConfig, db_manager: DatabaseManager):
        self.config = config
        self.db_manager = db_manager
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def start(self) -> None:
        """启动UDP接收器"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="quantclaw-udp")
        self._thread.start()
        logger.info("UDP 广播接收器已启动 (端口 %s), 响应端口 %s", 
                   self.config.udp_bind_port, self.config.udp_response_port)

    def stop(self) -> None:
        """停止UDP接收器"""
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("UDP 广播接收器已停止")

    def _run(self) -> None:
        """UDP接收器主循环"""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._sock.settimeout(1.0)
        
        try:
            self._sock.bind(("0.0.0.0", self.config.udp_bind_port))
        except OSError as e:
            logger.error("UDP 绑定端口 %s 失败: %s", self.config.udp_bind_port, e)
            return

        logger.info("UDP 监听 0.0.0.0:%s 就绪，等待设备广播...", self.config.udp_bind_port)
        
        while self._running:
            try:
                data, addr = self._sock.recvfrom(65535)
                self._handle_packet(data, addr)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    logger.exception("UDP 接收错误")
                break

    def _handle_packet(self, data: bytes, addr: tuple[str, int]) -> None:
        """处理接收到的UDP数据包"""
        client_ip = addr[0]
        try:
            payload = json.loads(data.decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.debug("[UDP] 来自 %s 的非 JSON 数据 (%d bytes), 跳过", client_ip, len(data))
            return

        if not isinstance(payload, dict):
            return

        logger.info("[UDP广播] 来自 %s:%s | 数据=%s", 
                   client_ip, addr[1], json.dumps(payload, ensure_ascii=False)[:500])

        inner = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        raw_mac = pick(inner, "mac", "MAC", "deviceMac", "device_mac", "macAddress", "mac_address", "id", default="")
        if not raw_mac:
            raw_mac = pick(payload, "mac", "MAC", "deviceMac", "device_mac", "macAddress", "mac_address", "id", default="")
        
        mac = normalize_mac(raw_mac)
        if mac is None:
            logger.warning("[UDP] 来自 %s 的数据包缺少有效 MAC 地址", client_ip)
            self._send_response(client_ip, {"code": 1002, "message": "invalid mac", "data": None})
            return

        self._send_response(client_ip, {"code": 0, "message": "ack", "data": {"mac": mac, "serverTime": server_time_str()}})

        p = {str(k): first_value(v) for k, v in inner.items()}
        p["ip"] = str(pick(p, "ip", "lastIp", "last_ip", "deviceIp", "clientIp") or client_ip)
        p["hostname"] = str(pick(p, "hostname", "host", "name", default=""))
        p["model"] = str(pick(p, "model", "deviceModel", "device_model", default=""))
        p["firmwareVersion"] = str(pick(p, "firmwareVersion", "firmware_version", "firmware", "version", default=""))
        p["ssid"] = str(pick(p, "ssid", "lastSsid", "last_ssid", default=""))
        p["interfaces"] = p.get("interfaces") if isinstance(p.get("interfaces"), list) else []
        p["ttydEnabled"] = parse_bool(pick(p, "ttydEnabled", "ttyd_enabled", "ttyd", default=False), False)
        p["ttydPort"] = as_int(pick(p, "ttydPort", "ttyd_port", default=7681), 7681)
        p["mdnsHost"] = str(pick(p, "mdnsHost", "mdns_host", "mdns", default=""))
        p["httpPort"] = as_int(pick(p, "httpPort", "http_port", "port", default=80), 80)
        p["accessScope"] = str(pick(p, "accessScope", "access_scope", default="lan"))
        p["phone"] = str(pick(p, "phone", "phone_number", "phoneNum", "phone_num", default=""))
        p["internetAvailable"] = parse_bool(pick(p, "internetAvailable", "internet_available", "internet", default=False), False)
        p["status"] = str(pick(p, "status", "state", default=""))
        p["_observedMacs"] = extract_macs(inner)
        
        if mac not in p["_observedMacs"]:
            p["_observedMacs"].insert(0, mac)

        is_hb = any(k in inner for k in ("internetAvailable", "internet_available", "internet", "status", "state"))
        st = server_time_str()

        try:
            if is_hb:
                hb_err, data = self.db_manager.process_heartbeat(mac, p)
                if hb_err is not None:
                    logger.warning("[UDP心跳] MAC=%s 失败: %s", mac, hb_err.get("message"))
                else:
                    logger.info("[UDP心跳] MAC=%s ip=%s status=%s", mac, p.get("ip"), p.get("status"))
            else:
                data = self.db_manager.register_device(mac, p)
                logger.info("[UDP注册] MAC=%s host=%s ip=%s | isNew=%s", 
                           mac, p.get("hostname"), p.get("ip"), data["isNew"])
        except Exception as e:
            logger.exception("[UDP] 处理数据包失败: %s", e)

    def _send_response(self, client_ip: str, data: dict) -> None:
        """发送UDP响应"""
        try:
            resp = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1.0)
            sock.sendto(resp, (client_ip, self.config.udp_response_port))
            sock.close()
        except OSError as e:
            logger.debug("[UDP] 响应发送失败 %s:%s - %s", 
                        client_ip, self.config.udp_response_port, e)