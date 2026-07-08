# 数据库重构提示词

> 本文档通过对话逐步完善，最终将作为数据库重构的完整执行指南。
> 
> ✅ 所有问题已确认完毕，文档进入最终定稿阶段。

---

## 一、数据库选型与基础设施

| 项目 | 决策 |
|------|------|
| 数据库类型 | **PostgreSQL** |
| 技术驱动 | **psycopg2**（原生 SQL 操作） |
| 连接信息 | host=`localhost`, port=`5432`, user=`quant`, password=`open123456`, dbname=`quantclaw` |
| 连接池 | **psycopg2 自带连接池**（`psycopg2.pool.ThreadedConnectionPool`） |
| 错误策略 | 数据库不可用时**系统启动报错，拒绝启动** |
| 迁移工具 | **暂不做**（全新开始，直接执行建表 SQL） |
| 数据迁移 | **不需要**（废弃 `users.db` 和 `quantclaw.sqlite`，全新开始） |
| 缓存 | **Redis**（短信验证码存储，5 分钟有效期） |

> ⚠️ 不使用 ORM，所有数据库操作直接写原生 SQL。
> ⚠️ 旧数据文件 `users.db` / `quantclaw.sqlite` / `settings.json` / `ssh_config.json` 不再使用。

---

## 二、核心数据模型

### 2.1 数据关系

| 关系 | 决策 |
|------|------|
| 用户 ↔ 设备 | **一对多**（一个用户拥有多台设备，设备归属唯一用户） |
| 扩展预留 | 未来可能需要升级为多对多，`devices.mac` 不设 UNIQUE 约束 |
| `phone` | **用户级**（手机号作为用户标识，设备注册时校验） |
| 主设备 | 用户可手动指定某台设备为主设备（`devices.is_primary`） |

### 2.2 角色权限

| 项目 | 决策 |
|------|------|
| 角色系统 | **实现三级权限体系**（通过 users.role 字段控制） |
| 软删除 | **不实现**（直接物理删除） |
| `USERS` 内存字典 | **完全删除**（所有用户通过注册登录写入数据库） |

#### 权限等级定义

| 权限值 | 角色名称 | 登录权限 | 说明 |
|--------|----------|----------|------|
| `role_usr_8f7d` | 普通用户 | ✅ 本网站可登录 | 正常注册用户，可使用本网站全部功能 |
| `role_adm_3k9p` | 管理员用户 | ✅ 本网站可登录 | 管理员用户，既能登录本网站，也能登录管理员网站（后续实现） |

#### 权限值设计说明

采用"前缀_角色标识_随机后缀"的结构：
- **前缀**：固定为 `role_`，便于识别
- **角色标识**：`usr`=普通用户，`adm`=管理员
- **随机后缀**：4位字母数字组合，增强不可预测性

#### 权限验证规则

- **注册默认值**：新注册用户 `role` 字段默认为 `role_usr_8f7d`（普通用户）
- **本网站登录**：仅允许 `role` 属于白名单 `('role_usr_8f7d', 'role_adm_3k9p')` 的用户登录，其他角色一律拒绝
- **向后兼容**：现有用户 `role` 字段默认设为 `role_usr_8f7d`，不影响正常使用
- **预留接口**：为后续管理员网站提供用户权限 CRUD 操作接口

---

## 三、数据表设计

