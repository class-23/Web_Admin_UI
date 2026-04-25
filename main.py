"""
QuantClaw 网络扫描服务
扫描当前网段设备，找出名为 quant 的设备
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import subprocess
import re
import socket
import json
import platform
import time

IS_WINDOWS = platform.system().lower() in ('windows', 'windows_nt')

app = FastAPI(title="QuantClaw Network Scanner")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")


class Device(BaseModel):
    ip: str
    mac: str
    hostname: Optional[str] = None
    name: Optional[str] = None
    is_quant: bool = False


class ScanResult(BaseModel):
    devices: List[Device]
    quant_device: Optional[Device] = None
    total: int
    gateway: str


def get_gateway() -> str:
    """获取默认网关"""
    try:
        if IS_WINDOWS:
            result = subprocess.run(
                ["powershell", "-Command", "ipconfig"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                line = line.strip()
                if 'Default Gateway' in line or '默认网关' in line:
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        return match.group(1)
        else:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=5
            )
            match = re.search(r'default via (\d+\.\d+\.\d+\.\d+)', result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split('.')
        return f"{parts[0]}.{parts[1]}.{parts[2]}.1"
    except Exception:
        return "192.168.1.1"


def get_local_ip() -> str:
    """获取本机 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def scan_with_arp() -> List[Device]:
    """使用 arp 扫描局域网"""
    devices = []
    
    gateway = get_gateway()
    local_ip = get_local_ip()
    
    if local_ip == "127.0.0.1":
        return devices
    
    parts = local_ip.split('.')
    network_prefix = f"{parts[0]}.{parts[1]}.{parts[2]}"
    
    try:
        if IS_WINDOWS:
            import threading
            
            def ping_host(ip):
                try:
                    subprocess.run(
                        ["ping", "-n", "1", "-w", "200", ip],
                        capture_output=True, timeout=2
                    )
                except Exception:
                    pass
            
            threads = []
            for i in range(1, 255):
                ip = f"{network_prefix}.{i}"
                thread = threading.Thread(target=ping_host, args=(ip,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join(timeout=2)
        else:
            subprocess.run(
                ["sh", "-c", f"for i in $(seq 1 254); do (ping -c 1 -W 1 {network_prefix}.$i > /dev/null 2>&1 &); done"],
                capture_output=True, timeout=10
            )
    except Exception:
        pass
    
    time.sleep(3)
    
    try:
        if IS_WINDOWS:
            result = subprocess.run(
                ["powershell", "-Command", "arp -a"],
                capture_output=True, text=True, timeout=5
            )
            
            current_interface = None
            for line in result.stdout.split('\n'):
                line = line.strip()
                
                if 'Interface:' in line:
                    match = re.search(r'Interface:\s*(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        current_interface = match.group(1)
                    continue
                
                if not line or 'Internet 地址' in line or 'Physical Address' in line:
                    continue
                
                match = re.match(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-]+)\s+(\S+)', line, re.IGNORECASE)
                if match:
                    ip = match.group(1)
                    mac_raw = match.group(2)
                    mac = mac_raw.replace('-', ':').upper() if '-' in mac_raw else mac_raw.upper()
                    entry_type = match.group(3).lower()
                    
                    if not mac or mac == "FF:FF:FF:FF:FF:FF":
                        continue
                    if entry_type not in ('dynamic', '动态'):
                        continue
                    
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        hostname = ""
                    
                    name = None
                    is_quant = False
                    check_str = (hostname or "").lower()
                    
                    if "quant" in check_str:
                        name = hostname
                        is_quant = True
                    
                    pi_prefixes = ["B8:27:EB", "DC:A6:32", "E4:5F:01", "28:CD:C1", "2C:CF:67"]
                    for prefix in pi_prefixes:
                        if mac.startswith(prefix):
                            name = "Raspberry Pi (possible quant)"
                            is_quant = True
                            break
                    
                    device = Device(
                        ip=ip,
                        mac=mac,
                        hostname=hostname if hostname else None,
                        name=name,
                        is_quant=is_quant
                    )
                    devices.append(device)
        else:
            subprocess.run(["ip", "neigh", "flush", "all"], capture_output=True)
            
            result = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True)
            
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts_line = line.split()
                if len(parts_line) < 4:
                    continue
                
                ip = parts_line[0]
                mac = ""
                hostname = ""
                
                for i, p in enumerate(parts_line):
                    if re.match(r'([0-9a-f]{2}:){5}[0-9a-f]{2}', p.lower()):
                        mac = p.upper()
                        break
                
                if not mac or ip == gateway:
                    continue
                
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except Exception:
                    pass
                
                name = None
                is_quant = False
                check_str = (hostname or "").lower()
                
                if "quant" in check_str:
                    name = hostname
                    is_quant = True
                
                pi_prefixes = ["B8:27:EB", "DC:A6:32", "E4:5F:01", "28:CD:C1", "2C:CF:67"]
                if mac:
                    for prefix in pi_prefixes:
                        if mac.startswith(prefix):
                            name = "Raspberry Pi (possible quant)"
                            is_quant = True
                            break
                
                device = Device(
                    ip=ip,
                    mac=mac,
                    hostname=hostname if hostname else None,
                    name=name,
                    is_quant=is_quant
                )
                devices.append(device)
                
    except Exception as e:
        print(f"ARP scan error: {e}")
    
    return devices


def scan_with_nmap() -> List[Device]:
    """使用 nmap 扫描 (如果可用)"""
    if IS_WINDOWS:
        return []
    
    devices = []
    
    try:
        local_ip = get_local_ip()
        parts = local_ip.split('.')
        network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        
        result = subprocess.run(
            ["nmap", "-sn", "-PR", network],
            capture_output=True, text=True, timeout=30
        )
        
        current_ip = None
        current_mac = None
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            
            if 'Nmap scan report' in line:
                match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                if match:
                    current_ip = match.group(1)
            
            elif 'MAC Address' in line:
                match = re.search(r'([0-9A-Fa-f:]{17})', line)
                if match:
                    current_mac = match.group(1).upper()
            
            elif 'Host is up' in line and current_ip and current_mac:
                hostname = None
                try:
                    hostname = socket.gethostbyaddr(current_ip)[0]
                except Exception:
                    pass
                
                name = None
                is_quant = False
                if hostname and "quant" in hostname.lower():
                    name = hostname
                    is_quant = True
                
                device = Device(
                    ip=current_ip,
                    mac=current_mac,
                    hostname=hostname if hostname else None,
                    name=name,
                    is_quant=is_quant
                )
                devices.append(device)
                
                current_ip = None
                current_mac = None
        
    except FileNotFoundError:
        print("nmap not installed")
    except Exception as e:
        print(f"nmap scan error: {e}")
    
    return devices


def get_quant_device(devices: List[Device]) -> Optional[Device]:
    """找出名为 quant 的设备"""
    for device in devices:
        if device.is_quant:
            return device
    
    # 如果没找到，尝试通过 MAC 厂商识别树莓派
    pi_prefixes = ["B8:27:EB", "DC:A6:32", "E4:5F:01", "28:CD:C1", "2C:CF:67"]
    for device in devices:
        for prefix in pi_prefixes:
            if device.mac.startswith(prefix):
                device.name = "Raspberry Pi (possible quant)"
                device.is_quant = True
                return device
    
    return None


@app.get("/", response_class=HTMLResponse)
async def root():
    """返回前端页面"""
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/scan", response_model=ScanResult)
async def scan_network():
    """扫描网络设备"""
    gateway = get_gateway()
    
    # 优先使用 nmap，不行就用 arp
    devices = scan_with_nmap()
    if not devices:
        devices = scan_with_arp()
    
    # 再次尝试 ARP 补充
    if not devices:
        devices = scan_with_arp()
    
    quant_device = get_quant_device(devices)
    
    return ScanResult(
        devices=devices,
        quant_device=quant_device,
        total=len(devices),
        gateway=gateway
    )


@app.get("/api/info")
async def get_info():
    """获取本机信息"""
    return {
        "local_ip": get_local_ip(),
        "gateway": get_gateway(),
        "hostname": socket.gethostname()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
