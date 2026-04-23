# QuantClaw Network Scanner

局域网设备扫描服务，用于发现网络中名为 `quant` 的设备（树莓派）。

## 功能特性

- 自动扫描局域网内的所有设备
- 自动识别 Quant 设备（Raspberry Pi）
- 支持 nmap 和 ARP 两种扫描方式
- 实时显示网关、本机 IP 等网络信息
- 响应式 Web 界面，支持手机访问

## 技术栈

- **后端**: FastAPI + Uvicorn
- **前端**: 原生 HTML/CSS/JS（响应式设计）
- **扫描**: nmap / ARP

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 安装 nmap（可选，推荐）

```bash
# Ubuntu/Debian
sudo apt install nmap

# macOS
brew install nmap
```

### 启动服务

```bash
./start.sh
```

或直接运行：

```bash
python3 main.py
```

服务启动后访问 http://localhost:8000

## API 接口

| 接口 | 方法 | 描述 |
|------|------|------|
| `/` | GET | Web 界面 |
| `/api/scan` | GET | 扫描局域网设备 |
| `/api/info` | GET | 获取本机网络信息 |

### 扫描结果示例

```json
{
  "devices": [
    {
      "ip": "192.168.1.100",
      "mac": "B8:27:EB:12:34:56",
      "hostname": "quant.local",
      "name": "quant.local",
      "is_quant": true
    }
  ],
  "quant_device": {...},
  "total": 5,
  "gateway": "192.168.1.1"
}
```

## 项目结构

```
quantclaw_web/
├── main.py              # FastAPI 应用
├── requirements.txt     # Python 依赖
├── start.sh             # 启动脚本
├── static/              # 静态文件目录
└── templates/
    └── index.html       # Web 界面
```

## 系统要求

- Python 3.8+
- Linux/macOS（ARP 扫描需要 root 权限）

## 许可证

MIT