### 3.1 用户表 `users`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | SERIAL | PK | 主键 |
| `phone` | VARCHAR(20) | UNIQUE, NOT NULL | 手机号 |
| `username` | VARCHAR(50) | UNIQUE, NOT NULL | 用户名 |
| `password` | VARCHAR(255) | NOT NULL | bcrypt 加密密码 |
| `password_changed_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 密码最后修改时间（用于 JWT 失效判定） |
| `role` | VARCHAR(32) | NOT NULL, DEFAULT 'role_usr_8f7d' | 用户权限等级（字母数字组合，增强安全性） |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

#### 权限字段说明

- `role` 字段使用 VARCHAR(32) 类型，默认值为 `'role_usr_8f7d'`
- 权限值采用"前缀_角色标识_随机后缀"结构，增强安全性和不可预测性
- 权限值定义：`role_usr_8f7d`=普通用户，`role_adm_3k9p`=管理员用户
- 现有用户数据迁移时，`role` 字段默认设为 `'role_usr_8f7d'`
- 预留管理接口：后续可通过管理员网站更新用户 `role` 字段

### 3.2 设备表 `devices`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | SERIAL | PK | 主键 |
| `user_id` | INTEGER | FK → users.id, NOT NULL, DEFAULT 1 | 所属用户 |
| `device_name` | VARCHAR(100) | NOT NULL, DEFAULT '' | 设备别名 |
| `mac` | VARCHAR(17) | NOT NULL | 设备 MAC 地址（不设 UNIQUE，预留多对多） |
| `hostname` | VARCHAR(128) | NOT NULL, DEFAULT '' | 设备主机名 |
| `model` | VARCHAR(128) | NOT NULL, DEFAULT '' | 设备型号 |
| `firmware_version` | VARCHAR(64) | NOT NULL, DEFAULT '' | 固件版本 |
| `ip` | VARCHAR(64) | NOT NULL, DEFAULT '' | 设备主 IP（SSH 连接用） |
| `ssid` | VARCHAR(128) | NOT NULL, DEFAULT '' | 连接 WiFi 名称 |
| `internet_available` | BOOLEAN | NOT NULL, DEFAULT FALSE | 互联网连通状态 |
| `status` | `device_status`（自定义枚举） | NOT NULL, DEFAULT 'registered' | 设备状态（registered/online/offline/unknown） |
| `heartbeat_interval_sec` | INTEGER | NOT NULL, DEFAULT 60 | 心跳间隔（设备可独立配置） |
| `ttyd_enabled` | BOOLEAN | NOT NULL, DEFAULT FALSE | 终端服务开关 |
| `ttyd_port` | INTEGER | NOT NULL, DEFAULT 7681 | 终端服务端口 |
| `mdns_host` | VARCHAR(128) | NOT NULL, DEFAULT '' | 局域网本地域名 |
| `http_port` | INTEGER | NOT NULL, DEFAULT 80 | HTTP 服务端口 |
| `access_scope` | VARCHAR(32) | NOT NULL, DEFAULT 'lan' | 访问权限范围（lan / wan） |
| `interfaces_json` | TEXT | YES | 网络接口 JSON 字符串 `[{"name":"eth0","ip":"192.168.1.1","type":"ethernet"}]` |
| `device_secret` | VARCHAR(100) | NOT NULL, DEFAULT '' | 设备连接密钥，注册/心跳时 HMAC 校验 |
| `is_quant` | BOOLEAN | NOT NULL, DEFAULT FALSE | 是否 QuantClaw 设备 |
| `paired_at` | TIMESTAMPTZ | YES | 配对绑定时间 |
| `first_seen_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 首次发现时间 |
| `last_seen_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 最后心跳时间 |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 更新时间 |

> ⚠️ `interfaces_json` 使用 TEXT 存储 JSON 字符串
> ⚠️ `status` 使用 PostgreSQL 自定义枚举类型 `device_status`，值为 `registered` / `online` / `offline` / `unknown`
> ⚠️ 设备注册和心跳时通过 `device_secret` 进行 HMAC 签名校验

### 3.3 SSH 配置表 `ssh_configs`（每个用户一条记录）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `user_id` | INTEGER | PK, FK → users.id | 所属用户（主键） |
| `host` | VARCHAR(255) | YES, DEFAULT '' | SSH 主机地址（动态跟随主设备 IP） |
| `port` | INTEGER | YES, DEFAULT 22 | SSH 端口 |
| `username` | VARCHAR(100) | YES, DEFAULT '' | SSH 用户名 |
| `password` | VARCHAR(255) | YES, DEFAULT '' | SSH 密码 |
| `remote_path` | VARCHAR(500) | YES, DEFAULT '/home/quant' | 默认远程路径 |
| `created_at` | TIMESTAMPTZ | YES, DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | YES, DEFAULT NOW() | 更新时间 |

> `host` 更新逻辑：当用户指定的主设备（`is_primary=true`）上报心跳时，自动更新 `ssh_configs.host` 为该设备的最新 IP。

### 3.4 系统设置表 `settings`（每个用户一条记录）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `user_id` | INTEGER | PK, FK → users.id | 所属用户（主键） |
| `data` | JSONB | NOT NULL, DEFAULT '{}' | 设置数据（JSONB 存储全部用户偏好配置） |
| `created_at` | TIMESTAMPTZ | YES, DEFAULT NOW() | 创建时间 |
| `updated_at` | TIMESTAMPTZ | YES, DEFAULT NOW() | 更新时间 |

> `data` JSONB 字段包含原 `settings.json` 的全部内容（主题 `theme`、语言 `language`、文件管理规则 `rules`、用户默认设置 `user_defaults`、分块大小 `chunk_size` 等），保持灵活可扩展。

---

## 四、Redis 缓存（短信验证码）

| 项目 | 决策 |
|------|------|
| 连接信息 | host=`localhost`, port=`6379`, db=`0`（`redis.Redis(host='localhost', port=6379, db=0)`） |
| Key 格式 | `sms_code:{phone}` |
| Value | 6 位数字验证码 |
| TTL | **300 秒（5 分钟）**，过期自动删除 |
| 重发限制 | 60 秒内不允许重复发送（可用单独 TTL 60s 的 `sms_cooldown:{phone}` Key） |

---
## 五、环境配置文件变更（`.env` / `.env.example`）

> ⚠️ 废弃所有 SQLite 和 JSON 文件相关配置，全部替换为 PostgreSQL + Redis。

### 5.1 删除的配置项

| 配置项 | 原值 | 删除原因 |
|--------|------|----------|
| `DB_PATH` | `./quantclaw.sqlite` | SQLite 废弃 |
| `SETTINGS_FILE` | `settings.json` | JSON 文件迁入 PostgreSQL `settings` 表 |
| `SSH_CONFIG_FILE` | `ssh_config.json` | JSON 文件迁入 PostgreSQL `ssh_configs` 表 |
| `CONFIG_BACKUP_DIR` | `config_backups` | 不再使用 JSON 文件备份 |
| `CONFIG_HISTORY_FILE` | `config_history.json` | 不再使用 JSON 文件记录历史 |

### 5.2 新增的配置项

```env
# ---------- PostgreSQL 数据库 ----------
PG_HOST=localhost
PG_PORT=5432
PG_USER=quant
PG_PASSWORD=open123456
PG_DBNAME=quantclaw
PG_POOL_MIN=2
PG_POOL_MAX=10

# ---------- Redis 缓存 ----------
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

### 5.3 变更后的完整 `.env.example`

