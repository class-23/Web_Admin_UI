# QuantClaw 龙虾盒子设备管理后台

面向 IoT 智能座舱设备的全栈管理平台，提供设备注册、心跳监控、远程文件管理、SSH 运维等一站式能力。支持 HTTP/UDP 双通道设备通信，集成微信 OAuth 2.0 登录，通过 Docker 容器化部署。

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Templates)                      │
│       原生 HTML/CSS/JS + Tailwind CSS + RemixIcon        │
│            index.html / file_manager.html / ...          │
├─────────────────────────────────────────────────────────┤
│                  后端 (FastAPI + Uvicorn)                 │
│  ┌──────────┬──────────┬───────────┬──────────────────┐ │
│  │ 认证模块  │ 设备管理  │ 文件管理   │  SSH / 系统管理   │ │
│  │ auth     │ devices  │ files     │  ssh / settings  │ │
│  └──────────┴──────────┴───────────┴──────────────────┘ │
│  ┌────────────────────────────────────────────────────┐  │
│  │              UDP 广播接收器 (后台线程)               │  │
│  └────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                     数据存储层                            │
│         PostgreSQL (psycopg2)  +  Redis (缓存)           │
└─────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | 异步 Web 框架，自动生成 OpenAPI 文档 |
| 前端 | 原生 HTML/CSS/JS | Tailwind CSS + RemixIcon，响应式设计 |
| 数据库 | PostgreSQL | psycopg2 原生 SQL，无 ORM |
| 缓存 | Redis | 短信验证码存储，5 分钟 TTL |
| 认证 | JWT + bcrypt | HttpOnly Cookie + API Key 双重认证 |
| 远程连接 | Paramiko | SSH 文件管理与命令执行 |
| 限流 | SlowAPI | 接口频率限制 |
| 部署 | Docker + Gitea Actions | 容器化 + CI/CD 自动部署 |

## 功能特性

### 设备管理
- **设备注册**：HTTP 接口 + UDP 广播双通道，支持 HMAC-SHA256 签名校验
- **心跳监控**：定时上报在线状态，180 秒超时离线判定，实时显示设备状态（在线/离线/未知）
- **设备列表**：按用户手机号过滤，展示 MAC、IP、主机名、固件版本、WiFi 名称等完整信息
- **设备绑定**：支持设备与用户一对一绑定，可指定主设备

### 用户认证
- 手机号注册 + 用户名/密码登录
- 短信验证码登录（Redis 存储，5 分钟有效期，60 秒发送冷却）
- JWT HttpOnly Cookie 认证 + API Key 双重认证
- 微信开放平台 OAuth 2.0 扫码登录与账号绑定
- 密码修改/重置，密码变更后 JWT 自动失效
- 两级角色权限：普通用户 / 管理员

### 远程文件管理
- 支持本地和 SSH 远程两种模式的文件浏览
- 文件/文件夹的创建、重命名、删除、复制、移动
- 文本文件在线读取与编辑保存
- SSH 连接配置与状态检测，主机地址跟随主设备 IP 自动更新

### 系统管理
- 磁盘使用情况监控（跨平台 Windows/Linux）
- 用户偏好设置（主题、语言、权限等，JSONB 存储）
- 健康检查端点
- Swagger UI 交互式 API 文档

## 项目结构

