# QuantClaw Web Admin UI — Docker 双重机制实施方案（web_admin_ui 专项版）

> **版本**: v1.0  
> **日期**: 2026-05-16  
> **适用项目**: QuantClaw Web Admin UI  
> **交付根目录**: `web_admin_ui/`

---

## 📋 文档目的

纠正前期命名偏差，将所有开发、部署、测试活动严格收束到 `web_admin_ui/` 文件夹内。交付物仅为：

```
交付根目录/
├── web_admin_ui/             ← 完整项目代码（这就是全部工作空间）
│   ├── main.py               ← 唯一入口
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/
│   ├── scripts/
│   ├── templates/
│   └── static/
│
└── 龙虾颗粒说明书.pdf         ← 唯一配套文档
```

### 为什么必须以 web_admin_ui/ 为边界收束？

| 原因 | 说明 |
|------|------|
| 消除路径歧义 | 知识库文档中出现过 `qiye_Admin_UI/`、`Web_Admin_UI/` 等多种名称，现在统一锚定为 `web_admin_ui/` |
| Docker 构建上下文自包含 | `context: .` 的 `.` 就是 `web_admin_ui/` 自身，无需相对路径跳转 |
| 开发者体验 | `cd web_admin_ui` 后，所有命令就地执行，不需要关心上级目录有什么 |

---

## 一、web_admin_ui/ 内的完整项目结构

```
web_admin_ui/                          ← 这就是全部工作空间，cd 进来就不要出去了
│
├── main.py                            ← 唯一启动入口（内/外层共用）
├── requirements.txt                   ← Python 依赖清单
│
├── app/
│   ├── app_factory.py                 ← FastAPI 应用工厂（装配所有模块）
│   ├── core/
│   │   └── config.py                  ← 配置加载（从 .env 读取）
│   └── modules/
│       ├── receiver/                  ← Receiver 模块（设备注册/心跳接收）
│       │   ├── router.py              ← 路由定义
│       │   ├── service.py             ← 业务逻辑
│       │   ├── repository.py          ← SQLite 持久化
│       │   └── runtime.py             ← 生命周期管理
│       └── web/
│           └── legacy_app.py          ← 原有后台逻辑承接
│
├── templates/
│   └── index.html                     ← 首页（Receiver 等待页）
│
├── static/                            ← 静态资源
│
├── scripts/
│   └── test_receiver_report.py        ← 模拟上报测试脚本
│
├── runtime/                           ← 运行时数据（.gitignore 排除）
│   └── quantclaw_devices.sqlite       ← 设备持久化数据库
│
├── Dockerfile                         ← 单镜像定义
├── docker-compose.yml                 ← 单服务编排
├── .env.example                       ← 环境变量模板
├── .env                               ← 实际配置（.gitignore 排除）
├── .gitignore                         ← 排除 .env / runtime / __pycache__
├── .dockerignore                      ← 排除 .env / runtime / .venv
└── README.md                          ← 项目说明
```

### 明确排除的内容

| 排除项 | 原因 | 处理方式 |
|--------|------|----------|
| `cg_main.py` | 历史兼容壳，非主入口，造成"到底启动哪个"的困惑 | 从 `web_admin_ui/` 中删除 |
| `docs/` 目录 | 所有文档已内化至 README.md | 不放入 `web_admin_ui/` |
| 根目录散落的其他 `.md` | 信息已整合，保留会造成文档碎片化 | 仅保留 README.md |

### 为什么删除 cg_main.py？

来自《项目交接说明》§3.1 的历史教训：

> "仓库最初存在两个后端入口 `main.py` 和 `cg_main.py`，两者职责重叠，后续维护容易出现路由重复、功能漂移、启动方式不一致"

既然现在是 `web_admin_ui/` 清洁开发，没有理由再携带一个废弃入口。

---

## 二、Docker 双重机制详解

### 2.1 架构总览