```env
# ============================================================
# QuantClaw 设备管理后台 - 环境配置示例
# 复制此文件为 .env 并修改相应的值
# ============================================================

# ---------- 应用服务器 ----------
APP_TITLE=QuantClaw Device Manager
APP_HOST=0.0.0.0
APP_PORT=8081

# ---------- PostgreSQL 数据库 ----------
PG_HOST=localhost
PG_PORT=5432
PG_USER=quant
PG_PASSWORD=open123456
PG_DBNAME=quantclaw
PG_POOL_MIN=2
PG_POOL_MAX=10

# ---------- Redis 缓存 ----------
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ---------- QuantClaw 设备管理 ----------
UDP_ENABLED=true
ALLOW_INSECURE=true
HEARTBEAT_INTERVAL_SEC=60

# ---------- 认证 ----------
TOKEN_EXPIRE_DAYS=30

# ---------- CORS 跨域 ----------
CORS_ALLOW_ORIGINS=*

# ---------- SSH 远程管理 ----------
SSH_DEFAULT_REMOTE_PATH=/home/quant
SSH_CONNECT_TIMEOUT=10
SSH_SUDO_TIMEOUT=30
```

---
## 六、多对多扩展预留

当前一对多（`devices.user_id`），未来如需多对多，新增：

```sql
CREATE TABLE user_devices (
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, device_id)
);
```

升级步骤：数据从 `devices.user_id` 迁移到 `user_devices` → 移除 `devices.user_id`。

---

## 七、INDEX 索引设计

| 索引名 | 表 | 列 | 用途 |
|------|----|----|------|
| `idx_users_phone` | users | phone | 手机号登录查询 |
| `idx_users_username` | users | username | 用户名登录查询 |
| `idx_devices_user_id` | devices | user_id | 按用户查设备列表 |
| `idx_devices_mac` | devices | mac | 按 MAC 查设备 |
| `idx_devices_last_seen_at` | devices | last_seen_at | 心跳排序 / 在线判定 |
| `idx_devices_status` | devices | status | 按设备状态过滤 |

---

## 八、ER 关系图

```
┌──────────────────┐        ┌───────────────────────┐
│      users       │ 1──N   │       devices         │
│                  │        │                       │
│ id (PK)          │        │ id (PK)               │
│ phone (U)        │        │ user_id (FK)          │
│ username (U)     │        │ device_name           │
│ password         │        │ mac                   │
│ password_changed │        │ hostname              │
│ created_at       │        │ model                 │
│ updated_at       │        │ firmware_version      │
└──────────────────┘        │ ip                    │
        │                   │ ssid                  │
        │ 1──1              │ internet_available    │
        │                   │ status (device_status)│
        │ 1──1              │ heartbeat_interval    │
        │                   │ ttyd_enabled          │
┌───────┴──────────┐        │ ttyd_port             │
│   ssh_configs    │        │ mdns_host             │
│                  │        │ http_port             │
│ user_id (PK, FK) │        │ access_scope          │
│ host             │        │ interfaces_json (TEXT)│
│ port             │        │ device_secret         │
│ username         │        │ is_quant              │
│ password         │        │ paired_at             │
│ remote_path      │        │ first_seen_at         │
│ created_at       │        │ last_seen_at          │
│ updated_at       │        │ created_at            │
└──────────────────┘        │ updated_at            │
        │                   └───────────────────────┘
        │ 1──1
┌───────┴──────────┐
│    settings      │
│                  │
│ user_id (PK, FK) │
│ data (JSONB)     │
│ created_at       │
│ updated_at       │
└──────────────────┘
```

---

## 九、完整建表 SQL