```
Web_Admin_UI/
├── main.py                    # FastAPI 应用入口，路由注册
├── app/                       # 应用核心模块
│   ├── app_factory.py         # 应用工厂
│   └── core/                  # 核心配置、数据库、安全依赖
├── login/                     # 用户认证模块
│   ├── auth.py                # JWT 生成/验证、密码加密
│   ├── database.py            # psycopg2 连接池
│   ├── code_store.py          # Redis 验证码存储
│   ├── sms_utils.py           # 短信发送
│   ├── wechat_service.py      # 微信 OAuth 服务
│   ├── wechat_router.py       # 微信登录路由
│   ├── wechat_risk_control.py # 微信风控
│   ├── limiter.py             # 接口限流配置
│   ├── password_policy.py     # 密码策略
│   ├── config.py              # 认证模块配置
│   ├── constants.py           # 角色权限常量
│   ├── schemas.py             # 请求/响应模型
│   └── routers/
│       └── auth_router.py     # 登录/注册/密码管理路由
├── quantclaw_receiver/        # 设备通信模块
│   ├── config.py              # 设备管理配置
│   ├── database.py            # 设备数据库操作（psycopg2）
│   ├── device_manager.py      # 设备管理器（注册/心跳/列表）
│   ├── udp_receiver.py        # UDP 广播接收器
│   ├── utils.py               # 签名/格式转换/设备行映射
│   └── exceptions.py          # 自定义异常
├── static/                    # 静态资源
│   ├── css/                   # 样式文件
│   └── js/                    # 前端脚本
│       ├── index.js           # 首页设备管理逻辑
│       ├── file_manager.js    # 文件管理交互
│       ├── setting.js         # 设置页面
│       └── tutorial.js        # 使用教程
├── templates/                 # Jinja2 模板
│   ├── base.html              # 基础布局
│   ├── index.html             # 首页（仪表盘）
│   ├── login.html             # 登录页
│   ├── register.html          # 注册页
│   ├── bind-wechat.html       # 微信绑定页
│   ├── file_manager.html      # 文件管理页
│   ├── devices.html           # 设备列表页
│   ├── device_detail.html     # 设备详情页
│   ├── dashboard.html         # 数据面板
│   ├── tutorial.html          # 使用教程
│   ├── setting.html           # 系统设置
│   ├── config.html            # 配置页
│   ├── change-password.html   # 修改密码
│   ├── forgot-password.html   # 忘记密码
│   └── reset-password.html    # 重置密码
├── tests/                     # 测试用例
├── docs/                      # 项目文档
│   ├── worklog.md             # 工作日志
│   ├── todo.md                # 任务清单
│   ├── databases.md           # 数据库设计文档
│   └── agents/                # Agent 配置
├── .gitea/workflows/          # CI/CD 流水线
│   ├── deploy.yml             # 自动部署
│   └── test.yml               # 自动测试
├── Dockerfile                 # Docker 镜像构建
├── docker-compose.yml         # Docker 编排
├── requirements.txt           # 生产依赖
├── requirements-dev.txt       # 开发依赖
├── .env.example               # 环境变量模板
└── start.sh                   # 启动脚本
```

## 快速开始

### 前置条件

- Python 3.8+
- PostgreSQL 数据库
- Redis 服务

### 1. 克隆项目

```bash
git clone <仓库地址>
cd Web_Admin_UI
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv

# Windows
.venv\Scripts\pip install -r requirements.txt

# Linux/macOS
.venv/bin/pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，修改数据库连接信息：

```env
# PostgreSQL 数据库
PG_HOST=localhost
PG_PORT=5432
PG_USER=quant
PG_PASSWORD=your_password
PG_DBNAME=quantclaw

# Redis 缓存
REDIS_HOST=localhost
REDIS_PORT=6379

# 应用服务器
APP_HOST=0.0.0.0
APP_PORT=8082
```

### 4. 初始化数据库

确保 PostgreSQL 中已创建数据库和自定义枚举类型：

```sql
CREATE DATABASE quantclaw;

-- 设备状态枚举
CREATE TYPE device_status AS ENUM ('registered', 'online', 'offline', 'unknown');
```

应用启动时会自动建表，无需手动执行建表 SQL。

### 5. 启动服务

```bash
# 直接运行
python main.py