```
┌──────────────────────────────────────────────────────────┐
│  服务器宿主机                                             │
│                                                           │
│  web_admin_ui/  ← 全部工作在此目录内                       │
│  │                                                        │
│  ├── 外层：.venv + python main.py   (开发调试，端口 8081)  │
│  │   特点：改代码 → Ctrl+C → 重启 → 2秒生效               │
│  │                                                        │
│  └── 内层：docker compose up        (生产运行，端口 3309)  │
│      特点：构建镜像 → 稳定运行 → 环境隔离                   │
│                                                           │
│  web_admin_ui/../龙虾颗粒说明书.pdf  ← 唯一外部参考文档     │
└──────────────────────────────────────────────────────────┘
```

### 为什么必须双重而非只选其一？

| 场景 | 仅用 Docker | 仅用宿主机 | 双重机制 |
|------|-------------|-----------|----------|
| 调试一个 Bug 需改 5 次代码 | 每次 docker build 3-5 分钟，总耗 25 分钟 | 改完即重启，总耗 1 分钟 | ✅ 外层调试 |
| 正式部署给客户使用 | 环境隔离，依赖确定 | 依赖宿主机 Python 版本，不可控 | ✅ 内层部署 |
| 验证"容器环境能否复现本地行为" | 无法对比 | 无法对比 | ✅ 同份代码两层运行，行为可对齐 |

---

### 2.2 Dockerfile（位于 web_admin_ui/Dockerfile）

```dockerfile
FROM python:3.11-slim

# 安装 curl 用于健康检查
# 为什么：docker-compose.yml 的 healthcheck 依赖 curl 命令
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
# 为什么这样做：只改业务代码不改依赖时，跳过 pip install 层
# 达成目标：二次构建时间从 3 分钟降到 30 秒
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建 runtime 目录
# 为什么：Receiver 数据库路径默认为 runtime/quantclaw_devices.sqlite
# 达成目标：避免首次启动因目录不存在而报错
RUN mkdir -p runtime

EXPOSE 8081

# 唯一启动命令——与外层完全一致
CMD ["python", "main.py"]
```

---

### 2.3 docker-compose.yml（位于 web_admin_ui/docker-compose.yml）

```yaml
services:
  quantclaw:
    build:
      context: .              # 构建上下文就是 web_admin_ui/ 自身
      dockerfile: Dockerfile
    container_name: quantclaw
    ports:
      - "${HOST_PORT:-3309}:${APP_PORT:-8081}"
    env_file:
      - .env                  # 环境变量从 web_admin_ui/.env 注入
    volumes:
      - ./runtime:/app/runtime   # 设备数据库持久化
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8081/api/receiver/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    restart: unless-stopped
```

#### 关键设计决策解释

| 配置项 | 为什么这样做 | 达成目标 |
|--------|-------------|----------|
| `context: .` | 构建上下文锚定 `web_admin_ui/`，无需相对路径跳转 | 避免上级目录无关文件混入镜像 |
| `env_file: .env` | 内外层共享同一个环境变量文件 | 配置行为 100% 一致 |
| `volumes: ./runtime` | 容器销毁后数据库不丢失 | 设备注册信息持久保存 |
| `restart: unless-stopped` | 异常退出自动重启 | 生产环境稳定性保障 |

---

### 2.4 .env.example（位于 web_admin_ui/.env.example）

```ini
# ===== 核心配置（必须设置）=====
# 设备认证密钥 —— 必须与龙虾颗粒配网时设置的一致
DEVICE_SECRET=

# ===== 服务端口 =====
APP_PORT=8081
HOST_PORT=3309

# ===== 数据持久化 =====
RECEIVER_DB_PATH=runtime/quantclaw_devices.sqlite

# ===== SSH 配置（后台管理功能需要）=====
SSH_HOST=
SSH_PORT=22
SSH_USERNAME=
SSH_PASSWORD=

# ===== QuantClaw 设备访问配置 =====
QUANTCLAW_HTTP_PORT=80
QUANTCLAW_TTYD_PORT=7681
```

### 为什么 DEVICE_SECRET 是唯一必填项？

来自《项目交接说明》：

> ".env 至少要设置：DEVICE_SECRET"

设备注册时会携带此密钥，如果与服务端不一致，注册请求将被拒绝。这是"先能连上"的硬性前提。

---

## 三、内外层同步开发流程（详细操作手册）

### 3.1 外层开发环境搭建（调试首选）

> 所有命令均在 `web_admin_ui/` 目录下执行