```sql
-- ============================================
-- 数据库重构建表 SQL
-- 目标: PostgreSQL (localhost:5432/quantclaw)
-- ============================================

-- 设备状态枚举类型
DO $$ BEGIN
    CREATE TYPE device_status AS ENUM ('registered', 'online', 'offline', 'unknown');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 用户表
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    phone           VARCHAR(20) NOT NULL,
    username        VARCHAR(50) NOT NULL,
    password        VARCHAR(255) NOT NULL,
    password_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    role            VARCHAR(32) NOT NULL DEFAULT 'role_usr_8f7d',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_users_phone ON users(phone);
CREATE UNIQUE INDEX idx_users_username ON users(username);

-- 设备表
CREATE TABLE devices (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL DEFAULT 1 REFERENCES users(id) ON DELETE CASCADE,
    device_name     VARCHAR(100) NOT NULL DEFAULT '',
    mac             VARCHAR(17) NOT NULL,
    hostname        VARCHAR(128) NOT NULL DEFAULT '',
    model           VARCHAR(128) NOT NULL DEFAULT '',
    firmware_version VARCHAR(64) NOT NULL DEFAULT '',
    ip              VARCHAR(64) NOT NULL DEFAULT '',
    ssid            VARCHAR(128) NOT NULL DEFAULT '',
    internet_available BOOLEAN NOT NULL DEFAULT FALSE,
    status          device_status NOT NULL DEFAULT 'registered',
    heartbeat_interval_sec INTEGER NOT NULL DEFAULT 60,
    ttyd_enabled    BOOLEAN NOT NULL DEFAULT FALSE,
    ttyd_port       INTEGER NOT NULL DEFAULT 7681,
    mdns_host       VARCHAR(128) NOT NULL DEFAULT '',
    http_port       INTEGER NOT NULL DEFAULT 80,
    access_scope    VARCHAR(32) NOT NULL DEFAULT 'lan',
    interfaces_json TEXT,
    device_secret   VARCHAR(100) NOT NULL DEFAULT '',
    is_quant        BOOLEAN NOT NULL DEFAULT FALSE,
    paired_at       TIMESTAMPTZ,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_devices_user_id ON devices(user_id);
CREATE INDEX idx_devices_mac ON devices(mac);
CREATE INDEX idx_devices_last_seen_at ON devices(last_seen_at);
CREATE INDEX idx_devices_status ON devices(status);

-- SSH 配置表
CREATE TABLE ssh_configs (
    user_id         INTEGER NOT NULL PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    host            VARCHAR(255) DEFAULT '',
    port            INTEGER DEFAULT 22,
    username        VARCHAR(100) DEFAULT '',
    password        VARCHAR(255) DEFAULT '',
    remote_path     VARCHAR(500) DEFAULT '/home/quant',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 系统设置表
CREATE TABLE settings (
    user_id         INTEGER NOT NULL PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data            JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 十、已确认的技术决策汇总

| 项目 | 决策 |
|------|------|
| 数据库 | PostgreSQL |
| 驱动 | psycopg2 |
| 操作方式 | 原生 SQL（无 ORM） |
| 连接池 | `psycopg2.pool.ThreadedConnectionPool` |
| 错误策略 | 数据库不可用 → 系统拒绝启动 |
| 迁移工具 | 暂不做 |
| 缓存 | Redis（短信验证码，5 分钟 TTL） |
| 角色权限 | 实现两级权限体系（role字段：role_usr_8f7d-普通用户，role_adm_3k9p-管理员，均可登录本网站） |
| 软删除 | 不实现 |
| `USERS` 字典 | 完全删除 |
| UDP 广播 | **保留**，`quantclaw_receiver/` 模块适配 PostgreSQL |
| 认证方式 | JWT + HttpOnly Cookie（不变） |
| 在线判定 | `status` 字段 + 心跳间隔（180 秒阈值） |
| 设备注册 | 必须携带匹配的 `device_secret` |
| 主设备 | 用户手动标记 `is_primary`，SSH host 跟随主设备 IP |
| 心跳间隔 | 设备表独立存储，每台设备可不同 |
| 旧数据 | 全部废弃，全新开始 |
| `device_secret` | 不再硬编码 `"quant123456"`，改为每个设备独立配置 |
| `.env` / `.env.example` | 删除 SQLite + JSON 文件配置，新增 PostgreSQL + Redis 配置 |

---

## 十一、涉及修改的代码文件范围（执行阶段参考，当前不做改动）

> ⚠️ **核心原则：只换存储层，不改业务逻辑。** 详见第十二节。所有文件的 public 方法签名、返回值结构、异常类型保持完全不变。

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `main.py` | **重写** | 删除 USERS 字典、JSON 文件读写、旧 SQLite 路由；替换为 PostgreSQL |
| `login/config.py` | **重写** | 新增 PostgreSQL 连接配置、Redis 连接配置 |
| `login/database.py` | **重写** | 替换 SQLAlchemy 为 psycopg2 连接池 |
| `login/models.py` | **删除** | ORM 模型不再需要 |
| `login/auth.py` | **适配** | 数据库查询改为原生 SQL |
| `login/routers/auth_router.py` | **适配** | 注册/登录/密码修改/验证码 改为 PostgreSQL + Redis |
| `login/code_store.py` | **重写** | 替换内存字典为 Redis |
| `login/sms_utils.py` | **不变** | 短信发送逻辑保持 |
| `login/schemas.py` | **适配** | 请求模型按需调整 |
| `quantclaw_receiver/database.py` | **重写** | 替换 sqlite3 为 psycopg2 |
| `quantclaw_receiver/device_manager.py` | **适配** | 适配新的设备注册/心跳/列表逻辑 |
| `quantclaw_receiver/config.py` | **适配** | 去掉 SQLite 路径和 `device_secret` 硬编码，新增 PostgreSQL 配置，`device_secret` 改为每个设备独立配置 |
| `quantclaw_receiver/udp_receiver.py` | **适配** | UDP 处理改为调用新的数据库方法 |
| `.env.example` | **重写** | 删除 SQLite + JSON 文件配置，新增 PostgreSQL + Redis 配置 |
| `.env` | **重写** | 同上，与 `.env.example` 保持一致结构 |
| `templates/` (7 个文件) | **审核** | 确认前端逻辑与新的 API 兼容 |

---

## 十二、数据库替换执行指南——只换存储层，不改业务逻辑

> ⚠️ **核心原则：只替换数据存储方式（SQLite → PostgreSQL），不改变任何业务逻辑代码。**
>
> 即：原来 `quantclaw_receiver/database.py` 中的 `register_device()`、`process_heartbeat()`、`get_devices_list()` 方法名、参数列表、返回值结构全部保持不变，**只把方法内部的 `sqlite3.Cursor.execute()` 换成 `psycopg2.Cursor.execute()`**，对应的 SQL 语句适配 PostgreSQL 语法即可。同理，`login/database.py` 的 `get_db()` 只把引擎从 SQLAlchemy+SQLite 换成 psycopg2 连接池，返回一个 `psycopg2.extensions.connection`。

### 12.1 替换总则

| 原则 | 说明 |
|------|------|
| **方法签名不变** | 所有 public 方法的函数名、参数、返回值类型完全不变 |
| **调用方无感** | `device_manager.py`、`auth_router.py`、`main.py` 等调用方代码一行不改 |
| **只改方法体** | 只替换方法内部的数据库连接和 SQL 语句 |
| **返回值兼容** | 返回给前端的 JSON 结构和字段名与原来完全一致 |
| **错误处理不变** | 异常类型和 `try/except` 结构保持，`DatabaseError` 照常抛出 |

### 12.2 数据读取流程（提取数据）

#### 12.2.1 用户认证数据读取（`login/` 模块）

```
原: db.query(User).filter(User.phone == phone).first()
新: conn.execute("SELECT * FROM users WHERE phone = %s", (phone,)).fetchone()
```

| 原 SQLAlchemy 操作 | 新 psycopg2 原生 SQL |
|------|------|
| `db.query(User).filter(User.id == uid).first()` | `cur.execute("SELECT * FROM users WHERE id = %s", (uid,)); cur.fetchone()` |
| `db.query(User).filter(User.phone == p).first()` | `cur.execute("SELECT * FROM users WHERE phone = %s", (p,)); cur.fetchone()` |
| `db.query(User).filter(User.username == u).first()` | `cur.execute("SELECT * FROM users WHERE username = %s", (u,)); cur.fetchone()` |
| `db.add(user); db.commit(); db.refresh(user)` | `cur.execute("INSERT INTO users (...) VALUES (...) RETURNING *", ...); row = cur.fetchone(); conn.commit()` |
| `user.hashed_password = ...; db.commit()` | `cur.execute("UPDATE users SET password = %s, updated_at = NOW() WHERE id = %s", ...); conn.commit()` |

#### 12.2.2 设备数据读取（`quantclaw_receiver/` 模块）

```
原: conn.execute("SELECT mac, hostname, ... FROM devices WHERE mac = ?", (mac,)).fetchone()
新: cur.execute("SELECT mac, hostname, ... FROM devices WHERE mac = %s", (mac,)); cur.fetchone()
```

| 原 sqlite3 操作 | 新 psycopg2 操作 | 注意事项 |
|------|------|------|
| 占位符 `?` | 改为 `%s` | psycopg2 统一用 `%s`，不是 `?` |
| `conn.row_factory = sqlite3.Row` | 用 `RealDictCursor` 或手动构建 dict | 返回的 dict key 必须与原来一致 |
| `conn.execute("INSERT INTO devices (...) VALUES (?,...)", (...))` | `cur.execute("INSERT INTO devices (...) VALUES (%s,...)", (...))` | 字段顺序和默认值与原来相同 |
| `conn.commit()` | `conn.commit()` | commit 行为一致 |

#### 12.2.3 设置和 SSH 配置读取（`main.py` 中）

| 原 JSON 文件操作 | 新 PostgreSQL 操作 |
|------|------|
| `json.load(open("settings.json"))` | `cur.execute("SELECT data FROM settings WHERE user_id = %s", (uid,)); row["data"]` |
| `json.dump(data, open("settings.json","w"))` | `cur.execute("INSERT INTO settings (...) ON CONFLICT (user_id) DO UPDATE SET data = %s, updated_at = NOW()", ...)` |
| `json.load(open("ssh_config.json"))` | `cur.execute("SELECT * FROM ssh_configs WHERE user_id = %s", (uid,))` |
| `json.dump(data, open("ssh_config.json","w"))` | `cur.execute("INSERT INTO ssh_configs (...) ON CONFLICT (user_id) DO UPDATE SET ...", ...)` |

### 12.3 数据写入流程（存储数据）

#### 12.3.1 设备注册数据存储规则

**入口**：`quantclaw_receiver/device_manager.py` → `register_device()` 方法（**方法签名不变**）

**验证规则**：
1. 请求体为空且 `allow_insecure=true` → 直接返回设备列表（兼容旧行为）
2. 从请求中提取 `device_secret` 字段 → 查询 `devices` 表校验
3. 签名验证逻辑（HMAC-SHA256）**完全不变**，只是签名用的 secret 从硬编码 `"quant123456"` 改为从 `devices.device_secret` 动态获取
4. 字段校验（MAC、timestamp 等）**完全不变**

**存储规则**（`quantclaw_receiver/database.py` 的 `register_device()` 方法内部）：
```
原 sqlite3 SQL:
  INSERT INTO devices (mac, hostname, model, ...) VALUES (?, ?, ?, ...)