# 或使用启动脚本
./start.sh
```

服务启动后访问：
- 主界面：http://localhost:8082
- API 文档（Swagger UI）：http://localhost:8082/docs
- 登录页面：http://localhost:8082/login

## API 接口概览

完整的 API 文档请访问启动后的 `/docs` 路径。

### 认证模块

| 接口 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/register` | POST | 用户注册（手机号+密码） | 无 |
| `/api/login` | POST | 密码登录 | 无 |
| `/api/login-by-sms` | POST | 短信验证码登录 | 无 |
| `/api/send-code` | POST | 发送短信验证码 | 无 |
| `/api/logout` | POST | 登出 | Cookie |
| `/api/current-user` | GET | 获取当前用户信息 | Cookie |
| `/api/change-password` | POST | 修改密码 | Cookie |
| `/api/forgot-password/send-code` | POST | 忘记密码-发送验证码 | 无 |
| `/api/forgot-password/verify` | POST | 忘记密码-验证验证码 | 无 |
| `/api/reset-password` | POST | 重置密码 | 无 |

### 微信登录

| 接口 | 方法 | 描述 |
|------|------|------|
| `/api/wechat/qrcode` | GET | 获取微信登录二维码链接 |
| `/api/wechat/callback` | GET | 微信 OAuth 回调 |
| `/api/wechat/bind` | POST | 绑定微信账号 |

### 设备管理

| 接口 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/device/register` | GET/POST | 设备注册 | 无（设备端调用） |
| `/api/device/heartbeat` | GET/POST | 设备心跳上报 | 无（设备端调用） |
| `/api/devices` | GET | 获取设备列表 | Cookie / API Key |
| `/api/devices` | POST | 创建设备 | Cookie / API Key |
| `/api/devices/{mac}` | DELETE | 删除设备 | Cookie / API Key |
| `/api/phone_search_device` | GET | 通过手机号查询设备 | 无 |

### 文件管理

| 接口 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/files` | GET | 列出目录文件 | Cookie / API Key |
| `/api/files/rename` | POST | 重命名文件/文件夹 | Cookie / API Key |
| `/api/files/delete` | POST | 删除文件/文件夹 | Cookie / API Key |
| `/api/files/copy` | POST | 复制文件/文件夹 | Cookie / API Key |
| `/api/files/move` | POST | 移动文件/文件夹 | Cookie / API Key |
| `/api/files/create-folder` | POST | 创建文件夹 | Cookie / API Key |
| `/api/files/create-file` | POST | 创建空文件 | Cookie / API Key |
| `/api/files/save` | POST | 保存文件内容 | Cookie / API Key |
| `/api/files/read` | POST | 读取文件内容 | Cookie / API Key |

### SSH 连接

| 接口 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/ssh/status` | GET | 查询 SSH 连接状态 | Cookie / API Key |
| `/api/ssh/configure` | POST | 配置 SSH 连接 | Cookie / API Key |

### 系统管理

| 接口 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/api/settings` | GET | 获取用户设置 | Cookie / API Key |
| `/api/settings` | POST | 更新用户设置 | Cookie / API Key |
| `/api/disk_usage` | GET | 获取磁盘使用情况 | Cookie / API Key |
| `/api/health` | GET | 健康检查 | 无 |

### 认证方式说明

- **Cookie 登录**：通过 `/api/login` 或 `/api/login-by-sms` 获取 JWT，自动设置 HttpOnly Cookie
- **API Key + 手机号**：Header 传入 `X-API-Key` + `X-Phone`，或 Query 参数传入 `api_key` + `phone`

## Docker 部署

### 使用 Docker Compose

```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker logs -f quantclaw_app

# 停止
docker compose down
```

### CI/CD 自动部署

项目配置了 Gitea Actions 自动部署流水线（`.gitea/workflows/deploy.yml`），代码推送到 `main` 分支后自动执行：

```yaml
git pull → docker compose build → docker compose up -d
```

## 数据库设计

核心数据表：

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户表 | phone, username, password, role |
| `devices` | 设备表 | mac, hostname, ip, status, user_id |
| `ssh_configs` | SSH 配置表 | host, port, username, password, user_id |
| `settings` | 系统设置表 | data (JSONB), user_id |

详细数据库设计文档请参阅 [databases.md](databases.md)。

## 运行测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```