```bash
# ========== 进入工作目录 ==========
cd web_admin_ui

# ========== 步骤1：创建虚拟环境 ==========
# 为什么：隔离依赖，不污染系统 Python
# 目标：.venv 内包含项目所有精确版本依赖
python -m venv .venv

# ========== 步骤2：激活虚拟环境 ==========
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# ========== 步骤3：安装依赖 ==========
# 为什么：requirements.txt 锁定了兼容版本
# 目标：环境可复现，不因版本差异出 Bug
pip install -r requirements.txt

# ========== 步骤4：配置环境变量 ==========
cp .env.example .env
# 编辑 .env，至少设置：
#   DEVICE_SECRET=quant123456   ← 必须与设备配网时设置的一致

# ========== 步骤5：启动服务 ==========
python main.py
# 输出应显示：Uvicorn running on http://0.0.0.0:8081

# ========== 步骤6：验证 ==========
# 6.1 健康检查
curl http://127.0.0.1:8081/api/receiver/health
# 期望：{"status":"healthy",...}

# 6.2 设备列表（应为空）
curl http://127.0.0.1:8081/api/receiver/devices
# 期望：[]

# 6.3 前端页面
# 浏览器打开 http://127.0.0.1:8081/
# 应看到"等待设备上报"状态
```

#### 外层热修改流程

```
修改 app/modules/receiver/service.py
    ↓
Ctrl+C 停止服务
    ↓
python main.py 重启
    ↓
2秒内服务恢复
```

> **为什么调试阶段不用 Docker？** 一个网络扫描 Bug 可能需要改 5 次代码、重启 5 次服务。Docker 每次重建 3-5 分钟，总耗时 25 分钟；外层开发只需 1 分钟。

---

### 3.2 内层生产环境搭建（稳定部署）

```bash
# ========== 确认在正确目录 ==========
cd web_admin_ui

# ========== 步骤1：确认 .env 配置 ==========
cat .env
# 确保 DEVICE_SECRET 已设置
# 确保 HOST_PORT 未被占用

# ========== 步骤2：构建并启动 ==========
docker compose up -d --build
# --build: 首次或代码变更后使用，强制重建镜像
# -d: 后台运行

# ========== 步骤3：查看运行状态 ==========
docker compose ps
# 期望：quantclaw 服务状态为 running

# ========== 步骤4：查看实时日志 ==========
docker compose logs -f quantclaw
# 按 Ctrl+C 退出日志流

# ========== 步骤5：验证 ==========
# 5.1 健康检查
curl http://127.0.0.1:3309/api/receiver/health

# 5.2 设备列表
curl http://127.0.0.1:3309/api/receiver/devices

# 5.3 前端页面
# 浏览器打开 http://<服务器IP>:3309/
```

---

### 3.3 内外层切换规则

**核心原则：同一时刻只运行一层，避免端口冲突和数据不同步。**

```bash
# 场景A：当前 Docker 在运行，想切到外层调试

# Step 1: 停止内层
docker compose down

# Step 2: 启动外层
python main.py    # 使用 APP_PORT=8081

# 场景B：调试完毕，切回内层

# Step 1: 停止外层
Ctrl+C

# Step 2: 启动内层
docker compose up -d    # 无需 --build，复用已构建的镜像
```

#### 为什么禁止同时运行？

1. 两个进程同时监听端口 → 启动失败
2. 两个独立 SQLite 实例 → 数据不同步 → 调试结论失真

---

## 四、对接龙虾颗粒设备的完整流程

### 4.1 流程全景

```
阶段1: 服务器部署 ─────────────────────────────
  [cd web_admin_ui] → [配置 .env] → [docker compose up] → [健康检查通过]
                                                          ↓
阶段2: 物理设备准备 ─────────────────────────────
  [通电 5V/2A+] → [等待 30 秒] → [绿灯常亮]
                                                          ↓
阶段3: 设备配网 ─────────────────────────────────
  [连接 QuantClaw-XXXX 热点] → [访问设备管理页]
  → [输入家庭 WiFi 密码] → [设备重启] → [蓝灯常亮]
                                                          ↓
阶段4: 首次连接验证 ─────────────────────────────
  [设备发送注册请求到 Receiver] → [前端显示设备卡片]
  → [确认设备在线] ✓ 全流程跑通
                                                          ↓
阶段5: 后续配置（按需）───────────────────────────
  [配置 DeepSeek 密钥] → [开始使用 AI 功能]
```