新 psycopg2 SQL（字段对应 devices 表）:
  INSERT INTO devices (
    user_id, mac, hostname, model, firmware_version, ip, ssid,
    internet_available, status, heartbeat_interval_sec,
    ttyd_enabled, ttyd_port, mdns_host, http_port,
    access_scope, device_secret, is_quant,
    first_seen_at, last_seen_at, created_at, updated_at
  ) VALUES (
    %s, %s, %s, %s, %s, %s, %s,
    FALSE, 'registered', %s,
    %s, %s, %s, %s,
    %s, %s, FALSE,
    %s, %s, %s, %s
  )
```

**字段映射表**（原 payload key → 新 devices 列）：

| 原 payload key | 新 `devices` 列 | 类型 | 默认值 |
|------|------|------|------|
| `mac` | `mac` | VARCHAR(17) | — |
| `hostname` | `hostname` | VARCHAR(128) | `''` |
| `model` | `model` | VARCHAR(128) | `''` |
| `firmwareVersion` | `firmware_version` | VARCHAR(64) | `''` |
| `ip` | `ip` | VARCHAR(64) | `''` |
| `ssid` | `ssid` | VARCHAR(128) | `''` |
| `interfaces` | `interfaces_json` | TEXT | `'[]'` |
| `ttydEnabled` | `ttyd_enabled` | BOOLEAN | `FALSE` |
| `ttydPort` | `ttyd_port` | INTEGER | `7681` |
| `mdnsHost` | `mdns_host` | VARCHAR(128) | `''` |
| `httpPort` | `http_port` | INTEGER | `80` |
| `accessScope` | `access_scope` | VARCHAR(32) | `'lan'` |
| `heartbeatIntervalSec` | `heartbeat_interval_sec` | INTEGER | `60` |
| `user_id` | `user_id` | INTEGER FK | 从认证上下文中获取 |
| — | `device_name` | VARCHAR(100) | `''` |
| — | `status` | `device_status` | `'registered'` |
| — | `internet_available` | BOOLEAN | `FALSE` |
| — | `is_quant` | BOOLEAN | `FALSE` |
| — | `device_secret` | VARCHAR(100) | `''` |
| — | `paired_at` | TIMESTAMPTZ | `NULL` |
| — | `first_seen_at` | TIMESTAMPTZ | `NOW()` |
| — | `last_seen_at` | TIMESTAMPTZ | `NOW()` |
| — | `created_at` | TIMESTAMPTZ | `NOW()` |
| — | `updated_at` | TIMESTAMPTZ | `NOW()` |

> ⚠️ 原 sqlite 的 `devices` 表用 `last_ip` 等列名，新 PostgreSQL 表用 `ip`、`ssid`。**但是函数返回给调用方的 dict key 必须与原来完全一致**（如 `lastIp`、`lastSsid`），这个映射在 `utils.py` 的 `row_to_device()` 中做，**该函数签名和返回结构不变，只把访问 `row["last_ip"]` 改为 `row["ip"]`**。

#### 12.3.2 心跳数据存储规则

**入口**：`device_manager.py` → `process_heartbeat()` 方法（**方法签名不变**）

**在线状态判定规则**：
```
原逻辑: row["status"] == "online" 或 last_seen 距今 ≤ 180 秒 → isOnline = true
新逻辑: 完全相同的判定规则，只是数据从 PostgreSQL 的 devices 表读取
```

**存储规则**（`quantclaw_receiver/database.py` 的 `process_heartbeat()` 方法内部）：
```
UPDATE devices SET
  last_seen_at = %s, updated_at = %s,
  ip = %s, ssid = %s,
  internet_available = %s,
  status = %s,
  firmware_version = %s,
  ttyd_enabled = %s, ttyd_port = %s,
  mdns_host = %s, http_port = %s,
  access_scope = %s
