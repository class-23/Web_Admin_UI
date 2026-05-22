# QuantClaw Network Scanner

局域网设备扫描服务，用于发现网络中名为 `quant` 的设备（树莓派），并提供Web界面进行设备管理和文件操作。
测试

## 功能特性

- **设备扫描**：自动扫描局域网内的所有设备，支持 nmap 和 ARP 两种扫描方式
- **设备识别**：自动识别 Quant 设备（Raspberry Pi）
- **网络信息**：实时显示网关、本机 IP 等网络信息
- **设备管理**：支持设备连接状态监控和管理
- **文件管理**：支持本地和 SSH 远程文件操作（浏览、创建、编辑、删除、复制、移动）
- **用户认证**：内置用户认证系统，支持多用户管理
- **磁盘监控**：显示磁盘使用情况
- **响应式 Web 界面**：支持手机访问

## 技术栈

- **后端**: FastAPI + Uvicorn
- **前端**: 原生 HTML/CSS/JS（响应式设计）
- **扫描**: nmap / ARP
- **远程操作**: Paramiko (SSH)
- **数据验证**: Pydantic

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

# Windows
# 从官网下载并安装：https://nmap.org/download.html
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
| `/` | GET | Web 主界面 |
| `/login` | GET | 登录页面 |
| `/file_manager` | GET | 文件管理页面 |
| `/api/scan` | GET | 扫描局域网设备 |
| `/api/scan/status` | GET | 获取扫描状态 |
| `/api/info` | GET | 获取本机网络信息 |
| `/api/devices` | GET | 获取所有设备信息（包含连接状态） |
| `/api/device/connect` | POST | 连接设备 |
| `/api/device/disconnect` | POST | 断开设备连接 |
| `/api/device/status/{ip}` | GET | 获取设备状态 |
| `/api/files` | GET | 列出文件和文件夹 |
| `/api/files/rename` | POST | 重命名文件或文件夹 |
| `/api/files/delete` | POST | 删除文件或文件夹 |
| `/api/files/copy` | POST | 复制文件或文件夹 |
| `/api/files/move` | POST | 移动文件或文件夹 |
| `/api/files/create-folder` | POST | 创建文件夹 |
| `/api/files/create-file` | POST | 创建文件 |
| `/api/files/save` | POST | 保存文件内容 |
| `/api/files/read` | POST | 读取文件内容 |
| `/api/disk_usage` | GET | 获取磁盘使用情况 |
| `/api/login` | POST | 用户登录 |
| `/api/verify_token` | POST | 验证令牌 |
| `/api/logout` | POST | 用户登出 |
| `/api/current_user` | GET | 获取当前用户信息 |
| `/api/users` | GET | 获取用户列表 |
| `/api/users` | POST | 创建新用户 |
| `/api/users/{username}` | PUT | 更新用户信息 |
| `/api/users/{username}` | DELETE | 删除用户 |

| `/api/ssh/status` | GET | 获取 SSH 连接状态 |

### 扫描结果示例

```json
{
  "devices": [
    {
      "ip": "192.168.1.100",
      "mac": "B8:27:EB:12:34:56",
      "hostname": "quant.local",
      "name": "quant.local",
      "is_quant": true,
      "connection_status": "idle",
      "is_connected": false,
      "connected_at": null
    }
  ],
  "quant_device": {
    "ip": "192.168.1.100",
    "mac": "B8:27:EB:12:34:56",
    "hostname": "quant.local",
    "name": "quant.local",
    "is_quant": true,
    "connection_status": "idle",
    "is_connected": false,
    "connected_at": null
  },
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
├── templates/           # Web 界面
│   ├── index.html       # 主页面
│   ├── login.html       # 登录页面
│   └── file_manager.html # 文件管理页面
└── .gitignore           # Git 忽略文件
```

## 系统要求

- Python 3.8+
- Linux/macOS/Windows
- ARP 扫描在 Linux/macOS 需要 root 权限
- nmap（可选，推荐安装以提高扫描效果）

## 默认登录信息

- **用户名**: admin
- **密码**: openclaw123456

## 许可证

MIT