---

### 4.2 阶段1 详细操作（服务器部署，预计 5 分钟）

```bash
# 1.1 进入项目目录
cd web_admin_ui

# 1.2 创建环境配置
cp .env.example .env
nano .env   # 填写必选项

# ========== .env 最小必填项 ==========
DEVICE_SECRET=quant123456    # ⚠️ 必须与设备配网时设置的一致
HOST_PORT=3309
APP_PORT=8081
# ===================================

# 1.3 启动 Docker
docker compose up -d --build

# 1.4 四项验证
echo "=== 检查1: 容器运行 ==="
docker compose ps | grep quantclaw

echo "=== 检查2: 健康接口 ==="
curl -s http://127.0.0.1:3309/api/receiver/health | python -m json.tool

echo "=== 检查3: 设备列表(应为空) ==="
curl -s http://127.0.0.1:3309/api/receiver/devices | python -m json.tool

echo "=== 检查4: 前端页面 ==="
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3309/
# 期望：200
```

> **为什么这一步最重要？** 如果 Receiver 未正常运行，设备发出的注册请求无处可去，后面所有操作都白费。这是"先能连上"的前提。

---

### 4.3 阶段2-3：设备配网（按龙虾颗粒说明书操作）

服务器端无需额外操作，但需确认前提：

**前提条件检查清单：**

- ✅ 服务器与龙虾颗粒设备将接入同一个路由器
- ✅ 路由器 DHCP 开启，设备可获得 IP
- ✅ 路由器未开启 AP 隔离（否则设备与服务器互不可达）
- ✅ 服务器防火墙允许 3309 端口入站

**如何验证"同一网络"？**

```bash
# 在服务器上
ip addr show | grep "inet "    # 获取服务器 IP，如 192.168.1.100

# 设备配网后，通过 HDMI 显示器查看设备 IP
# 如果设备 IP 是 192.168.1.xxx → 同网段 ✓
# 如果设备 IP 是 10.0.0.xxx → 不同网段 ✗
```

---

### 4.4 阶段4：首次连接验证（最关键时刻）

```bash
# 4.1 监听 Receiver 日志（实时观察注册过程）
docker compose logs -f quantclaw | grep -i "register\|heartbeat\|device"

# 4.2 查询设备列表
curl http://127.0.0.1:3309/api/receiver/devices | python -m json.tool

# 4.3 前端验证
# 浏览器打开 http://<服务器IP>:3309/
# 应看到设备卡片
```

#### 设备列表为空时的逐项排查

```
Step 1: 设备蓝灯是否常亮？
  ├── 否 → 配网失败，回到阶段3
  └── 是 → 继续

Step 2: 从设备 IP 能否 ping 通服务器？
  ├── 在设备终端执行：ping <服务器IP>
  ├── 不通 → 网络隔离，检查路由器 AP 隔离设置
  └── 通 → 继续

Step 3: 设备能否访问 Receiver？
  ├── 在设备终端执行：curl http://<服务器IP>:3309/api/receiver/health
  ├── 返回非 200 → 防火墙拦截
  └── 返回 200 → 继续

Step 4: 检查 DEVICE_SECRET 是否一致
  ├── 服务器 .env 中的值 vs 设备配置页中设置的值
  ├── 不一致 → 修改 .env 并重启 Docker
  └── 一致 → 查看 docker logs 获取详细报错
```

---

### 4.5 使用模拟脚本快速验证（不等物理设备也能测）

```bash
# 在 web_admin_ui/ 下执行
python scripts/test_receiver_report.py register
```

**为什么需要模拟脚本？** 物理设备可能还没到手，或网络环境未就绪。模拟脚本可在纯软件层面验证 Receiver 全链路：

```
脚本发送 POST /api/device/register
    ↓
Receiver 接收并写入 SQLite
    ↓
GET /api/receiver/devices 返回设备数据
    ↓
前端轮询（每3秒）获取最新设备列表
    ↓
设备卡片出现在首页
```