WHERE mac = %s AND user_id = %s
```

**隐式注册**（`heartbeat_allow_implicit=true` 时的 INSERT）：
- 与 12.3.1 的设备注册 INSERT 语句相同
- 区别在于：心跳中的隐式注册 `hostname` 和 `model` 为空字符串（与原来行为一致）

#### 12.3.3 SSH 配置数据存储规则

**入口**：`main.py` → `POST /api/ssh/configure`（**路由签名不变**）

**存储方式改变**：
```
原: json.dump(cfg, open("ssh_config.json", "w"))
新: INSERT INTO ssh_configs (...) VALUES (...) 
    ON CONFLICT (user_id) DO UPDATE SET host = ..., port = ..., ... updated_at = NOW()
```

**读取方式改变**：
```
原: json.load(open("ssh_config.json"))
新: SELECT * FROM ssh_configs WHERE user_id = %s
```

#### 12.3.4 系统设置数据存储规则

**入口**：`main.py` → `/api/settings` GET/POST（**路由签名不变**）

**存储方式改变**：
```
原: json.dump(settings.dict(), open("settings.json", "w"), ...)
新: INSERT INTO settings (user_id, data, ...) VALUES (%s, %s, ...)
    ON CONFLICT (user_id) DO UPDATE SET data = %s, updated_at = NOW()
```

**读取方式改变**：
```
原: GlobalSettings(**json.load(open("settings.json")))
新: row = cur.execute("SELECT data FROM settings WHERE user_id = %s", (uid,)).fetchone()
    GlobalSettings(**row["data"])
```

> ⚠️ `settings.data` 是 JSONB 列，存储的就是原来 `settings.json` 的全部内容。`GlobalSettings(**row["data"])` 构造出的对象与原来完全一致，后续所有业务逻辑零改动。

### 12.4 前端数据交互格式（必须与原来完全一致）

以下三个接口的响应格式**保持不变**，前端代码（`index.html`、`file_manager.js`）**一行不改**：

#### 12.4.1 `GET /api/devices` 响应格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "scanMode": "loop",
    "scanIntervalSec": 5,
    "pairedCount": 2,
    "pairCount": 2,
    "paired_count": 2,
    "totalKnownCount": 5,
    "pairedDevices": [...],
    "devices": [
      {
        "mac": "b8:27:eb:12:34:56",
        "hostname": "quant-device-1",
        "model": "Raspberry Pi 4",
        "firmwareVersion": "1.0.0",
        "lastIp": "192.168.1.100",
        "lastSsid": "MyWiFi",
        "internetAvailable": true,
        "status": "online",
        "lastSeenAt": "2026-05-20T12:00:00Z",
        "isOnline": true,
        "ttydEnabled": false,
        "ttydPort": 7681,
        "mdnsHost": "",
        "httpPort": 80,
        "accessScope": "lan",
        "httpUrl": "http://192.168.1.100:80",
        "mdnsUrl": "",
        "ttydUrl": "http://192.168.1.100:7681",
        "ssh": "ssh quant@192.168.1.100",
        "sshMdns": ""
      }
    ]
  }
}
```

