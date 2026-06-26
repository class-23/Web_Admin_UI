# QuantClaw 领域词汇表（Context Glossary）

> 本文件是架构、代码与文档的**共同语义锚点**。所有命名、ADR、issue 必须使用此处的词汇；新增领域概念请追加到本文件而非自由造词。

---

## 1. 角色与组织

| 术语 | 定义 |
|---|---|
| **QuantClaw 平台** | 本仓库代表的整套设备管理后台（FastAPI 应用） |
| **管理员 / 运维** | 拥有 `users.role = admin` 的账户，可管理用户与全局设置 |
| **终端用户** | 普通注册用户，通过手机号 + 密码使用平台 |
| **设备端（IoT 节点）** | 局域网内的 Raspberry Pi（`is_quant=true`），通过 UDP/HTTP 上报注册与心跳 |

---

## 2. 核心领域对象

| 术语 | 别名 | 存储位置 | 关键字段 |
|---|---|---|---|
| **User** | 用户 | PG `users` 表 | `phone / username / password / role` |
| **Device** | 设备 / IoT 节点 | PG `devices` 表 | `mac_address / device_name / status / last_heartbeat_at` |
| **DeviceConfig** | 设备配置 | SQLite `device_configs` 表（**独立配置库**） | `llm_provider / llm_model / wifi_* / skills_json` |
| **HeartbeatLog** | 心跳日志 | PG `heartbeat_logs` 表 | `device_id / status / cpu_usage / memory_usage` |
| **PairCode** | 配对码 | PG `pair_codes` 表 | `code (6 位) / status / expires_at / device_id` |
| **AuditLog** | 审计日志 | PG `audit_logs` 表 | 用户关键操作流水 |
| **Settings** | 用户个性化配置 | PG `settings` 表（JSONB） | `data` |
| **SshConfig** | 用户 SSH 配置 | PG `ssh_configs` 表 | `host / port / username / password / remote_path` |

---

## 3. 设备生命周期状态机

```
registered ──(首次心跳)──▶ online
     │                        │
     │                        └──(heartbeat 过期 180s)──▶ offline
     │
     └──(管理员显式断开)──▶ disconnected
```

术语：
- **registered**：设备已注册但尚未上报心跳
- **online**：最近 180s 内有心跳
- **offline**：超过 180s 无心跳
- **disconnected**：被管理员显式断开（UDP 拒绝）

---

## 4. 配对（Pairing）流程

1. 用户在 Web 端创建 `PairCode`（6 位数字，`pending` 状态，5 分钟有效期）
2. 设备端输入配对码 → 服务器校验 → 写入 `device.user_id`，状态从 `pending → used`
3. 已使用 / 已过期的码状态分别为 `used` / `expired`

术语：**paired**（已配对）= `device.user_id IS NOT NULL`。

---

## 5. 认证通道

| 通道 | 用途 | 实现 |
|---|---|---|
| **Cookie + JWT** | 浏览器用户 | `python-jose` 签发，HTTP-only Cookie |
| **API Key + Phone** | 设备端查询 | Header `X-API-Key` + `X-Phone` 或 Query `api_key` + `phone` |
| **短信验证码** | 注册 / 忘记密码 | `login.sms_utils.send_sms` 通道（外部 SMS 网关） |

术语：**查询 API Key** = `app.core.config.settings.QUERY_API_KEY`。

---

## 6. 术语禁用清单（避免命名漂移）

| ❌ 不要用 | ✅ 应该用 | 原因 |
|---|---|---|
| "Raspberry Pi" / "rpi" 在用户可见 UI | **Quant 设备** / **IoT 节点** | 业务语义是"Quant 品牌"，硬件是实现细节 |
| "scan device" | **设备注册 / 心跳** | 项目已脱离 nmap 扫描，IoT 是主动注册 |
| "file" 模糊时 | **本地文件** 或 **远程 SSH 文件** | 两种语义不同存储路径 |
| `miyao_key` / `secret_key` 字段 | **device_secret**（设备）/ **password_hash**（用户） | 历史字段已废弃，禁止复活 |

---

## 7. 仓库角色边界

| 目录 | 角色 | 是否可作为外部依赖 |
|---|---|---|
| `app/` | **新体系主域**（canonical） | 是，未来单一入口 |
| `quantclaw_receiver/`（根） | **legacy 接缝层**（deprecated facade） | 否，仅供 `main.py` 旧调用方 |
| `login/` | **legacy 认证包** | 否，并入 `app/services/auth_service.py` |
| `main.py` | **legacy 启动入口** | 否，重构至 `app.app_factory.create_app()` |
| `app/app_factory.py` | **canonical 入口** | 是 |
| `docs/adr/` | 架构决策记录 | 是 |
| `tests/` | 测试 | 是 |

---

## 8. 待澄清（Open Questions）

- [ ] 「Quant 设备」是否仍使用 nmap 扫描？当前 `quantclaw_receiver/` 内 UDP 模块与扫描功能是否仍在使用？
- [ ] `login.sms_utils` 外部短信网关是否仍是产品需求？如否，登录可移除短信通道
- [ ] `SETTINGS_DB_PATH = "runtime/settings.sqlite"` 配置库是按设备迁移场景设计还是临时缓存？

---

> 任何命名争议，请先查本表；未涵盖者，请追加而非替换。