---

## 五、安全设计

### 5.1 敏感信息保护

```
Layer 1: .env 文件不入库
  ├── .gitignore 包含 .env
  ├── .dockerignore 包含 .env（防止打入镜像）
  └── 提供 .env.example 作为模板

Layer 2: Docker Compose 通过 env_file 注入
  ├── 运行时才读取 .env
  └── 镜像内不含明文密钥

Layer 3: CI/CD 通过 Secrets 注入（如需要）
  └── 构建时动态生成 .env
```

### 5.2 防火墙最小化开放

```bash
sudo ufw allow 3309/tcp              # QuantClaw 管理后台
sudo ufw allow from 192.168.1.0/24   # 仅允许局域网访问
```

---

## 六、性能基线（来自已完成的优化成果）

| 指标 | 优化前 | 优化后 | 技术手段 |
|------|--------|--------|----------|
| 设备扫描总耗时 | 32秒 | 3秒 | 移除主动 ping，利用 ARP 缓存 |
| hostname 查询 | 无超时阻塞 | 500ms 超时 | `asyncio.wait_for` |
| 代码行数 | 407行 | 276行 | dataclass + Enum 重构 |
| 设备识别率 | 0% | 100% | NetBIOS + MAC 厂商前缀 + 端口扫描 |

> **这些优化在 Docker 中同样生效吗？** 是的，因为代码路径一致（单入口 `main.py`）。

---

## 七、完整验收清单

### ✅ 部署验收

```bash
[ ] cd web_admin_ui 成功进入项目目录
[ ] .env 文件已创建且 DEVICE_SECRET 已设置
[ ] docker compose up -d --build 成功执行
[ ] docker compose ps 显示 quantclaw 运行中
[ ] curl http://127.0.0.1:3309/api/receiver/health 返回 healthy
[ ] curl http://127.0.0.1:3309/api/receiver/devices 返回空数组
[ ] 浏览器访问 http://127.0.0.1:3309/ 看到"等待设备上报"页面
```

### ✅ 外层开发验收

```bash
[ ] python -m venv .venv 创建成功
[ ] pip install -r requirements.txt 安装成功
[ ] python main.py 启动成功，监听 8081
[ ] 修改代码后重启可立即生效
[ ] 日志输出清晰可见
```

### ✅ 设备连接验收

```bash
[ ] 设备通电后 30 秒内出现热点 QuantClaw-XXXX
[ ] 配网后设备蓝灯常亮
[ ] 服务器日志中出现设备注册记录
[ ] /api/receiver/devices 返回设备信息
[ ] 前端首页显示设备卡片
[ ] 模拟脚本测试通过：python scripts/test_receiver_report.py register
```

### ✅ 持久化验收

```bash
[ ] 容器重启后设备数据仍在
[ ] sqlite3 runtime/quantclaw_devices.sqlite "SELECT * FROM devices;" 有记录
[ ] 前端刷新后设备信息不丢失
```

---

## 八、总结：本方案的核心价值

| 设计原则 | 具体实现 | 解决的痛点 |
|----------|----------|-----------|
| 目录收束 | 一切在 `web_admin_ui/` 内闭环 | 消除路径歧义和无关文件干扰 |
| 最小复杂度 | 单入口 `main.py`、单镜像、单服务 | 杜绝双入口并存的维护混乱 |
| 环境一致性 | 内外层共享 `main.py` + `.env` | 调试结论可直接迁移到生产 |
| 渐进式验证 | 健康检查 → 模拟注册 → 真实设备 | 每步有明确成败判定 |
| 对齐说明书 | 部署步骤对应龙虾颗粒说明书阶段 | 不是凭空设计，是最短连通路径 |

**最终目标：让龙虾颗粒设备从通电到前端显示设备信息，全链路零卡点。**

---

## 九、快速启动

```bash
# 第一步：进入工作空间
cd web_admin_ui

# 第二步：配置环境
cp .env.example .env && nano .env    # 设置 DEVICE_SECRET

# 第三步：启动服务
docker compose up -d --build

# 第四步：确认就绪
curl http://127.0.0.1:3309/api/receiver/health

# 第五步：按龙虾颗粒说明书操作设备，等待设备上线
```