> ⚠️ **关键**：`devices` 数组中每项的字段名（`mac`、`hostname`、`model`、`firmwareVersion`、`lastIp`、`lastSsid`、`isOnline`...）必须与 `quantclaw_receiver/utils.py` 的 `row_to_device()` 返回的 key 完全一致。这个函数**只需把访问 `row["last_ip"]` 改为 `row["ip"]`、`row["last_ssid"]` 改为 `row["ssid"]`**，其余逻辑不变。

#### 12.4.2 `POST /api/device/register` 响应格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "mac": "b8:27:eb:12:34:56",
    "isNew": true,
    "heartbeatIntervalSec": 60,
    "serverTime": "2026-05-20T12:00:00Z",
    "observedMacs": [...],
    "pairedCandidateMacs": [...],
    "scanMode": "loop",
    "scanIntervalSec": 5,
    "pairedCount": 0,
    "totalKnownCount": 1,
    "pairedDevices": [],
    "devices": [...]
  }
}
```

#### 12.4.3 `POST /api/device/heartbeat` 响应格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "nextHeartbeatIntervalSec": 60,
    "serverTime": "2026-05-20T12:00:00Z",
    "observedMacs": [...],
    "pairedCandidateMacs": [...],
    "scanMode": "loop",
    "scanIntervalSec": 5,
    "pairedCount": 1,
    "totalKnownCount": 1,
    "pairedDevices": [...],
    "devices": [...]
  }
}
```

### 12.5 数据库操作规范

#### 12.5.1 psycopg2 连接池使用模式

```python
# quantclaw_receiver/database.py 中的 DatabaseManager 改法：
from psycopg2 import pool, extras

class DatabaseManager:
    def __init__(self, config):
        self.pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=config.pg_host,
            port=config.pg_port,
            user=config.pg_user,
            password=config.pg_password,
            dbname=config.pg_dbname,
        )
    
    def with_db(self, fn):
        """线程安全的数据库操作包装器 —— 方法签名完全不变"""
        conn = self.pool.getconn()
        try:
            return fn(conn)
        except psycopg2.Error as e:
            raise DatabaseError(f"数据库操作失败: {str(e)}") from e
        finally:
            self.pool.putconn(conn)
    
    # register_device(), process_heartbeat(), get_devices_list() 等方法对外签名完全不变
    # 内部只把 sqlite3.Cursor 操作改为 psycopg2.Cursor 操作
```

#### 12.5.2 认证模块数据库访问模式

```python
# login/database.py 改法：
from psycopg2 import pool

_pool = pool.ThreadedConnectionPool(minconn=2, maxconn=10, ...config...)

def get_db():
    """生成器签名不变，但返回 psycopg2 connection 而非 SQLAlchemy Session"""
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)

# login/auth.py 中 require_auth() 的用法改变：
# 原: user = db.query(User).filter(User.id == user_id).first()
# 新: 
# cur = db.cursor()
# cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
# row = cur.fetchone()
# user = dict(row) if row else None
```

#### 12.5.3 关键 SQL 语法差异速查

| 操作 | sqlite3 写法 | psycopg2 写法 |
|------|-------------|--------------|
| 占位符 | `?` | `%s` |
| 自增主键 | `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| 获取插入后的 ID | `cursor.lastrowid` | `RETURNING id` 或 `cursor.fetchone()[0]` |
| 时间戳 | `TEXT` 存字符串 | `TIMESTAMPTZ` 存 UTC |
| 布尔值 | `INTEGER` (0/1) | `BOOLEAN` (True/False) |
| JSON | `TEXT` 存 JSON 字符串 | `JSONB` 直接存 dict/list |
| UPSERT | `INSERT OR REPLACE` | `INSERT ... ON CONFLICT ... DO UPDATE` |

### 12.6 接口调用流程图

```
┌──────────────────────────────────────────────────────────────┐
│  设备注册流程 (POST /api/device/register)                    │
│                                                              │
│  1. main.py 路由接收请求 → device_manager.register_device()  │
│  2. 提取 device_secret → 查 devices 表校验                     │
│  3. HMAC 签名验证（secret 改为从 devices.device_secret 读）   │
│  4. db_manager.register_device(mac, payload)                  │
│     └─ INSERT INTO devices (...)  ──── 写入 PostgreSQL       │
│  5. db_manager.get_pairing_snapshot(mac, observed)            │
│     └─ SELECT * FROM devices WHERE access_scope='lan' ─── PG │
│  6. 合并结果返回 JSON ── 格式与原来完全一致                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  心跳流程 (POST /api/device/heartbeat)                       │
│                                                              │
│  1. main.py 路由 → device_manager.process_heartbeat()        │
│  2. db_manager.process_heartbeat(mac, payload)                │
│     ├─ 设备不存在 & heartbeat_allow_implicit                  │
│     │  └─ INSERT INTO devices (...) ──── 隐式注册             │
│     └─ 设备已存在                                             │
│        └─ UPDATE devices SET ... WHERE mac=%s AND user_id=%s  │
│  3. 在线判定：status='online' 或 last_seen 距今 ≤ 180s       │
│  4. 返回 JSON ── 格式与原来完全一致                            │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  设备列表流程 (GET /api/devices)                              │
│                                                              │
│  1. main.py 路由 → device_manager.get_devices_list()         │
│  2. db_manager.get_devices_list()                             │
│     └─ SELECT * FROM devices WHERE user_id=%s                 │
│        ORDER BY last_seen_at DESC ──── PostgreSQL             │
│  3. row_to_device() 转换每行为前端格式（函数逻辑不变）          │
│  4. 返回 JSON ── 格式与原来完全一致                            │
│  5. index.html 前端 fetchDevices() 解析 data.devices 展示     │
└──────────────────────────────────────────────────────────────┘
```

### 12.7 必须保证不变的代码清单

以下代码**绝对不允许修改逻辑**，只能在涉及数据库访问的地方做存储层替换：

| 文件 | 保持不变的部分 | 可改的部分 |
|------|-------------|-----------|
| `quantclaw_receiver/utils.py` | 所有工具函数逻辑（`make_sign`、`normalize_mac`、`row_to_device`、`parse_bool`、`pick`、`server_time_str`...） | `row_to_device()` 中访问 row dict 的 key 名（`last_ip`→`ip`、`last_ssid`→`ssid`） |
| `quantclaw_receiver/device_manager.py` | `register_device()`、`process_heartbeat()`、`get_devices_list()` 的业务流程、参数、返回值 | 无（只调用 db_manager 的方法，调用方式不变） |
| `quantclaw_receiver/udp_receiver.py` | UDP 包解析、MAC 提取、响应发送的全部逻辑 | 无 |
| `quantclaw_receiver/exceptions.py` | 所有异常类 | 无 |
| `login/auth.py` | JWT 生成/验证、Cookie 操作、密码加密 | `require_auth()` 和 `get_current_user_from_cookie()` 中的数据库查询语句 |
| `login/sms_utils.py` | 短信发送全部逻辑 | 无 |
| `login/schemas.py` | Pydantic 验证器全部逻辑 | 无（可能需要新增字段，但原有字段不变） |
| `templates/` 全部 | 全部 HTML/CSS/JS | 无 |
| `static/` 全部 | 全部 CSS/JS | 无 |

---

## 十三、权限系统实施细则

### 13.1 权限字段定义

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `role` | VARCHAR(32) | 'role_usr_8f7d' | 用户权限等级（字母数字组合） |

### 13.2 权限等级规范

| role 值 | 角色 | 登录权限 | 用途 |
|---------|------|----------|------|
| `role_usr_8f7d` | 普通用户 | ✅ 本网站可登录 | 正常注册用户 |
| `role_adm_3k9p` | 管理员用户 | ✅ 本网站可登录 | 管理员用户，本网站与管理员网站均可登录 |

### 13.3 权限值设计安全说明

采用"前缀_角色标识_随机后缀"的三层结构设计：

```
role_usr_8f7d
│    │   │
│    │   └─ 4位随机字符（字母+数字），增强不可预测性
│    └─ 角色标识（usr=用户，adm=管理员，spv=特殊）
└─ 固定前缀，便于识别
```

**安全优势**：
- 避免纯数字的简单枚举攻击
- 随机后缀使权限值难以猜测
- 结构清晰便于维护和扩展

### 13.4 注册流程变更

**变更内容**：新用户注册时，`role` 字段自动设置为 `'role_usr_8f7d'`

**SQL 示例**：
```sql
INSERT INTO users (phone, username, password, role, ...) 
VALUES (%s, %s, %s, 'role_usr_8f7d', ...)
```

### 13.5 登录权限验证逻辑

**验证流程**：
1. 用户输入手机号/用户名 + 密码
2. 查询数据库验证密码
3. 调用 `UserRoles.can_login_here(user.role)` 校验：仅白名单 `('role_usr_8f7d', 'role_adm_3k9p')` 通过
4. 校验通过 → 颁发 JWT 并设置 Cookie

**实际实现**（`login/routers/auth_router.py:login` / `login_by_sms`）：
```python
if user is None or not verify_password(req.password, user["password"]):
    return ApiResponse(code=401, message="手机号/用户名或密码错误")

if not UserRoles.can_login_here(user["role"]):
    return ApiResponse(code=403, message="权限不足,无法登录本网站")

set_auth_cookie(response, {"sub": str(user["id"]), "username": user["username"]})
return ApiResponse(code=0, message="登录成功", data={"username": user["username"]})
```

### 13.6 向后兼容性保证

- **现有用户**：ALTER TABLE 添加 `role` 字段时，默认值设为 `'role_usr_8f7d'`，不影响现有用户登录
- **数据迁移**：无需额外数据迁移，所有用户自动获得普通用户权限
- **API 响应**：JWT 颁发和 Cookie 设置逻辑保持不变

### 13.7 权限常量定义（推荐）

建议在代码中定义权限常量，避免硬编码字符串：

```python
# login/constants.py
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
```

### 13.8 预留管理员接口（暂不实现）

为后续管理员网站预留以下接口能力：

| 接口 | 功能 | 说明 |
|------|------|------|
| GET /admin/users | 查询用户列表 | 包含 role 字段 |
| PUT /admin/users/{id}/role | 更新用户权限 | 修改 role 字段值 |
| POST /admin/users | 创建管理员账户 | 可指定 role='role_adm_3k9p' |

> ⚠️ 以上接口在本项目中暂不实现，仅为架构预留。

### 13.9 涉及修改的代码文件

| 文件 | 修改内容 |
|------|----------|
| `login/database.py` | 用户查询 SQL 包含 role 字段 |
| `login/auth.py` | 登录时增加 role 验证 |
| `login/routers/auth_router.py` | 注册时设置 role='role_usr_8f7d'，登录时验证 role |
| `login/schemas.py` | 用户响应模型新增 role 字段（可选） |
| `login/constants.py`（新增） | 定义权限常量 |
