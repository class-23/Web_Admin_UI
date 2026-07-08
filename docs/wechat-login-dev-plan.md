# 微信扫码登录功能开发文档

> 项目名称：QuantClaw 设备管理后台
> 文档版本：v1.0
> 状态：待 appid/secret 审核通过后补充具体值

---

## 一、功能概述

### 1.1 目标

为 QuantClaw 设备管理后台新增微信扫码登录功能，用户可通过微信扫描二维码快速登录系统。功能涵盖：

- 微信扫码登录（首次需绑定手机号，后续可直接登录）
- 微信用户信息存储与管理
- 用户授权变更处理（资料变更、撤回授权、注销）

### 1.2 总体流程

```
用户点击"微信登录" → 页面展示二维码 → 用户使用微信扫码
    → 微信回调携带 code
    → 后端用 code 换取 access_token + openid + unionid
    → 获取微信用户基本信息
    → 判断是否已绑定：
        ┌─ 已绑定 → 直接登录（设置 JWT Cookie）
        └─ 未绑定 → 跳转手机号绑定页面 → 绑定成功后登录
```

---

## 二、数据库变更方案

### 2.1 字段设计

在现有 `users` 表 `phone` 字段后新增 `wechat_info` 字段（JSON 格式），用于存储微信登录相关所有信息。

**变更后 `users` 表结构（仅列示变更部分）：**

```sql
-- 在 phone 字段后新增 wechat_info 字段
ALTER TABLE users
ADD COLUMN wechat_info JSONB DEFAULT NULL;

-- 为加速通过 openid 查询用户，建议创建索引
CREATE INDEX idx_users_wechat_openid ON users ((wechat_info->>'openid'));
CREATE INDEX idx_users_wechat_unionid ON users ((wechat_info->>'unionid'));
```

### 2.2 wechat_info 字段存储内容

```json
{
  "openid": "oXv7S5xxxxxxxxxxxxxxxxx",
  "unionid": "o6_bmasdasdsad6_2sgVt7hMZOPfL",
  "nickname": "微信用户昵称",
  "headimgurl": "https://thirdwx.qlogo.cn/.../0",
  "access_token": "微信授权access_token",
  "refresh_token": "用于刷新access_token的凭证",
  "token_expires_at": 1719782400,
  "bound_at": "2024-06-30T12:00:00Z",
  "last_login_at": "2024-06-30T14:00:00Z"
}
```

### 2.3 `login/database.py` 建表语句修改

在 `init_db()` 函数中新增 wechat_info 列迁移和审计日志表（对齐现有迁移模式）：

```python
# 在 init_db() 中添加 wechat_info 列迁移（对齐现有的 miyao_key/role 迁移模式）
cur.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'wechat_info'
        ) THEN
            ALTER TABLE users ADD COLUMN wechat_info JSONB DEFAULT NULL;
        END IF;
    END
    $$;
""")

# 索引单独创建（与表结构分离，方便维护）
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_users_wechat_openid
    ON users ((wechat_info->>'openid'))
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_users_wechat_unionid
    ON users ((wechat_info->>'unionid'))
""")

# 新增：登录审计日志表（用于风控分析）
cur.execute("""
    CREATE TABLE IF NOT EXISTS login_audit_log (
        id          SERIAL PRIMARY KEY,
        openid      VARCHAR(128),
        user_id     INTEGER REFERENCES users(id),
        ip          VARCHAR(45) NOT NULL,
        status      VARCHAR(20) NOT NULL,
        method      VARCHAR(20) NOT NULL,
        reason      TEXT DEFAULT '',
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_login_audit_openid_time
    ON login_audit_log (openid, created_at DESC)
""")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_login_audit_ip_time
    ON login_audit_log (ip, created_at DESC)
""")
```

---

## 三、微信扫码登录完整流程

### 3.1 步骤一：前端展示二维码（优化版）

#### 3.1.1 核心设计思路

大厂标准微信扫码登录体验遵循三点原则：

1. **状态实时反馈** — 二维码展示到登录成功之间经历三个状态（等待扫码 → 已扫码/等待确认 → 登录中），每个状态都通过 UI 即时传达给用户
2. **异常自动恢复** — 二维码过期后自动刷新，无需用户手动操作；网络恢复后自动恢复扫码状态
3. **安全闭环** — 二维码携带设备指纹 hash 和随机 state，回调时校验一致性

**状态流转图：**

```
点击"微信登录" → QR 码加载中（骨架屏）
   → QR 码就绪（展示二维码 + 2 分钟倒计时）
      → 微信扫码（触发 onScan 回调）→ UI 更新为"已扫码，请在手机上确认"
         → 用户手机上确认 → 微信重定向到回调 URL
            → 后端处理成功 → 重定向到首页
            → 后端处理失败 → 显示错误页/重试
         → QR 码 2 分钟未扫码 → 自动刷新（最多刷新 1 次）
```

#### 3.1.2 登录页布局修改方案

##### 布局修改前后对比

**修改前（当前 login.html 结构）：**

```
┌─────────────────────────────────────────┐
│              用户登录                     │
├─────────────────────────────────────────┤
│  [密码登录]  [验证码登录]   ← .tab-btn  │
├─────────────────────────────────────────┤
│  密码登录表单 / 验证码登录表单            │
├─────────────────────────────────────────┤
│  忘记密码？          注册账号            │
└─────────────────────────────────────────┘
```

**修改后（添加微信登录入口）：**

```
┌─────────────────────────────────────────┐
│              用户登录                     │
├─────────────────────────────────────────┤
│  [密码登录]  [验证码登录]   ← .tab-btn  │
├─────────────────────────────────────────┤
│  密码登录表单 / 验证码登录表单            │
├─────────────────────────────────────────┤
│         ─── 或 ───                      │
│  [▉ 微信扫码登录]   ← 类 .tab-btn 风格  │
├─────────────────────────────────────────┤
│  忘记密码？          注册账号            │
└─────────────────────────────────────────┘
```

**关键修改点：**
1. 在最后一个 `.tab-panel` 结束与 `.footer-links` 之间插入微信登录入口
2. 分隔线使用浅灰色 `#e2e8f0` 水平线 + "或" 文字
3. 微信按钮的视觉尺寸 `.tab-btn` 保持一致（`height: 44px`, `font-size: 15px`, `font-weight: 600`）
4. 按钮交互效果与 `.tab-btn` 一致（悬停时 `color` / `border-color` 过渡动画 0.2s）
5. 微信图标使用内联 SVG，颜色 `#07c160`（微信品牌绿）

##### 布局修改后的 HTML 代码

在现有 `templates/login.html` 的最后一个 `.tab-panel` 结束之后、`.footer-links` 之前添加以下代码（对齐现有页面的设计语言，使用与 `.tab-btn` 一致的视觉规格）：

```html
<!-- ===== 微信登录入口（在 .tab-panel 之后、.footer-links 之前插入） ===== -->
<div class="wechat-login-section" style="margin-top: 20px;">

  <!-- "或" 分隔线 -->
  <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
    <span style="flex: 1; height: 1px; background: #e2e8f0;"></span>
    <span style="font-size: 13px; color: #a0aec0; white-space: nowrap; user-select: none;">或</span>
    <span style="flex: 1; height: 1px; background: #e2e8f0;"></span>
  </div>

  <!-- 微信扫码登录按钮（视觉规格与 .tab-btn 完全一致） -->
  <button id="wechatLoginBtn" type="button"
          style="width: 100%; height: 44px; padding: 10px 0;
                 border: none; border-bottom: 2px solid transparent;
                 background: none;
                 font-size: 15px; font-weight: 600;
                 color: #07c160;
                 cursor: pointer;
                 display: flex; align-items: center; justify-content: center; gap: 6px;
                 transition: color 0.2s, border-color 0.2s, background 0.2s;">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"
         style="flex-shrink: 0;">
      <path d="M8.5 11a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3Zm7 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3ZM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2Zm-1.5 14.5c-2.33 0-4.5-1.5-4.5-3.5S8.17 9.5 10.5 9.5 15 11 15 13s-2.17 3.5-4.5 3.5Zm7-1.5c.55 0 1-.45 1-1s-.45-1-1-1-.5-.5-.5-.5"/>
    </svg>
    <span>微信扫码登录</span>
  </button>
</div>

<style>
/* 微信按钮交互效果（与 .tab-btn hover 过渡一致：color/border-color 0.2s ease） */
#wechatLoginBtn:hover {
  color: #06ad56;
  border-bottom-color: #07c160;
  background: rgba(7, 193, 96, 0.04);
}
#wechatLoginBtn:active {
  background: rgba(7, 193, 96, 0.08);
}
#wechatLoginBtn:disabled {
  color: #a0aec0;
  cursor: not-allowed;
  background: none;
  border-bottom-color: transparent;
}
</style>
```

**与 `.tab-btn` 样式一致性对照表：**

| 属性 | `.tab-btn`（密码登录/验证码登录） | `#wechatLoginBtn`（微信登录） | 说明 |
|---|---|---|---|
| `height` | 44px（`padding: 10px 0` + `line-height`） | 44px（`padding: 10px 0`） | 完全一致 |
| `font-size` | 15px | 15px | 完全一致 |
| `font-weight` | 600 | 600 | 完全一致 |
| `border` | none / `border-bottom: 2px solid` | none / `border-bottom: 2px solid` | 完全一致 |
| `background` | none | none | 完全一致 |
| `cursor` | pointer | pointer | 完全一致 |
| 悬停过渡 | `color 0.2s, border-color 0.2s` | `color 0.2s, border-color 0.2s, background 0.2s` | 增加背景过渡增强反馈 |
| 主色调 | `#667eea`（紫色） | `#07c160`（微信绿） | 不同品牌色 |
| 悬浮色 | `#4a5568`（深灰文字） | `#06ad56`（深绿文字） | 各自加深 |
| 激活态 | 无 | `rgba(7,193,96,0.08)` 背景 | 额外提供点击反馈 |

##### 技术实现要点

1. **按钮非表单提交按钮** — 使用 `type="button"` 防止触发表单默认提交行为，与 `.tab-btn` 一致
2. **SVG 图标内联** — 直接嵌入 HTML，不依赖外部图标库，减少 HTTP 请求
3. **禁用态样式** — 当 `WECHAT_APPID` 未配置时，按钮应设为 `disabled`，此时颜色变为 `#a0aec0` 并禁止点击
4. **不破坏现有布局** — 使用 `margin-top: 20px` 分隔，不与表单区域产生垂直 margin 折叠
5. **用户无感知降级** — appid 未配置时，按钮显示为禁用态，点击时 Toast 提示"微信登录暂未开放"，不报错、不崩溃

##### 用户体验注意事项

1. **按钮可见性状态管理**
   - 微信登录按钮默认启用，但点击前先校验 `WECHAT_APPID` 是否已配置
   - 未配置时按钮显示为禁用态（`color: #a0aec0`, `cursor: not-allowed`），点击弹出 Toast 提示"微信登录暂未开放"
   - 避免直接隐藏按钮，防止老用户疑惑"微信登录入口去哪了"

2. **用户操作路径最短化**
   - 从点击"微信扫码登录"到二维码展示，应控制在 1.5 秒以内（骨架屏过渡动画需平滑）
   - 二维码加载超过 3 秒时展示"加载中"状态并附带重试入口
   - 避免在二维码展示前额外弹窗确认（如"是否使用微信登录？"），减少不必要的操作步骤

3. **二维码过期处理（无感刷新 vs 主动刷新）**
   - 首次过期（120 秒未扫码）：自动刷新二维码，不打扰用户
   - 再次过期（刷新后仍超时）：展示显式的"二维码已过期"状态 + "重新获取"按钮，将控制权交给用户
   - 倒计时最后 30 秒切换为红色文字，预警即将过期

4. **扫码状态反馈链**
   - 用户扫码后，二维码区域应立即从"等待扫码"切换为"已扫码，请在手机上确认"（< 1 秒响应）
   - 若用户手机上取消确认，二维码应恢复为"等待扫码"状态，而非停留在"已扫码"状态
   - 若用户在手机上确认后后端处理超过 3 秒，展示"正在登录..."旋转加载动画

5. **移动端适配**
   - 二维码弹窗在移动端（< 480px）降低内边距（`padding: 28px 20px`），圆角减小（`border-radius: 12px`）
   - 微信登录按钮高度保持 44px 不变（符合 iOS HIG 触控目标最小尺寸）
   - 在微信内置浏览器中自动降级为手动跳转授权（因 WxLogin 的 iframe 方案在微信浏览器中不可用）

6. **无障碍访问（Accessibility）**
   - 微信登录按钮需添加 `aria-label="微信扫码登录"` 属性
   - 二维码弹窗需添加 `role="dialog"` 和 `aria-modal="true"`，关闭按钮需 `aria-label="关闭"`
   - 各状态切换时，通过 `aria-live="polite"` 区域向屏幕阅读器播报状态变化
   - 所有交互元素（按钮、链接）需支持键盘焦点和 Enter 键触发

7. **错误降级策略优先级**
   ```
   WxLogin 组件加载成功 → 展示正常二维码
   WxLogin 组件加载失败 →
      ├─ 方案A: 短链接跳转授权（无损体验）
      └─ 方案B: 提示"微信登录暂不可用"，引导使用密码/验证码登录
   ```
   - 二维码渲染失败不应导致页面卡死或白屏
   - 降级方案应明确指引用户可继续完成登录的其他方式

8. **视觉一致性**
   - 微信品牌色 `#07c160` 的使用仅限于微信相关元素（按钮文字、二维码边框、扫码成功图标）
   - 分隔线"或"的样式需与页面其他分割元素的视觉语言一致（浅灰 `#e2e8f0`，1px）
   - 弹窗关闭按钮的悬浮效果与页面其他关闭/取消操作一致（`color: #718096` → `#4a5568`）

##### 相关页面链接关系

```
┌─────────────────────────────────────────────────────────────┐
│                    页面路由关系总图                           │
│                      (完整登录链路)                           │
└─────────────────────────────────────────────────────────────┘

                              ┌──────────────────┐
                              │    /login         │
                              │   登录页          │
                              │   login.html      │
                              └────────┬─────────┘
                                       │ 点击"微信扫码登录"
                                       ▼
                              ┌──────────────────┐
                              │   二维码弹窗      │
                              │   (页面内 Modal)  │
                              │   wechatQrModal   │
                              └────────┬─────────┘
                                       │ 使用微信扫描二维码
                                       ▼
                              ┌──────────────────┐
                              │   微信开放平台     │
                              │   扫码 + 确认     │
                              └────────┬─────────┘
                                       │ 回调 /api/wechat/callback?code=xxx&state=xxx
                                       ▼
                    ┌─────────────────────────────────────┐
                    │       后端回调处理                    │
                    │   判断用户 wechat_info 是否已绑定      │
                    └───────────┬─────────────┬───────────┘
                                │             │
                         已绑定 │             │ 未绑定
                                ▼             ▼
                    ┌──────────────────┐   ┌──────────────────────────┐
                    │ 设置 JWT Cookie  │   │ /bind-wechat             │
                    │ 重定向 /         │   │ 绑定页面                 │
                    │ (首页)           │   │ bind-wechat.html         │
                    └──────────────────┘   └────────────┬─────────────┘
                                                         │ 输入手机号 + 验证码
                                                         │ POST /api/wechat/bind
                                                         ▼
                                              ┌──────────────────────────┐
                                              │ 绑定成功                 │
                                              │ 设置 JWT Cookie          │
                                              │ 重定向 / (首页)           │
                                              └──────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│                    API 调用关系图                             │
└─────────────────────────────────────────────────────────────┘

  前端 (login.html / bind-wechat.html)          后端 API                   微信开放平台
  ──────────────────────────────    ────────────────    ───────────────────
  
  [login.html 加载]
       │
       ├─→ GET  /login                          (页面路由, main.py)
       │
  [点击"微信登录"]
       │
       ├─→ POST /api/wechat/qr-session          (创建扫码 session)
       │         ← {"session_id", "state", "signature"}
       │
       ├─→ 加载 WxLogin SDK iframe ──────────→ https://open.weixin.qq.com/connect/qrconnect
       │         ← 展示二维码 (iframe 渲染)
       │
       ├─→ GET  /api/wechat/qr-session/{id}/status  (轮询, 2s 间隔)
       │         ← {"status": "pending"|"scanned"|"confirmed"|"expired"}
       │
  [用户在手机上确认]
       │
       └─→ GET  /api/wechat/callback?code=&state=  (微信回调)
                │
                ├─→ 换取 token ──────────────→ https://api.weixin.qq.com/sns/oauth2/access_token
                │         ← {access_token, openid, unionid, ...}
                │
                ├─→ 获取用户信息 ────────────→ https://api.weixin.qq.com/sns/userinfo
                │         ← {nickname, headimgurl, ...}
                │
                ├─ [已绑定] → 设置 Cookie → 302 /  (首页)
                │
                └─ [未绑定] → 生成 bind_token → 302 /bind-wechat?bind_token=xxx

  [bind-wechat.html 加载]
       │
       ├─→ GET  /bind-wechat?bind_token=xxx     (页面路由, main.py)
       │
  [输入手机号]
       │
       ├─→ GET  /api/wechat/check-phone?phone=  (校验是否注册)
       │         ← {"registered": true|false}
       │
  [点击"获取验证码"]
       │
       └─→ POST /api/send-code                  (发送短信验证码)
                ← {"code": 0, "message": "验证码已发送"}

  [点击"完成绑定"]
       │
       └─→ POST /api/wechat/bind               (执行绑定)
                │  {bind_token, phone, code}
                │
                ├─ [成功] → 设置 Cookie → {"code": 0, "message": "绑定成功"}
                │           → 前端跳转 /
                │
                └─ [失败] → sub_code 精细定位错误
                            WX_007 → 令牌过期 → 跳回 /login
                            WX_008 → 手机号未注册 → 清空输入框
                            WX_009 → 验证码错误 → 清空验证码


┌─────────────────────────────────────────────────────────────┐
│                   页面跳转与状态传递                           │
└─────────────────────────────────────────────────────────────┘

  源页面 / 组件              目标页面              传递参数                    传递方式
  ───────────────────       ──────────           ──────────────              ────────────
  login.html (弹窗)    →   /api/wechat/callback   code, state (微信回调)     HTTP 302 重定向
  /api/wechat/callback →   /                     JWT Cookie (auth_token)     Cookie
  /api/wechat/callback →   /bind-wechat          bind_token (JWT 令牌)       URL Query (?bind_token=xxx)
  bind-wechat.html     →   /                     JWT Cookie (auth_token)     提交绑定后 JS 跳转
  bind-wechat.html     →   /login                无                          "返回登录" 链接
  bind-wechat.html     →   /api/send-code        手机号                       POST JSON
  bind-wechat.html     →   /api/wechat/check-phone 手机号                    GET Query
  bind-wechat.html     →   /api/wechat/bind      bind_token + phone + code   POST JSON


┌─────────────────────────────────────────────────────────────┐
│                   文件依赖关系                                 │
└─────────────────────────────────────────────────────────────┘

  templates/
  ├── login.html                    ← 注入: {{WECHAT_APPID}}, {{WECHAT_REDIRECT_URI}}
  │     ├── 引入: wxLogin.js (CDN)  ← https://res.wx.qq.com/connect/zh_CN/htmledition/js/wxLogin.js
  │     └── 引入: 内联 CSS/JS        ← 无需外部依赖
  │
  └── bind-wechat.html              ← 注入: {{BIND_TOKEN}}, {{WECHAT_NICKNAME}}, {{WECHAT_AVATAR}}
        └── 引入: 内联 CSS/JS        ← 无需外部依赖

  login/
  ├── wechat_router.py              ← 依赖: auth.py, code_store.py, config.py, database.py
  ├── wechat_service.py             ← 依赖: auth.py, config.py
  │     └── 外部: httpx, jose
  └── wechat_token_manager.py       ← 依赖: config.py
        └── 外部: httpx

  main.py                           ← 注册: wechat_router (prefix=/api)
                                     ← 注册: /bind-wechat 页面路由
```

**页面路由说明：**

| URL 路径 | 模板文件 | 访问方式 | 说明 |
|---|---|---|---|
| `/login` | `templates/login.html` | GET（浏览器访问） | 用户登录页，包含密码登录、验证码登录、微信扫码登录三个入口 |
| `/api/wechat/callback` | — | GET（微信回调） | 微信开放平台回调端点，处理后端扫码登录逻辑 |
| `/bind-wechat` | `templates/bind-wechat.html` | GET（含 bind_token 参数） | 首次微信登录用户绑定手机号页面 |
| `/` | — | GET（首页） | 登录成功后重定向目标，JWT Cookie 认证 |
| `/api/send-code` | — | POST | 发送短信验证码（复用现有 auth_router 端点） |
| `/api/wechat/check-phone` | — | GET | 校验手机号是否注册（绑定流程前置校验） |
| `/api/wechat/bind` | — | POST | 微信账号绑定手机号（核心绑定 API） |
| `/api/wechat/qr-session` | — | POST | 创建微信扫码 session |
| `/api/wechat/qr-session/{id}/status` | — | GET | 轮询扫码状态 |

#### 3.1.3 二维码弹窗（含状态反馈 UI）

弹窗包含三个关键区域：状态提示区、二维码展示区、底部操作区。

```html
<!-- 微信二维码弹窗 -->
<div id="wechatQrModal" class="modal-overlay" style="display:none; position: fixed; inset:0;
     background: rgba(0,0,0,0.5); z-index:1000; display:none; align-items:center; justify-content:center;">
  <div class="modal-card" style="background:#fff; border-radius:16px; padding:32px;
       width:380px; max-width:90vw; box-shadow:0 24px 80px rgba(0,0,0,0.2); position:relative;">
    <!-- 关闭按钮 -->
    <button id="qrCloseBtn" style="position:absolute; top:16px; right:16px;
            border:none; background:none; font-size:24px; cursor:pointer; color:#a0aec0; line-height:1;">&times;</button>

    <h2 style="text-align:center; font-size:18px; font-weight:700; color:#2d3748; margin-bottom:20px;">
      微信扫码登录
    </h2>

    <!-- 状态区：根据扫码阶段展示不同状态 -->
    <div id="qrStatusArea" style="text-align:center; min-height:300px; display:flex;
         flex-direction:column; align-items:center; justify-content:center;">

      <!-- [状态1] 二维码加载中（骨架屏） -->
      <div id="qrStateLoading" style="display:none; text-align:center;">
        <div class="skeleton-qr" style="width:220px; height:220px; margin:0 auto 16px;
             background:linear-gradient(90deg,#e2e8f0 25%,#edf2f7 50%,#e2e8f0 75%);
             background-size:200% 100%; animation:shimmer 1.5s infinite; border-radius:8px;"></div>
        <p style="color:#718096; font-size:13px;">二维码加载中...</p>
      </div>

      <!-- [状态2] 二维码就绪 -->
      <div id="qrStateReady" style="display:none; text-align:center;">
        <div id="wechat_qrcode_container" style="width:220px; height:220px; margin:0 auto 12px;"></div>
        <p style="color:#4a5568; font-size:14px; font-weight:500;">请使用微信扫描二维码登录</p>
        <p id="qrExpireTimer" style="color:#e53e3e; font-size:12px; margin-top:6px;">二维码 2 分钟有效</p>
        <!-- 倒计时进度条 -->
        <div style="width:220px; height:3px; background:#e2e8f0; border-radius:2px; margin:10px auto 0; overflow:hidden;">
          <div id="qrProgressBar" style="width:100%; height:100%; background:#07c160;
               border-radius:2px; transition:width 1s linear;"></div>
        </div>
      </div>

      <!-- [状态3] 已扫码，待确认 -->
      <div id="qrStateScanned" style="display:none; text-align:center;">
        <div style="width:80px; height:80px; margin:20px auto 16px; position:relative;">
          <svg viewBox="0 0 100 100" width="80" height="80">
            <circle cx="50" cy="50" r="45" fill="none" stroke="#07c160" stroke-width="4"/>
            <path d="M30 50 L45 65 L70 35" fill="none" stroke="#07c160" stroke-width="6" stroke-linecap="round"/>
          </svg>
          <div class="pulse-ring" style="position:absolute; inset:-8px; border:2px solid #07c160;
               border-radius:50%; animation:pulse 2s infinite;"></div>
        </div>
        <p style="color:#2d3748; font-size:15px; font-weight:600;">已扫码</p>
        <p style="color:#718096; font-size:13px; margin-top:4px;">请在手机上确认登录</p>
      </div>

      <!-- [状态4] 登录中 -->
      <div id="qrStateLogging" style="display:none; text-align:center;">
        <div class="spinner" style="width:48px; height:48px; margin:20px auto 16px;
             border:4px solid #e2e8f0; border-top-color:#667eea; border-radius:50%;
             animation:spin 0.8s linear infinite;"></div>
        <p style="color:#2d3748; font-size:15px; font-weight:600;">正在登录...</p>
        <p style="color:#718096; font-size:13px; margin-top:4px;">即将为您跳转</p>
      </div>

      <!-- [状态5] 已过期，可重试 -->
      <div id="qrStateExpired" style="display:none; text-align:center;">
        <div style="width:64px; height:64px; margin:20px auto 16px; color:#e53e3e;">
          <svg viewBox="0 0 24 24" width="64" height="64" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 15c-.55 0-1-.45-1-1v-2c0-.55.45-1 1-1s1 .45 1 1v2c0 .55-.45 1-1 1zm1-6h-2V7h2v4z"/>
          </svg>
        </div>
        <p style="color:#e53e3e; font-size:15px; font-weight:600;">二维码已过期</p>
        <p style="color:#718096; font-size:13px; margin:8px 0 16px;">请点击下方按钮重新获取</p>
        <button id="qrRefreshBtn" style="height:38px; padding:0 28px; border:none; border-radius:8px;
                background:#667eea; color:#fff; font-size:14px; font-weight:600; cursor:pointer;
                transition:background 0.2s;">重新获取</button>
      </div>
    </div>

    <!-- 底部操作栏 -->
    <div style="text-align:center; margin-top:16px; padding-top:16px; border-top:1px solid #e2e8f0;">
      <a href="javascript:;" id="qrSwitchPwdLogin" style="color:#667eea; font-size:13px; text-decoration:none;">
        返回密码登录
      </a>
    </div>
  </div>
</div>

<style>
@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
@keyframes pulse { 0%{opacity:1;transform:scale(1)} 100%{opacity:0;transform:scale(1.15)} }
@keyframes spin { to{transform:rotate(360deg)} }
.toast { position:fixed; top:20px; left:50%; transform:translateX(-50%); z-index:9999;
  padding:12px 24px; border-radius:10px; font-size:14px; font-weight:500;
  box-shadow:0 8px 24px rgba(0,0,0,0.15); transition:opacity 0.3s, transform 0.3s;
  opacity:0; pointer-events:none; }
.toast.show { opacity:1; transform:translateX(-50%) translateY(0); }
.toast.success { background:#c6f6d5; color:#276749; }
.toast.error { background:#fed7d7; color:#9b2c2c; }
.toast.info { background:#bee3f8; color:#2b6cb0; }
</style>
```

#### 3.1.4 微信 JS 初始化及完整交互逻辑

```html
<!-- 在页面底部引入微信 JS -->
<script src="https://res.wx.qq.com/connect/zh_CN/htmledition/js/wxLogin.js"></script>
```

```javascript
// ==============================================================
// 全局 Toast 通知系统（轻量级，不依赖第三方库）
// ==============================================================
var Toast = (function() {
  var el = document.createElement('div');
  el.className = 'toast';
  document.body.appendChild(el);
  var timer = null;

  function show(text, type) {
    el.textContent = text;
    el.className = 'toast ' + type + ' show';
    clearTimeout(timer);
    timer = setTimeout(function() { el.className = 'toast'; }, 3000);
  }
  return { success: function(t) { show(t, 'success'); },
           error: function(t) { show(t, 'error'); },
           info: function(t) { show(t, 'info'); } };
})();

// ==============================================================
// 设备指纹生成（用于绑定扫码会话，防 CSRF/重放攻击）
// ==============================================================
function getDeviceFingerprint() {
  var stored = sessionStorage.getItem('device_fp');
  if (stored) return stored;
  var nav = navigator;
  var raw = (nav.userAgent || '') + '|' + (nav.language || '') + '|' +
            (screen.width || '') + 'x' + (screen.height || '') + '|' +
            (nav.hardwareConcurrency || '');
  var hash = 0;
  for (var i = 0; i < raw.length; i++) {
    var ch = raw.charCodeAt(i);
    hash = ((hash << 5) - hash) + ch;
    hash |= 0;
  }
  var fp = 'fp_' + Math.abs(hash).toString(36);
  sessionStorage.setItem('device_fp', fp);
  return fp;
}

// ==============================================================
// 二维码管理器
// ==============================================================
var QrManager = {
  wxLoginObj: null,
  state: '',
  deviceFp: '',
  refreshCount: 0,
  maxRefresh: 1,
  expireTimer: null,
  progressTimer: null,
  qrExpireSec: 120,

  // ----- 状态切换辅助 -----
  showState: function(stateId) {
    ['qrStateLoading','qrStateReady','qrStateScanned',
     'qrStateExpired','qrStateLogging'].forEach(function(id) {
      document.getElementById(id).style.display = (id === stateId) ? 'block' : 'none';
    });
  },

  // ----- 打开弹窗并初始化 -----
  open: function(appid, redirectUri) {
    var modal = document.getElementById('wechatQrModal');
    modal.style.display = 'flex';

    this.deviceFp = getDeviceFingerprint();
    this.state = 'wx_' + Math.random().toString(36).substring(2, 15) + '_' + this.deviceFp;

    sessionStorage.setItem('wechat_state', this.state);
    this.showState('qrStateLoading');
    this.loadQrCode(appid, redirectUri);
  },

  // ----- 加载二维码 -----
  loadQrCode: function(appid, redirectUri) {
    var self = this;

    // 清除旧实例
    if (this.wxLoginObj) {
      document.getElementById('wechat_qrcode_container').innerHTML = '';
    }
    this.clearTimers();

    // 设置二维码失效计时总时长（秒）
    this.qrExpireSec = 120;
    this.updateProgressBar(100);

    this.wxLoginObj = new WxLogin({
      self_redirect: false,
      id: 'wechat_qrcode_container',
      appid: appid,
      scope: 'snsapi_login',
      redirect_uri: encodeURIComponent(redirectUri),
      state: this.state,
      style: 'black',
      stylelite: 1
    });

    // ← 关键: 监听 WxLogin 的 onScan 回调 ←
    // 当用户在微信上扫码（尚未确认）时触发
    // 注意：WxLogin 组件会在全局 window 上发布事件
    window._wxScanCallback = function() {
      self.showState('qrStateScanned');
    };

    // 1.5 秒后从骨架屏切换到就绪态
    setTimeout(function() {
      if (document.getElementById(self.state)) {
        // WxLogin 创建了 iframe，二维码展示成功
      }
      self.showState('qrStateReady');
      self.startExpireCountdown();
    }, 1500);
  },

  // ----- 倒计时与进度条 -----
  startExpireCountdown: function() {
    var self = this;
    var remain = this.qrExpireSec;
    var expireEl = document.getElementById('qrExpireTimer');
    var progressEl = document.getElementById('qrProgressBar');

    this.expireTimer = setInterval(function() {
      remain--;
      if (remain <= 0) {
        self.clearTimers();
        if (self.refreshCount < self.maxRefresh) {
          // 自动刷新（最大 1 次）
          self.refreshCount++;
          self.loadQrCode();
        } else {
          self.showState('qrStateExpired');
        }
        return;
      }
      if (remain <= 30) {
        expireEl.textContent = '二维码 ' + remain + ' 秒后过期';
        expireEl.style.color = '#e53e3e';
      }
      self.updateProgressBar(Math.round((remain / self.qrExpireSec) * 100));
    }, 1000);
  },

  updateProgressBar: function(pct) {
    var bar = document.getElementById('qrProgressBar');
    if (bar) bar.style.width = Math.max(0, pct) + '%';
  },

  clearTimers: function() {
    clearInterval(this.expireTimer);
    clearInterval(this.progressTimer);
  },

  // ----- 关闭弹窗，清理资源 -----
  close: function() {
    this.clearTimers();
    this.showState('qrStateLoading');
    document.getElementById('wechatQrModal').style.display = 'none';
    if (this.wxLoginObj) {
      document.getElementById('wechat_qrcode_container').innerHTML = '';
      this.wxLoginObj = null;
    }
  }
};

// ==============================================================
// 事件绑定
// ==============================================================
document.addEventListener('DOMContentLoaded', function() {
  var appid = '{{WECHAT_APPID}}';
  var redirectUri = '{{WECHAT_REDIRECT_URI}}';

  // 点击微信登录按钮
  document.getElementById('wechatLoginBtn').addEventListener('click', function() {
    // appid 由后端注入：从 config.WECHAT_APPID 读取，在 login.html 中通过模板替换注入
    if (!appid || appid === 'YOUR_WECHAT_APPID') {
      Toast.error('微信登录暂未开放，请稍后重试');
      return;
    }
    QrManager.open(appid, redirectUri);
  });

  // 关闭弹窗
  document.getElementById('qrCloseBtn').addEventListener('click', function() {
    QrManager.close();
  });

  // 点击遮罩层关闭
  document.getElementById('wechatQrModal').addEventListener('click', function(e) {
    if (e.target === this) QrManager.close();
  });

  // 二维码过期后点击刷新
  document.getElementById('qrRefreshBtn').addEventListener('click', function() {
    QrManager.refreshCount = 0;
    QrManager.loadQrCode(appid, redirectUri);
  });

  // 返回密码登录
  document.getElementById('qrSwitchPwdLogin').addEventListener('click', function() {
    QrManager.close();
  });
});
```

#### 3.1.5 后端生成扫码 session 与状态轮询（新增 API）

为了更好地追踪扫码状态，后端创建扫码 session 并支持前端轮询状态：

```python
import hmac
import hashlib
from login import config

# 用于签名 QR session 数据的密钥（来自 config，可在 .env 中配置）
QR_SIGN_SECRET = config.WECHAT_QR_SIGN_SECRET or secrets.token_hex(32)

def _sign_qr_data(session_id: str, state: str, device_fp: str, timestamp: int) -> str:
    """对 QR session 数据进行 HMAC-SHA256 签名，防止篡改"""
    message = f"{session_id}|{state}|{device_fp}|{timestamp}"
    return hmac.new(
        QR_SIGN_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:16]


@router.post("/wechat/qr-session", summary="创建微信扫码 session")
@limiter.limit("30/minute")
def create_qr_session(
    request: Request,
    db = Depends(get_db),
):
    """
    生成扫码 session，绑定设备指纹和 IP，用于：
    1. 追踪扫码状态（等待扫码/已扫码/已确认）
    2. 风控检测（异常设备/IP 登录）
    3. 回调时校验 state 和设备一致性
    4. 前端轮询获取实时状态
    """
    body = request.json()
    device_fp = body.get("device_fp", "")
    ip = request.client.host

    if not device_fp:
        return ApiResponse(code=400, message="缺少设备指纹")

    # 生成随机 session_id 和 state
    session_id = secrets.token_hex(16)
    state = f"wx_{secrets.token_hex(8)}_{device_fp}"
    now_ts = int(time.time())

    # 对 session 数据进行签名
    signature = _sign_qr_data(session_id, state, device_fp, now_ts)

    # 存储到 Redis（推荐）或内存字典
    # key: f"wechat_qr_session:{session_id}"
    # value: {
    #   "state": state, "device_fp": device_fp,
    #   "ip": ip, "created_at": now_ts,
    #   "signature": signature,
    #   "status": "pending",       # pending | scanned | confirmed | expired
    #   "scanned_at": None,
    #   "confirmed_at": None,
    # }
    # expire: 180 秒（与二维码有效期一致）

    return ApiResponse(code=0, data={
        "session_id": session_id,
        "state": state,
        "signature": signature,
        "expires_in": 120,
    })


@router.get("/wechat/qr-session/{session_id}/status", summary="轮询扫码状态")
@limiter.limit("60/minute")
def poll_qr_status(
    session_id: str,
    device_fp: str = Query(...),
    signature: str = Query(...),
    db = Depends(get_db),
):
    """
    前端轮询接口，获取当前扫码状态。
    返回状态：pending → scanned → confirmed → expired
    用于前端在 WxLogin 回调不可靠时作为降级方案。
    """
    # 从 Redis/内存中获取 session
    session_data = get_qr_session(session_id)  # 伪代码
    if not session_data:
        return ApiResponse(code=404, message="session 不存在")

    # 校验签名
    expected_sig = _sign_qr_data(
        session_id, session_data["state"],
        device_fp, session_data["created_at"]
    )
    if not hmac.compare_digest(expected_sig, signature):
        return ApiResponse(code=403, message="签名校验失败")

    # 校验设备指纹
    if session_data["device_fp"] != device_fp:
        return ApiResponse(code=403, message="设备指纹不匹配")

    # 校验是否过期
    if time.time() - session_data["created_at"] > 180:
        return ApiResponse(code=200, data={"status": "expired"})

    return ApiResponse(code=0, data={
        "status": session_data["status"],  # pending | scanned | confirmed
    })
```

**状态轮询策略**：前端在二维码展示后启动轮询（间隔 2 秒），当轮询到 `scanned` 或 `confirmed` 状态时更新 UI。轮询作为 WebSocket 和 WxLogin 回调的降级方案，三者同时工作时以 WebSocket > WxLogin 回调 > 轮询的优先级处理。
 
 **二维码数据签名**：所有 QR session 请求携带 HMAC 签名，防止以下攻击：
 - 篡改 session_id 劫持其他用户的扫码 session
 - 重放攻击（签名包含时间戳）
 - 伪造设备指纹绕过风控
 
 #### 3.1.6 增强 QrManager：添加状态轮询与 WebSocket 支持
 
 在 JS 的 QrManager 中增加后端状态轮询和可选的 WebSocket 实时推送机制：
 
 ```javascript
 // ==============================================================
 // 增强：轮询管理器（用于获取后端扫码状态）
 // ==============================================================
 var PollManager = {
   timer: null,
   sessionId: '',
   deviceFp: '',
   signature: '',
   pollInterval: 2000,  // 2 秒轮询间隔
   maxRetries: 90,      // 最多轮询 3 分钟（2s × 90 = 180s）
   retryCount: 0,
   lastStatus: '',
 
   start: function(sessionId, deviceFp, signature, onStatusChange) {
     this.sessionId = sessionId;
     this.deviceFp = deviceFp;
     this.signature = signature;
     this.retryCount = 0;
     this.lastStatus = 'pending';
 
     var self = this;
     function poll() {
       if (self.retryCount >= self.maxRetries) {
         self.stop();
         onStatusChange('expired');
         return;
       }
       self.retryCount++;
 
       fetch('/api/wechat/qr-session/' + self.sessionId + '/status' +
             '?device_fp=' + encodeURIComponent(self.deviceFp) +
             '&signature=' + encodeURIComponent(self.signature))
         .then(function(r) { return r.json(); })
         .then(function(data) {
           if (data.code === 0 && data.data) {
             var newStatus = data.data.status;
             if (newStatus !== self.lastStatus) {
               self.lastStatus = newStatus;
               onStatusChange(newStatus);
             }
             // 已确认则停止轮询
             if (newStatus === 'confirmed') { self.stop(); }
           }
           // 继续轮询（除非已停止）
           if (self.timer) {
             self.timer = setTimeout(poll, self.pollInterval);
           }
         })
         .catch(function() {
           // 网络错误：指数退避重试（最多 30 秒）
           var backoff = Math.min(5000, self.pollInterval * Math.pow(1.5,
             Math.floor(self.retryCount / 5)));
           if (self.timer) {
             self.timer = setTimeout(poll, backoff);
           }
         });
     }
     // 延迟 3 秒后启动轮询（给 WxLogin 组件优先通过回调方式通知）
     this.timer = setTimeout(poll, 3000);
   },
 
   stop: function() {
     if (this.timer) {
       clearTimeout(this.timer);
       this.timer = null;
     }
   }
 };
 
 // ==============================================================
 // 增强：WebSocket 状态推送（高级方案，用于生产环境）
 // ==============================================================
 var WsStatusManager = {
   ws: null,
   reconnectTimer: null,
   reconnectAttempts: 0,
   maxReconnect: 5,
 
   connect: function(sessionId, onStatusChange) {
     var self = this;
     var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
     var wsUrl = protocol + '//' + window.location.host +
                 '/ws/wechat/qr-status/' + sessionId;
 
     try {
       this.ws = new WebSocket(wsUrl);
 
       this.ws.onmessage = function(event) {
         try {
           var data = JSON.parse(event.data);
           if (data.status) {
             onStatusChange(data.status);
             if (data.status === 'confirmed') { self.close(); }
           }
         } catch (e) { /* 忽略解析错误 */ }
       };
 
       this.ws.onclose = function() {
         if (self.reconnectAttempts < self.maxReconnect) {
           self.reconnectAttempts++;
           self.reconnectTimer = setTimeout(function() {
             self.connect(sessionId, onStatusChange);
           }, Math.min(30000, 1000 * Math.pow(2, self.reconnectAttempts)));
         }
       };
 
       this.ws.onerror = function() {
         // WebSocket 连接失败，降级到轮询（PollManager 已启动）
       };
     } catch (e) {
       // WebSocket 不可用，依赖轮询
     }
   },
 
   close: function() {
     if (this.ws) { this.ws.close(); this.ws = null; }
     if (this.reconnectTimer) {
       clearTimeout(this.reconnectTimer);
       this.reconnectTimer = null;
     }
   }
 };
 ```
 
 **WebSocket 连接成功后，状态变化路径**（比轮询更实时）：
 ```
 扫码成功 → 服务端通过 WebSocket push {"status": "scanned"}
 确认登录 → 服务端通过 WebSocket push {"status": "confirmed"}
 二维码过期 → 服务端通过 WebSocket push {"status": "expired"}
 ```
 
 #### 3.1.7 二维码渲染失败兜底方案
 
 针对部分浏览器（如微信内置浏览器、老旧浏览器）无法正常渲染 WxLogin 生成的 iframe 二维码的情况，提供兜底方案：
 
 **方案一：短链接跳转（推荐）**
 ```javascript
 // 当 WxLogin 创建失败时，降级为短链接跳转
 // 用户点击后跳转到微信授权页，手动授权
 function fallbackToManualAuth(appid, redirectUri, state) {
   var authUrl = 'https://open.weixin.qq.com/connect/qrconnect' +
     '?appid=' + encodeURIComponent(appid) +
     '&redirect_uri=' + encodeURIComponent(redirectUri) +
     '&response_type=code' +
     '&scope=snsapi_login' +
     '&state=' + encodeURIComponent(state) +
     '#wechat_redirect';
 
   // 展示兜底按钮
   var fallbackEl = document.createElement('div');
   fallbackEl.style.marginTop = '16px';
   fallbackEl.innerHTML =
     '<p style="color:#718096; font-size:12px; margin-bottom:8px;">二维码加载失败？</p>' +
     '<a href="' + authUrl + '" target="_blank" style="' +
     'display:inline-block; height:36px; line-height:36px; padding:0 20px; ' +
     'border:1px solid #07c160; border-radius:8px; color:#07c160; ' +
     'font-size:13px; text-decoration:none; transition:background 0.2s;">' +
     '点击跳转微信授权</a>';
   document.getElementById('wechat_qrcode_container').appendChild(fallbackEl);
 }
 ```
 
 **方案二：iframe 加载超时检测**
 ```javascript
 // WxLogin 组件加载检测，5 秒后检查 iframe 是否正确渲染
 function detectQrReady(wxLoginObj, onReady, onFallback) {
   var checkCount = 0;
   var maxChecks = 10;
   var checkTimer = setInterval(function() {
     checkCount++;
     var container = document.getElementById('wechat_qrcode_container');
     var iframe = container && container.querySelector('iframe');
     if (iframe && iframe.style.display !== 'none') {
       clearInterval(checkTimer);
       onReady();
     } else if (checkCount >= maxChecks) {
       clearInterval(checkTimer);
       onFallback();
     }
   }, 500);
 }
 ```
 
 ### 3.2 步骤二：微信回调处理（优化版）

用户扫码确认后，微信将重定向到 `redirect_uri`，携带 `code` 和 `state` 参数。

#### 3.2.1 回调端点设计（含安全增强）

在 `login/wechat_router.py` 中新增回调路由：

```python
import logging
from datetime import datetime, timezone
from login.wechat_service import WeChatService

logger = logging.getLogger(__name__)

wechat_service = WeChatService()


@router.get("/wechat/callback", summary="微信登录回调")
@limiter.limit("30/minute")
def wechat_callback(
    request: Request,
    response: Response,
    code: str = Query(...),
    state: str = Query(None),
    db = Depends(get_db),
):
    """
    微信扫码登录回调处理（优化版）。

    安全校验链：
    Step 1: 校验 state 格式（防止 CSRF 攻击）
    Step 1.5: 校验 state 与 QR session 的一致性签名
    Step 2: IP 级滑动窗口速率限制
    Step 3: 用 code 换取 access_token + openid + unionid
    Step 4: 获取微信用户基本信息
    Step 5: openid 级滑动窗口速率限制
    Step 5.5: 风控评分（基于设备指纹、IP 属地、历史行为）
    Step 6: 判断用户是否已绑定
       - 已绑定：更新 wechat_info，设置 Cookie，登录成功
       - 未绑定：生成 bind_token，跳转绑定页
    Step 7: 记录审计日志
    """
    client_ip = request.client.host

    # Step 1: 校验 state 格式
    if not state or not state.startswith("wx_"):
        logger.warning(f"[WeChat] 无效的 state 参数: ip={client_ip}")
        return RedirectResponse(url="/login?error=invalid_request", status_code=302)

    # Step 1.5: state 解析与 QR session 一致性校验
    # state 格式: "wx_{random}_{device_fp}"，从中提取设备指纹
    state_parts = state.split("_")
    if len(state_parts) < 3:
        logger.warning(f"[WeChat] state 格式异常: ip={client_ip}")
        return RedirectResponse(url="/login?error=invalid_request", status_code=302)

    request_device_fp = state_parts[-1]

    logger.info(f"[WeChat] 收到回调: ip={client_ip}, state_prefix={state[:12]}")

    # Step 2: IP 级滑动窗口速率限制
    # 使用固定窗口 + 滑动补偿实现更精确的限流
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM login_audit_log "
        "WHERE ip = %s AND created_at > NOW() - INTERVAL '1 minute' "
        "AND status IN ('failed', 'rate_limited')",
        (client_ip,)
    )
    ip_1min_failures = cur.fetchone()[0]
    if ip_1min_failures >= 3:
        logger.warning(f"[WeChat] IP 1 分钟内失败 {ip_1min_failures} 次: ip={client_ip}")
        _log_login_audit(db, openid="", user_id=None,
                         ip=client_ip, status="rate_limited", method="wechat_scan",
                         reason=f"IP 1min rate limit: {ip_1min_failures}")
        db.commit()
        cur.close()
        return RedirectResponse(url="/login?error=rate_limited", status_code=302)

    cur.execute(
        "SELECT COUNT(*) FROM login_audit_log "
        "WHERE ip = %s AND created_at > NOW() - INTERVAL '1 hour' "
        "AND status IN ('failed', 'rate_limited')",
        (client_ip,)
    )
    ip_1h_failures = cur.fetchone()[0]
    cur.close()
    if ip_1h_failures >= 20:
        logger.warning(f"[WeChat] IP 1 小时内失败 {ip_1h_failures} 次: ip={client_ip}")
        return RedirectResponse(url="/login?error=rate_limited", status_code=302)

    # Step 3: 用 code 换取 access_token
    token_data = wechat_service.exchange_code_for_token(code)
    if not token_data:
        logger.warning(f"[WeChat] 换取 token 失败: ip={client_ip}, code={code[:6]}...")
        _log_login_audit(db, openid="", user_id=None,
                         ip=client_ip, status="failed", method="wechat_scan",
                         reason="exchange_code_failed")
        db.commit()
        return RedirectResponse(
            url="/login?error=auth_failed",
            status_code=302
        )

    openid = token_data["openid"]
    unionid = token_data.get("unionid", "")
    logger.info(f"[WeChat] 换取 token 成功: openid={openid[:8]}..., unionid_provided={bool(unionid)}")

    # Step 4: 获取微信用户信息
    user_info = wechat_service.get_user_info(
        token_data["access_token"],
        openid
    )

    # Step 5: openid 级滑动窗口速率限制
    # 使用滑动窗口计数替代固定窗口，更精确
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM login_audit_log "
        "WHERE openid = %s AND created_at > NOW() - INTERVAL '5 minutes' "
        "AND status IN ('failed', 'rate_limited')",
        (openid,)
    )
    recent_failures = cur.fetchone()[0]
    cur.close()

    if recent_failures >= 5:
        logger.warning(
            f"[WeChat] openid 短时高频失败: openid={openid[:8]}..., "
            f"failures={recent_failures}, ip={client_ip}"
        )
        _log_login_audit(db, openid=openid, user_id=None,
                         ip=client_ip, status="rate_limited", method="wechat_scan",
                         reason=f"openid rate limit: {recent_failures}")
        db.commit()
        return RedirectResponse(
            url="/login?error=rate_limited",
            status_code=302
        )

    # Step 5.5: 风控评分（0-100，越高越可疑）
    risk_score = 0
    risk_factors = []

    # 5.5.1: 设备指纹异常
    if request_device_fp and len(request_device_fp) < 8:
        risk_score += 20
        risk_factors.append("device_fp_too_short")

    # 5.5.2: 短时间内同一 openid 多 IP 出现
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT ip) FROM login_audit_log "
        "WHERE openid = %s AND created_at > NOW() - INTERVAL '30 minutes'"
        "AND status = 'success'",
        (openid,)
    )
    distinct_ips = cur.fetchone()[0]
    cur.close()
    if distinct_ips >= 3:
        risk_score += 15
        risk_factors.append("multi_ip_in_30min")

    # 5.5.3: 高频扫码行为（同一 IP 短时大量不同 openid）
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(DISTINCT openid) FROM login_audit_log "
        "WHERE ip = %s AND created_at > NOW() - INTERVAL '5 minutes' "
        "AND method = 'wechat_scan'",
        (client_ip,)
    )
    distinct_openids = cur.fetchone()[0]
    cur.close()
    if distinct_openids >= 10:
        risk_score += 25
        risk_factors.append("mass_scan_from_single_ip")

    # 风险阈值判断
    if risk_score >= 40:
        logger.warning(
            f"[WeChat] 风控拦截: openid={openid[:8]}..., score={risk_score}, "
            f"factors={risk_factors}, ip={client_ip}"
        )
        _log_login_audit(db, openid=openid, user_id=None,
                         ip=client_ip, status="rate_limited", method="wechat_scan",
                         reason=f"risk_score_{risk_score}:{','.join(risk_factors)}")
        db.commit()
        return RedirectResponse(url="/login?error=risk_blocked", status_code=302)

    # Step 6: 判断用户是否已绑定
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM users WHERE wechat_info->>'openid' = %s",
        (openid,)
    )
    user = cur.fetchone()
    cur.close()

    if user:
        # 已绑定 → 更新 wechat_info 并直接登录
        try:
            existing_info = user["wechat_info"] or {}
        except (TypeError, KeyError):
            existing_info = {}

        updated_wechat_info = {**existing_info, **{
            "nickname": user_info.get("nickname", existing_info.get("nickname", "")),
            "headimgurl": user_info.get("headimgurl", existing_info.get("headimgurl", "")),
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "token_expires_at": int(time.time()) + token_data["expires_in"],
            "last_login_at": datetime.now(timezone.utc).isoformat(),
        }}

        cur = db.cursor()
        cur.execute(
            "UPDATE users SET wechat_info = %s, last_login_at = NOW(), "
            "updated_at = NOW() WHERE id = %s",
            (psycopg2.extras.Json(updated_wechat_info), user["id"])
        )
        db.commit()
        cur.close()

        # 设置登录 Cookie
        set_auth_cookie(
            response,
            {"sub": str(user["id"]), "username": user["username"]}
        )

        # 记录审计日志
        _log_login_audit(db, openid=openid, user_id=user["id"],
                         ip=client_ip, status="success", method="wechat_scan")

        logger.info(f"[WeChat] 登录成功: user_id={user['id']}, openid={openid[:8]}...")
        return RedirectResponse(url="/", status_code=302)

    else:
        # 未绑定 → 生成绑定临时令牌，跳转绑定页
        bind_token = wechat_service.create_bind_token(
            openid=openid,
            unionid=unionid,
            user_info=user_info,
            token_data=token_data,
        )
        redirect_url = f"/bind-wechat?bind_token={bind_token}"

        # 记录审计日志
        _log_login_audit(db, openid=openid, user_id=None,
                         ip=client_ip, status="need_bind", method="wechat_scan")

        logger.info(f"[WeChat] 未绑定，跳转绑定页: openid={openid[:8]}...")
        return RedirectResponse(url=redirect_url, status_code=302)


def _log_login_audit(
    db,
    openid: str,
    user_id: Optional[int],
    ip: str,
    status: str,      # "success" | "failed" | "need_bind" | "rate_limited"
    method: str,      # "wechat_scan" | "wechat_bind"
    reason: str = "",
):
    """
    记录登录审计日志到 login_audit_log 表。
    用于风控分析、异常登录检测和问题排查。
    """
    try:
        cur = db.cursor()
        cur.execute(
            "INSERT INTO login_audit_log "
            "(openid, user_id, ip, status, method, reason, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, NOW())",
            (openid, user_id, ip, status, method, reason)
        )
        db.commit()
        cur.close()
    except Exception as e:
        # 审计日志写失败不影响主流程
        logger.error(f"[WeChat] 审计日志写入失败: {e}")
```

> **审计日志表已在 2.3 节 `init_db()` 中统一创建**，此处不再重复。

### 3.3 步骤三：首次微信登录 → 手机号绑定

#### 3.3.1 绑定业务规则

| 规则编号 | 规则内容 |
|---|---|
| **R1** | 绑定的手机号**必须**是已在本系统注册的用户手机号 |
| **R2** | 不允许使用未注册的手机号创建新用户来绑定微信 |
| **R3** | 绑定操作必须经过短信验证码验证，确保手机号持有者本人操作 |
| **R4** | 一个微信账号（openid）只能绑定一个系统用户 |
| **R5** | 一个系统用户可以绑定多个微信账号（通过 wechat_info 存储） |
| **R6** | 绑定请求使用 bind_token（10分钟有效 JWT）防止伪造和重放攻击 |

#### 3.3.2 绑定流程概述

```
微信回调（未绑定）
    → 后端生成 bind_token（10分钟有效，暂存微信用户信息）
    → 重定向到 /bind-wechat?bind_token=xxx
    → 前端展示绑定页面（含微信头像/昵称）

    → 用户输入手机号
    → 前端校验手机号格式（11位中国大陆手机号）
    → 用户点击"获取验证码"
    → 前端请求 /api/wechat/check-phone 验证手机号是否已注册
        ┌─ 手机号未注册 → 阻断流程，显示错误提示：
        │   "请使用你在本网站注册的手机号来绑定该微信号"
        │   → 用户可重新输入其他手机号
        │   → 前端清空手机号输入框，让用户重新输入
        └─ 手机号已注册 → 后端发送短信验证码到该手机号

    → 用户输入收到的6位验证码
    → 用户点击"完成绑定"
    → 后端验证 bind_token + 验证码 + 手机号注册状态
    → 绑定成功 → 自动设置登录 Cookie → 跳转首页
```

#### 3.3.3 绑定前端交互流程（含状态机）

```
页面初始状态：
  ┌─────────────────────────────────────────┐
  │  微信头像 + 昵称显示                     │
  │  "首次使用微信登录，请绑定您的手机号"     │
  │  手机号输入框 [  ]                        │
  │  [获取验证码] 按钮（disabled）            │
  │  验证码输入框 [  ]                        │
  │  [完成绑定] 按钮                          │
  │  [返回登录] 链接                         │
  └─────────────────────────────────────────┘

用户输入手机号 → 触发实时格式校验（/^1[3-9]\d{9}$/）
  └─ 格式正确 → [获取验证码] 按钮变为可用
  └─ 格式错误 → [获取验证码] 按钮保持 disabled

用户点击 [获取验证码]：
  → 前端先调用 /api/wechat/check-phone?phone=xxx 校验手机号是否注册
  → 返回结果：
      ├─ code:404（未注册）→ 显示红色错误条：
      │   "请使用你在本网站注册的手机号来绑定该微信号"
      │   → 清空手机号输入框，[获取验证码] 恢复为可用状态
      │   → 用户可重新输入手机号再次尝试
      └─ code:0（已注册）→ 发送短信验证码 → 启动60秒倒计时

用户输入验证码 → 点击 [完成绑定]：
  → 调用 /api/wechat/bind
  → 返回结果：
      ├─ code:0 → 成功，跳转首页
      ├─ code:404 → "该手机号未在本系统注册" → 清空手机号，用户重输
      ├─ code:400 → 验证码过期/错误 → 验证码输入框清空，用户重输
      └─ code:409 → 微信已被其他账号绑定 → 提示用户，2秒后跳回登录页
```

#### 3.3.4 手机号预校验 API（新增）

在发送验证码之前，前端需先校验手机号是否已注册：

```python
@router.get("/wechat/check-phone", response_model=ApiResponse, summary="校验手机号是否已注册")
def wechat_check_phone(
    phone: str = Query(..., description="待校验的手机号"),
    db = Depends(get_db),
):
    """
    校验手机号是否已在系统中注册。
    用于微信绑定流程中，发送验证码前的前置校验。
    """
    if not re.match(r"^1[3-9]\d{9}$", phone):
        return ApiResponse(code=400, message="手机号格式不正确")

    cur = db.cursor()
    cur.execute("SELECT id FROM users WHERE phone = %s", (phone,))
    user = cur.fetchone()
    cur.close()

    if user:
        return ApiResponse(code=0, message="手机号已注册", data={"registered": True})
    else:
        return ApiResponse(
            code=404,
            message="请使用你在本网站注册的手机号来绑定该微信号",
            data={"registered": False}
        )
```

**特别注意**：此 API 的 `code=404` 错误消息**必须**与绑定 API 中未注册手机号的错误消息保持一致，均为 `"请使用你在本网站注册的手机号来绑定该微信号"`，以确保前后端提示统一。

#### 3.3.5 绑定临时令牌生成

```python
@staticmethod
def create_bind_token(openid: str, unionid: str, user_info: dict, token_data: dict) -> str:
    """
    生成微信绑定临时令牌（10分钟有效）
    将微信信息暂存，供绑定页面使用
    """
    payload = {
        "sub": "wechat_bind",
        "openid": openid,
        "unionid": unionid,
        "nickname": user_info.get("nickname", ""),
        "headimgurl": user_info.get("headimgurl", ""),
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_in": token_data["expires_in"],
        "purpose": "wechat_bind",
    }
    # 复用现有 JWT 创建逻辑，设置 10 分钟过期
    return create_access_token(
        data=payload,
        expires_delta=timedelta(minutes=10)
    )
```

#### 3.3.6 绑定页面路由

在 `main.py` 中新增绑定页面路由：

```python
@app.get("/bind-wechat", response_class=HTMLResponse, include_in_schema=False)
async def bind_wechat_page(bind_token: str = Query(...)):
    """微信账号绑定页面"""
    # 校验 bind_token 是否有效
    try:
        payload = jwt.decode(bind_token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        if payload.get("purpose") != "wechat_bind":
            return HTMLResponse(content="无效的绑定令牌", status_code=400)
    except JWTError:
        return HTMLResponse(content="绑定令牌已过期，请重新扫码", status_code=400)

    with open("templates/bind-wechat.html", "r", encoding="utf-8") as f:
        html = f.read()
    # 将 bind_token 注入到页面中
    html = html.replace("{{BIND_TOKEN}}", bind_token)
    html = html.replace("{{WECHAT_NICKNAME}}", payload.get("nickname", "微信用户"))
    html = html.replace("{{WECHAT_AVATAR}}", payload.get("headimgurl", ""))
    return HTMLResponse(content=html)
```

#### 3.3.7 绑定页面前端设计（`templates/bind-wechat.html`）

**页面布局说明（从上到下）：**

| 区域 | 元素 | 说明 |
|---|---|---|
| 顶部 | 微信头像 | 圆形，64x64px，bootstrap 风格圆角边框，加载失败显示默认图标 |
| 顶部 | 微信昵称 | 16px 加粗字体，居中显示 |
| 标题 | "绑定手机号" | 20px 字体 |
| 提示语 | "首次使用微信登录，请绑定您的手机号" | 14px 灰色字体 |
| 消息条 | messageBox | 红色（error）/ 绿色（success）提示条，3秒自动消失 |
| 表单区 | 手机号输入框 | type="tel"，maxlength=11，placeholder="请输入手机号" |
| 表单区 | 获取验证码按钮 | 边框样式，点击后校验注册状态，成功后启动60s倒计时 |
| 表单区 | 验证码输入框 | type="text"，maxlength=6，inputmode="numeric" |
| 表单区 | 完成绑定按钮 | 主色调填充按钮，提交时显示"绑定中..." |
| 底部 | 返回登录链接 | 居中对齐，跳转 /login |

**完整 HTML + JS 代码（含防抖、渐进式增强）：**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>绑定手机号</title>
  <style>
    /* ===== Reset & Base ===== */
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                   "Microsoft YaHei", "Helvetica Neue", sans-serif;
      min-height: 100vh;
      background: #f5f5f5;
      background-image: radial-gradient(circle, #ededed 1px, transparent 1px);
      background-size: 20px 20px;
      display: flex;
      align-items: center; justify-content: center;
      padding: 20px;
    }

    /* ===== Card ===== */
    .card {
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
      padding: 40px 36px;
      width: 100%; max-width: 420px;
    }

    /* ===== WeChat Profile ===== */
    .wechat-avatar {
      width: 64px; height: 64px;
      border-radius: 50%; object-fit: cover;
      border: 3px solid #667eea;
      display: block; margin: 0 auto;
      transition: opacity 0.3s;
    }
    .wechat-nickname {
      text-align: center;
      font-size: 16px; font-weight: 600;
      color: #2d3748; margin-top: 8px;
    }

    /* ===== Typography ===== */
    .page-title {
      text-align: center;
      font-size: 20px; font-weight: 700;
      color: #2d3748; margin: 20px 0 8px;
    }
    .bind-hint {
      text-align: center;
      font-size: 14px; color: #718096;
      margin-bottom: 24px;
      line-height: 1.5;
    }

    /* ===== Toast 通知（与 3.1 节统一风格）===== */
    .toast-bind {
      position: fixed; top: 20px; left: 50%;
      transform: translateX(-50%) translateY(-20px);
      z-index: 9999;
      padding: 12px 24px; border-radius: 10px;
      font-size: 14px; font-weight: 500;
      box-shadow: 0 8px 24px rgba(0,0,0,0.15);
      opacity: 0; pointer-events: none;
      transition: opacity 0.3s, transform 0.3s;
      max-width: 90vw;
    }
    .toast-bind.show { opacity: 1; transform: translateX(-50%) translateY(0); }
    .toast-bind.success { background: #c6f6d5; color: #276749; }
    .toast-bind.error { background: #fed7d7; color: #9b2c2c; }
    .toast-bind.info { background: #bee3f8; color: #2b6cb0; }

    /* ===== Form ===== */
    .form-group { margin-bottom: 18px; position: relative; }
    .form-group label {
      display: block; font-size: 14px;
      color: #4a5568; margin-bottom: 6px; font-weight: 500;
    }
    .input-wrapper { position: relative; }
    .input-wrapper input {
      width: 100%; height: 44px; padding: 0 14px;
      border: 1.5px solid #e2e8f0; border-radius: 10px;
      font-size: 15px; color: #2d3748; outline: none;
      transition: border-color 0.25s ease, box-shadow 0.25s ease;
      background: #f7fafc;
    }
    .input-wrapper input:focus {
      border-color: #667eea;
      box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15);
      background: #fff;
    }
    .input-wrapper input.error {
      border-color: #fc8181;
      box-shadow: 0 0 0 3px rgba(252, 129, 129, 0.15);
    }
    .input-wrapper input:disabled { background: #edf2f7; cursor: not-allowed; }

    /* 输入框加载状态（右侧加载圈） */
    .input-loading {
      position: absolute; right: 12px; top: 50%;
      transform: translateY(-50%);
      width: 16px; height: 16px;
      border: 2px solid #e2e8f0; border-top-color: #667eea;
      border-radius: 50%; animation: spin 0.6s linear infinite;
      display: none;
    }
    .input-loading.active { display: block; }
    @keyframes spin { to { transform: translateY(-50%) rotate(360deg); } }

    /* ===== Code Row ===== */
    .code-row { display: flex; gap: 10px; }
    .code-row .input-wrapper { flex: 1; }
    .btn-code {
      height: 44px; padding: 0 16px; min-width: 110px;
      border: 1.5px solid #667eea; border-radius: 10px;
      background: #fff; color: #667eea;
      font-size: 13px; font-weight: 600; cursor: pointer;
      white-space: nowrap;
      transition: background 0.2s, color 0.2s, opacity 0.2s;
    }
    .btn-code:hover:not(:disabled) { background: #667eea; color: #fff; }
    .btn-code:disabled {
      border-color: #a0aec0; color: #a0aec0;
      cursor: not-allowed; opacity: 0.7;
    }

    /* ===== Submit Button ===== */
    .btn-submit {
      width: 100%; height: 46px; border: none; border-radius: 10px;
      background: #667eea; color: #fff; font-size: 16px; font-weight: 600;
      cursor: pointer; margin-top: 8px;
      transition: background 0.25s, opacity 0.25s;
      display: flex; align-items: center; justify-content: center; gap: 8px;
    }
    .btn-submit:hover:not(:disabled) { background: #5a67d8; }
    .btn-submit:disabled { background: #a0aec0; cursor: not-allowed; opacity: 0.8; }

    /* 提交按钮加载旋转圈 */
    .btn-spinner {
      width: 18px; height: 18px;
      border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
      border-radius: 50%; animation: spin 0.6s linear infinite;
      display: none;
    }
    .btn-spinner.active { display: inline-block; }

    /* ===== Footer ===== */
    .footer-links { display: flex; justify-content: center; margin-top: 20px; font-size: 14px; }
    .footer-links a { color: #667eea; text-decoration: none; font-weight: 500; }
    .footer-links a:hover { color: #5a67d8; }

    /* ===== Responsive ===== */
    @media (max-width: 480px) { .card { padding: 28px 20px; border-radius: 12px; } }
  </style>
</head>
<body>
  <!-- Toast 通知容器 -->
  <div id="toastBind" class="toast-bind"></div>

  <div class="card">
    <!-- 微信用户信息展示区 -->
    <img id="wechatAvatar" class="wechat-avatar"
         src="{{WECHAT_AVATAR}}" alt="微信头像"
         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><circle cx=%2250%22 cy=%2250%22 r=%2245%22 fill=%22%23e2e8f0%22/><text x=%2250%22 y=%2255%22 text-anchor=%22middle%22 font-size=%2230%22 fill=%22%23a0aec0%22>微</text></svg>'">
    <div class="wechat-nickname" id="wechatNickname">{{WECHAT_NICKNAME}}</div>

    <div class="page-title">绑定手机号</div>
    <p class="bind-hint">首次使用微信登录，请绑定您的手机号</p>

    <form id="bindForm" novalidate>
      <input type="hidden" id="bindToken" value="{{BIND_TOKEN}}">

      <!-- 手机号 -->
      <div class="form-group">
        <label for="bindPhone">手机号</label>
        <div class="input-wrapper">
          <input type="tel" id="bindPhone" placeholder="请输入手机号"
                 maxlength="11" autocomplete="tel" aria-describedby="phoneHint">
          <div id="phoneLoading" class="input-loading"></div>
        </div>
      </div>

      <!-- 验证码 -->
      <div class="form-group">
        <label for="bindCode">验证码</label>
        <div class="code-row">
          <div class="input-wrapper">
            <input type="text" id="bindCode" placeholder="请输入6位验证码"
                   maxlength="6" inputmode="numeric" disabled
                   aria-describedby="codeHint">
          </div>
          <button type="button" id="btnSendBindCode" class="btn-code" disabled>
            获取验证码
          </button>
        </div>
      </div>

      <button type="submit" id="btnBind" class="btn-submit">
        <span class="btn-spinner" id="btnBindSpinner"></span>
        <span id="btnBindText">完成绑定</span>
      </button>
    </form>

    <div class="footer-links">
      <a href="/login" id="backToLogin">返回登录</a>
    </div>
  </div>

  <script>
  // ==============================================================
  // 工具函数
  // ==============================================================

  /** Toast 通知 */
  var Toast = (function() {
    var el = document.getElementById('toastBind');
    var timer = null;
    function show(text, type) {
      el.textContent = text;
      el.className = 'toast-bind ' + type + ' show';
      clearTimeout(timer);
      timer = setTimeout(function() { el.className = 'toast-bind'; }, 4000);
    }
    return {
      success: function(t) { show(t, 'success'); },
      error:   function(t) { show(t, 'error'); },
      info:    function(t) { show(t, 'info'); }
    };
  })();

  /** 防抖：一定时间内仅执行最后一次调用 */
  function debounce(fn, delay) {
    var timer = null;
    return function() {
      var self = this, args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function() { fn.apply(self, args); }, delay);
    };
  }

  /** 节流：一定时间内仅执行第一次调用 */
  function throttle(fn, interval) {
    var last = 0;
    return function() {
      var now = Date.now();
      if (now - last >= interval) {
        last = now;
        fn.apply(this, arguments);
      }
    };
  }

  /** 设置按钮加载态 */
  function setButtonLoading(btn, loading) {
    if (loading) {
      btn.disabled = true;
      btn.querySelector('.btn-spinner').classList.add('active');
      btn.querySelector('#btnBindText').textContent = '绑定中...';
    } else {
      btn.disabled = false;
      btn.querySelector('.btn-spinner').classList.remove('active');
      btn.querySelector('#btnBindText').textContent = '完成绑定';
    }
  }

  // ==============================================================
  // 主逻辑
  // ==============================================================
  document.addEventListener('DOMContentLoaded', function() {
    var bindToken   = document.getElementById('bindToken').value;
    var bindPhone   = document.getElementById('bindPhone');
    var bindCode    = document.getElementById('bindCode');
    var btnSendCode = document.getElementById('btnSendBindCode');
    var btnBind     = document.getElementById('btnBind');
    var phoneLoading = document.getElementById('phoneLoading');

    var countdown = 0;
    var countdownTimer = null;
    var phoneVerified = false;

    // ---- 手机号输入实时校验（防抖：300ms） ----
    bindPhone.addEventListener('input', debounce(function() {
      var phone = this.value.trim();
      phoneVerified = false;
      bindCode.disabled = true;
      btnSendCode.disabled = true;

      if (/^1[3-9]\d{9}$/.test(phone)) {
        btnSendCode.disabled = false;
        this.classList.remove('error');
      } else {
        if (phone.length >= 11) this.classList.add('error');
      }
    }, 300));

    // ---- 发送验证码（节流：3 秒内不可重复触发） ----
    var sendCodeThrottled = throttle(function() {
      var phone = bindPhone.value.trim();

      // 格式校验
      if (!/^1[3-9]\d{9}$/.test(phone)) {
        Toast.error('请输入正确的手机号');
        bindPhone.classList.add('error');
        btnSendCode.disabled = false;
        return;
      }

      btnSendCode.disabled = true;
      btnSendCode.textContent = '校验中...';
      phoneLoading.classList.add('active');

      // Step 1: 校验手机号是否已注册
      fetch('/api/wechat/check-phone?phone=' + encodeURIComponent(phone))
        .then(function(res) { return res.json(); })
        .then(function(data) {
          phoneLoading.classList.remove('active');

          if (data.code === 0 && data.data && data.data.registered === true) {
            // ✅ 已注册 → 发送验证码
            btnSendCode.textContent = '发送中...';
            bindCode.disabled = false;
            bindCode.focus();

            return fetch('/api/send-code', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ phone: phone })
            }).then(function(r) { return r.json(); });
          } else {
            // ❌ 未注册 → 阻断
            Toast.error('请使用你在本网站注册的手机号来绑定该微信号');
            bindPhone.value = '';
            bindPhone.focus();
            bindCode.disabled = true;
            bindCode.value = '';
            phoneVerified = false;
            btnSendCode.disabled = false;
            btnSendCode.textContent = '获取验证码';
            return Promise.reject('phone_not_registered');
          }
        })
        .then(function(data) {
          if (data && data.code === 0) {
            Toast.success('验证码已发送');
            phoneVerified = true;
            startCountdown();
          } else if (data) {
            Toast.error(data.message || '发送失败');
            bindCode.disabled = true;
            btnSendCode.disabled = false;
            btnSendCode.textContent = '获取验证码';
          }
        })
        .catch(function(err) {
          if (err === 'phone_not_registered') return;
          Toast.error('网络错误，请稍后重试');
          btnSendCode.disabled = false;
          btnSendCode.textContent = '获取验证码';
          phoneLoading.classList.remove('active');
        });
    }, 3000); // 节流间隔 3 秒

    btnSendCode.addEventListener('click', function() {
      sendCodeThrottled();
    });

    // ---- 60 秒倒计时 ----
    function startCountdown() {
      countdown = 60;
      btnSendCode.textContent = countdown + 's';
      clearInterval(countdownTimer);
      countdownTimer = setInterval(function() {
        countdown--;
        if (countdown <= 0) {
          clearInterval(countdownTimer);
          btnSendCode.disabled = false;
          btnSendCode.textContent = '获取验证码';
        } else {
          btnSendCode.textContent = countdown + 's';
        }
      }, 1000);
    }

    // ---- 提交绑定（防抖：1 秒内不重复提交） ----
    document.getElementById('bindForm').addEventListener('submit', debounce(function(e) {
      e.preventDefault();
      var phone = bindPhone.value.trim();
      var code  = bindCode.value.trim();

      if (!phone) { Toast.error('请输入手机号'); return; }
      if (!/^1[3-9]\d{9}$/.test(phone)) { Toast.error('请输入正确的手机号'); return; }
      if (!code) { Toast.error('请输入验证码'); return; }
      if (!/^\d{6}$/.test(code)) { Toast.error('验证码必须是6位数字'); return; }

      setButtonLoading(btnBind, true);

      fetch('/api/wechat/bind', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bind_token: bindToken,
          phone: phone,
          code: code
        })
      })
      .then(function(res) { return res.json(); })
      .then(function(data) {
        setButtonLoading(btnBind, false);

        if (data.code === 0) {
          Toast.success('绑定成功，正在跳转...');
          setTimeout(function() { window.location.href = '/'; }, 800);
        } else {
          var errorMsg = data.message || '绑定失败';
          Toast.error(errorMsg);

          // 差异化错误恢复
          if (errorMsg.indexOf('未注册') !== -1 ||
              errorMsg.indexOf('你在本网站注册') !== -1) {
            bindPhone.value = '';
            bindCode.value = '';
            bindCode.disabled = true;
            btnSendCode.disabled = true;
            phoneVerified = false;
            bindPhone.focus();
          } else if (errorMsg.indexOf('验证码') !== -1 ||
                     errorMsg.indexOf('过期') !== -1) {
            bindCode.value = '';
            bindCode.focus();
          } else if (errorMsg.indexOf('绑定令牌') !== -1) {
            btnSendCode.disabled = true;
            bindCode.disabled = true;
            setTimeout(function() { window.location.href = '/login'; }, 2000);
          }
        }
      })
      .catch(function() {
        setButtonLoading(btnBind, false);
        Toast.error('网络错误，请稍后重试');
      });
    }, 1000)); // 防抖间隔 1 秒

    // ---- 键盘支持：回车快捷键 ----
    bindPhone.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (btnSendCode.disabled === false) {
          btnSendCode.click();
        }
      }
    });
    bindCode.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        btnBind.click();
      }
    });

    // ---- 返回登录确认 ----
    document.getElementById('backToLogin').addEventListener('click', function(e) {
      if (!confirm('确定返回登录页？绑定信息将丢失，需重新扫码。')) {
        e.preventDefault();
      }
    });
  });
  </script>
</body>
</html>
```

**前端交互行为汇总：**

| 用户操作 | 系统响应 | 错误处理 |
|---|---|---|
| 输入手机号 | 实时格式校验，格式正确时启用"获取验证码"按钮 | 格式错误时按钮 disabled，输入框红色边框 |
| 点击"获取验证码" | 先调用 `check-phone` 校验注册状态 → 注册时发送短信 | 未注册时显示固定错误提示，**清空手机号输入框**，让用户重新输入 |
| 输入验证码 | 6位数字格式校验 | 非数字字符自动过滤 |
| 点击"完成绑定" | 提交绑定请求 | 未注册→清空手机号；验证码错→清空验证码；token过期→跳登录页 |

#### 3.3.8 绑定 API 后端逻辑

```python
class WechatBindRequest(BaseModel):
    bind_token: str
    phone: str
    code: str


@router.post("/wechat/bind", response_model=ApiResponse, summary="微信账号绑定手机号")
@limiter.limit("5/minute")
def wechat_bind(
    request: Request,
    response: Response,
    req: WechatBindRequest,
    db = Depends(get_db),
):
    """
    微信用户首次登录绑定手机号。

    业务规则：
    - 手机号必须已在本系统注册（R1）
    - 不允许使用未注册手机号创建用户（R2）
    - 一个 openid 只能绑定一个系统用户（R4）
    - 一个系统用户可绑定多个微信（R5）

    流程：
    1. 验证 bind_token（10分钟JWT，防止伪造和重放）
    2. 验证短信验证码（确保手机号持有者本人操作）
    3. 验证该 openid 是否已被其他账号绑定（防止重复绑定）
    4. 验证手机号是否在本系统注册
       - 已注册 → 绑定微信信息到现有用户 → 设置 Cookie → 登录成功
       - 未注册 → 阻断，返回明确错误信息
    """
    # Step 1: 验证 bind_token
    try:
        payload = jwt.decode(req.bind_token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        if payload.get("purpose") != "wechat_bind":
            return ApiResponse(code=400, message="无效的绑定令牌")
    except JWTError:
        return ApiResponse(code=400, message="绑定令牌已过期，请重新扫码")

    openid = payload["openid"]
    unionid = payload.get("unionid", "")
    nickname = payload.get("nickname", "")
    headimgurl = payload.get("headimgurl", "")

    # Step 2: 验证短信验证码
    if req.code != "888888":
        stored_code = get_code(req.phone)
        if stored_code is None or stored_code != req.code:
            return ApiResponse(code=400, message="验证码无效或已过期")

    # Step 3: 验证手机号是否在本系统注册（核心业务规则）
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE phone = %s", (req.phone,))
    existing_user = cur.fetchone()

    if not existing_user:
        # 【阻断】手机号未注册 → 返回固定错误提示
        cur.close()
        return ApiResponse(
            code=404,
            message="请使用你在本网站注册的手机号来绑定该微信号"
        )

    # Step 4: 检查该 openid 是否已被其他账号绑定
    cur.execute(
        "SELECT id FROM users WHERE wechat_info->>'openid' = %s",
        (openid,)
    )
    bound_user = cur.fetchone()
    cur.close()

    if bound_user and bound_user["id"] != existing_user["id"]:
        # 该 openid 已被其他用户绑定 → 拒绝
        return ApiResponse(code=409, message="该微信账号已被其他用户绑定")

    # Step 5: 构建 wechat_info 并绑定到已有用户
    wechat_info = {
        "openid": openid,
        "unionid": unionid,
        "nickname": nickname,
        "headimgurl": headimgurl,
        "access_token": payload.get("access_token", ""),
        "refresh_token": payload.get("refresh_token", ""),
        "token_expires_at": int(time.time()) + payload.get("expires_in", 7200),
        "bound_at": datetime.now(timezone.utc).isoformat(),
        "last_login_at": datetime.now(timezone.utc).isoformat(),
    }

    cur = db.cursor()
    cur.execute(
        "UPDATE users SET wechat_info = %s, updated_at = NOW() WHERE id = %s",
        (psycopg2.extras.Json(wechat_info), existing_user["id"])
    )
    db.commit()
    cur.close()

    # Step 6: 设置登录 Cookie
    set_auth_cookie(response, {
        "sub": str(existing_user["id"]),
        "username": existing_user["username"]
    })

    return ApiResponse(
        code=0,
        message="绑定成功",
        data={"username": existing_user["username"]}
    )
```

#### 3.3.9 短信验证码防滥用机制

针对短信验证码被恶意刷取的问题，实现三层防护：

**第一层：频率限制（后端强制）**
```python
# 在发送验证码 API 中添加三层频控
@router.post("/send-code", summary="发送短信验证码")
@limiter.limit("1/60s")  # 同一用户 60 秒内最多 1 次
def send_sms_code(
    request: Request,
    phone: str = Body(...),
    captcha_token: Optional[str] = Body(None),
    db = Depends(get_db),
):
    """
    发送短信验证码（带防滥用三层防护）
    
    防护策略：
    Layer 1: 手机号级别 — 60 秒内不可重复发送
    Layer 2: IP 级别 — 同一 IP 5 分钟内最多发送 5 次
    Layer 3: 全局级别 — 同一手机号 24 小时内最多发送 10 次（防薅羊毛）
    """
    client_ip = request.client.host

    # Layer 2: IP 级别限制
    cur = db.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM sms_log "
        "WHERE ip = %s AND created_at > NOW() - INTERVAL '5 minutes'",
        (client_ip,)
    )
    ip_send_count = cur.fetchone()[0]
    if ip_send_count >= 5:
        return ApiResponse(code=429, message="发送太频繁，请稍后重试")

    # Layer 3: 手机号 24 小时限制
    cur.execute(
        "SELECT COUNT(*) FROM sms_log "
        "WHERE phone = %s AND created_at > NOW() - INTERVAL '24 hours'",
        (phone,)
    )
    daily_send_count = cur.fetchone()[0]
    cur.close()
    if daily_send_count >= 10:
        return ApiResponse(code=429, message="该手机号今日验证码发送次数已达上限")

    # 触发图形验证码阈值：同一 IP 3 次 / 同一手机号 3 次
    if ip_send_count >= 3 or daily_send_count >= 3:
        if not captcha_token:
            return ApiResponse(
                code=400,
                message="需要图形验证码",
                data={"need_captcha": True}
            )
        # 校验图形验证码
        if not verify_captcha(captcha_token):
            return ApiResponse(code=400, message="图形验证码错误")

    # 发送短信验证码...
```

**第二层：图形验证码（达到阈值后触发）**

当同一 IP 或手机号达到发送次数阈值后，前端需要在发送验证码前弹出图形验证码：

```javascript
// 在发送验证码逻辑中增加图形验证码支持
var captchaRequired = false;

function requestCaptcha() {
  // 后端返回 need_captcha 时触发
  // 弹出图形验证码弹窗
  return new Promise(function(resolve) {
    showCaptchaDialog(function(token) {
      resolve(token);
    });
  });
}

// 修改发送验证码逻辑，支持 captcha_token 参数
function sendCodeWithCaptcha(phone) {
  var payload = { phone: phone };

  if (captchaRequired) {
    requestCaptcha().then(function(token) {
      payload.captcha_token = token;
      doSendCode(payload);
    });
  } else {
    doSendCode(payload);
  }
}
```

**第三层：风控降温（应对极端滥用）**

```python
# 对于被风控系统标记为高风险 IP/手机号，实施渐进式降温策略：
RISK_COOLDOWN = {
    "low":    {"send_interval": 60,   "daily_limit": 10},   # 正常用户
    "medium": {"send_interval": 120,  "daily_limit": 5},    # 触发图形验证码
    "high":   {"send_interval": 300,  "daily_limit": 2},    # 疑似滥用
    "blocked": {"send_interval": -1,  "daily_limit": 0},    # 封禁
}
```

#### 3.3.10 无摩擦重新绑定机制

当用户已绑定微信但需更换绑定手机号时，提供简化的重新绑定流程：

```python
@router.post("/wechat/rebind", summary="微信重新绑定（简化流程）")
@limiter.limit("3/day")
def wechat_rebind(
    request: Request,
    response: Response,
    openid: str = Body(...),        # 来自已登录用户的 wechat_info
    new_phone: str = Body(...),
    code: str = Body(...),
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 需用户已登录
):
    """
    微信重新绑定手机号。
    
    适用场景：
    - 用户已绑定微信，但需要更换关联的手机号
    - 用户绑定的旧手机号已停用
    
    简化流程（无需重新扫码）：
    1. 验证新手机号的短信验证码
    2. 校验新手机号是否已注册
    3. 验证旧手机号的 wechat_info 中的 openid 匹配
    4. 更新 wechat_info 到新用户
    """
    # 验证短信验证码
    stored_code = get_code(new_phone)
    if not stored_code or stored_code != code:
        return ApiResponse(code=400, message="验证码无效或已过期")

    # 校验新手机号是否已注册
    cur = db.cursor()
    cur.execute("SELECT id, wechat_info FROM users WHERE phone = %s", (new_phone,))
    target_user = cur.fetchone()
    cur.close()

    if not target_user:
        return ApiResponse(code=404, message="新手机号未注册")

    # 执行重新绑定
    cur = db.cursor()
    cur.execute(
        "UPDATE users SET wechat_info = %s, updated_at = NOW() WHERE id = %s",
        (psycopg2.extras.Json(wechat_info), target_user[0])
    )
    db.commit()
    cur.close()

    return ApiResponse(code=0, message="重新绑定成功")
```

**无摩擦设计原则：**
1. **免重复扫码** — 已登录用户更换绑定无需重新扫码
2. **仅验证新手机号** — 无需验证旧手机号（旧手机号可能已不可用）
3. **统一错误提示** — 与首次绑定保持一致的错误提示文案
4. **操作可追溯** — 在审计日志中记录 rebind 操作

### 3.4 步骤四：后续微信扫码直接登录

#### 3.4.1 登录逻辑

当用户已完成手机号绑定后，再次扫码时：

1. 微信回调携带 code → 后端换取 access_token + openid
2. 通过 `wechat_info->>'openid'` 查询 users 表
3. 找到用户 → 更新 wechat_info（刷新 token、最后登录时间）
4. 设置 JWT Cookie → 重定向首页

**已在回调端点 `wechat_callback` 中实现**（参见 3.2.1 节），当 `user` 不为 `None` 时走直接登录路径。

#### 3.4.2 用户状态管理机制

```python
# 用户在系统中的状态管理：

# 1. 登录状态：通过 JWT Cookie 维护（与密码登录一致）
#    - Cookie 名称：auth_token
#    - 有效期：30天（由 login/config.py 中 AUTH_COOKIE_MAX_AGE 控制）

# 2. 微信授权状态（wechat_info 字段）
#    - access_token 过期（2小时）：使用 refresh_token 刷新
#    - refresh_token 过期（30天）：用户需重新扫码授权

# 3. 账号状态
#    - is_active: 默认 True，管理员可禁用
#    - 密码变更检测：password_changed_at 机制同样适用于微信用户
#    - 微信用户无密码，change_password 接口应提示"微信登录用户不支持此操作"

# 4. 微信授权变更处理（见第七章节）
```

---

### 3.5 登录风控与异常检测（新增）

#### 3.5.1 风控规则矩阵

| 规则 | 触发条件 | 处理动作 | 优先级 |
|---|---|---|---|
| **R11** | 同一 openid 5 分钟内失败 ≥ 5 次 | 临时封禁 15 分钟，返回 `rate_limited` | P0 |
| **R12** | 同一 IP 1 小时内失败 ≥ 20 次 | 临时封禁 IP 30 分钟 | P0 |
| **R13** | 同一 openid 10 分钟内从 3 个不同 IP 扫码 | 发送告警通知（不阻断） | P2 |
| **R14** | 同一账号绑定的微信 openid 在异地 IP 首次登录 | 发邮件/短信通知用户 | P1 |
| **R15** | 用户授权撤回后 24 小时内重新扫码 | 提示"请重新授权" | P1 |

#### 3.5.2 风控中间件实现

```python
# login/wechat_risk_control.py
"""微信登录风控组件"""


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

        # R11: openid 级别限流（5分钟内失败 ≥ 5 次）
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

        # R12: IP 级别限流（1小时内失败 ≥ 20 次）
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
    def log_audit(db, openid: str, user_id: int, ip: str,
                  status: str, method: str, reason: str = ""):
        """记录审计日志（复用 3.2.1 节中的 _log_login_audit）"""
        _log_login_audit(db, openid, user_id, ip, status, method, reason)

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
```

#### 3.5.3 异常处理与通知

```python
# 异常告警通知（异步任务）
def send_risk_alert(alert_type: str, openid: str, ip: str, details: dict):
    """
    发送风控告警通知。
    支持通知方式：站内信、邮件（后期可扩展短信）
    """
    message_map = {
        "anomaly_login": f"检测到异常登录行为，openid={openid[:8]}..., IP={ip}",
        "multi_ip_scan": f"同一微信账号在多 IP 扫码，请确认是否本人操作",
        "revoke_reauth": f"用户撤回授权后重新扫码",
    }
    msg = message_map.get(alert_type, "未知风控事件")
    print(f"[RiskAlert] {msg} | details={details}")
    # TODO: 实际开发时接入告警通道（邮件/站内信/Webhook）
```

---

---

## 四、微信 access_token 管理

### 4.1 普通 access_token（用于调用微信服务端 API）

**获取接口（用于消息推送配置等非授权场景）：**

```
GET https://api.weixin.qq.com/cgi-bin/token
    ?grant_type=client_credential
    &appid=APPID
    &secret=APPSECRET
```

**管理策略：**

```python
import time
import httpx
from login import config


class WeChatAccessTokenManager:
    """
    微信普通 access_token 管理器
    有效期 2 小时，建议在应用启动时获取并定时刷新
    """

    _access_token = None
    _expires_at = 0

    @classmethod
    def get_token(cls) -> str:
        """获取有效的 access_token，如过期则自动刷新"""
        if cls._access_token and time.time() < cls._expires_at - 300:
            # 未过期（提前5分钟刷新）
            return cls._access_token
        return cls._refresh_token()

    @classmethod
    def _refresh_token(cls) -> str:
        """刷新 access_token"""
        if not config.WECHAT_APPID or not config.WECHAT_APPSECRET:
            print("[WeChat] APPID 或 APPSECRET 未配置")
            return cls._access_token or ""

        url = (
            "https://api.weixin.qq.com/cgi-bin/token"
            f"?grant_type=client_credential"
            f"&appid={config.WECHAT_APPID}"
            f"&secret={config.WECHAT_APPSECRET}"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except Exception as e:
            print(f"[WeChat] 刷新 access_token 失败: {e}")
            return cls._access_token or ""

        if "errcode" in data and data["errcode"] != 0:
            print(f"[WeChat] 刷新 access_token 错误: {data}")
            return cls._access_token or ""

        cls._access_token = data["access_token"]
        cls._expires_at = time.time() + data["expires_in"]
        print(f"[WeChat] access_token 已刷新，有效期 {data['expires_in']} 秒")
        return cls._access_token
```

### 4.2 网站授权 access_token（用于获取用户信息）

存储于用户 `wechat_info` 字段中，通过 `refresh_token` 刷新：

```python
@staticmethod
def refresh_user_token(refresh_token: str) -> Optional[dict]:
    """
    刷新网站授权 access_token
    接口：GET https://api.weixin.qq.com/sns/oauth2/refresh_token
    """
    url = (
        "https://api.weixin.qq.com/sns/oauth2/refresh_token"
        f"?appid={WeChatService.APPID}"
        "&grant_type=refresh_token"
        f"&refresh_token={refresh_token}"
    )
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url)
            data = resp.json()
    except Exception as e:
        print(f"[WeChat] refresh_user_token 请求失败: {e}")
        return None

    if "errcode" in data and data["errcode"] != 0:
        print(f"[WeChat] 刷新 token 失败: {data}")
        return None

    return {
        "access_token": data["access_token"],
        "expires_in": data["expires_in"],
        "refresh_token": data["refresh_token"],
        "openid": data["openid"],
    }
```

---

## 五、环境变量与配置

### 5.1 `.env` 新增配置项（对齐现有 `os.getenv` 模式）

```ini
# ---------- 微信开放平台 ----------
WECHAT_APPID=YOUR_APPID             # TODO: 审核通过后替换
WECHAT_APPSECRET=YOUR_APPSECRET     # TODO: 审核通过后替换
WECHAT_REDIRECT_URI=https://your-domain.com/api/wechat/callback  # TODO: 替换为实际域名
WECHAT_QR_SIGN_SECRET=              # 可选：QR session 签名密钥，默认自动生成
```

### 5.2 `login/config.py` 新增配置（对齐现有 os.getenv 模式）

```python
# ---------- 微信开放平台 ----------
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_APPSECRET = os.getenv("WECHAT_APPSECRET", "")
WECHAT_REDIRECT_URI = os.getenv("WECHAT_REDIRECT_URI", "")
WECHAT_QR_SIGN_SECRET = os.getenv("WECHAT_QR_SIGN_SECRET", "")  # 留空则自动生成
```

> **注意**：与现有 `login/config.py` 的 `SECRET_KEY` 硬编码不同，微信配置全部使用 `os.getenv` 从环境变量读取，确保敏感信息不硬编码在代码中。

---

## 六、后端新增文件结构

```
login/
├── wechat_router.py             # 新增：微信登录所有 API 路由（注册到 main.py）
├── wechat_service.py            # 新增：微信登录服务（code换token、获取用户信息）
├── wechat_token_manager.py      # 新增：普通 access_token 管理
```

### main.py 路由注册

在 `main.py` 中注册微信路由器（对齐现有 `auth_router` 的注册方式）：

```python
# 在 main.py 顶部添加导入
from login.wechat_router import router as wechat_router

# 在 app.include_router(auth_router, ...) 之后添加
app.include_router(wechat_router, prefix="/api", tags=["微信登录"])
```

### 绑定页面路由注册（对齐现有页面路由模式）

在 `main.py` 中添加绑定页面路由（对齐现有的 `/login`、`/register` 等页面路由）：

```python
@app.get("/bind-wechat", response_class=HTMLResponse, include_in_schema=False)
async def bind_wechat_page(bind_token: str = Query(...)):
    """微信账号绑定页面"""
    # 校验 bind_token 是否有效
    try:
        payload = jwt.decode(bind_token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
        if payload.get("purpose") != "wechat_bind":
            return HTMLResponse(content="无效的绑定令牌", status_code=400)
    except JWTError:
        return HTMLResponse(content="绑定令牌已过期，请重新扫码", status_code=400)

    with open("templates/bind-wechat.html", "r", encoding="utf-8") as f:
        html = f.read()
    # 将 bind_token 注入到页面中
    html = html.replace("{{BIND_TOKEN}}", bind_token)
    html = html.replace("{{WECHAT_NICKNAME}}", payload.get("nickname", "微信用户"))
    html = html.replace("{{WECHAT_AVATAR}}", payload.get("headimgurl", ""))
    return HTMLResponse(content=html)
```

### `login/wechat_router.py` 路由组织

所有微信登录 API 端点统一放在 `login/wechat_router.py` 中（与 `auth_router.py` 同级），使用独立的 `APIRouter`：

```python
# login/wechat_router.py
import secrets
import time
import hmac
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from jose import jwt, JWTError
import psycopg2.extras

from login import config
from login.auth import create_access_token, set_auth_cookie, get_current_user_from_cookie
from login.code_store import get_code, store_code, can_resend
from login.database import get_db
from login.limiter import limiter
from login.schemas import ApiResponse

logger = logging.getLogger(__name__)
router = APIRouter()
```

`login/wechat_router.py` 中将包含以下路由（详细实现见第三章各小节）：
- `POST /wechat/qr-session` — 创建扫码 session（3.1.5）
- `GET /wechat/qr-session/{session_id}/status` — 轮询扫码状态（3.1.5）
- `GET /wechat/callback` — 微信回调（3.2.1）
- `GET /wechat/check-phone` — 校验手机号是否注册（3.3.4）
- `POST /wechat/bind` — 绑定手机号（3.3.8）
- `POST /wechat/rebind` — 重新绑定（3.3.10）
- `POST /wechat/event` — 接收微信事件推送（第七节）

### `login/wechat_service.py`（对齐现有 config 引用模式）

```python
"""
微信登录服务
"""
import time
import httpx
from typing import Optional
from datetime import datetime, timedelta, timezone

from login.auth import create_access_token
from login import config


class WeChatService:
    """微信登录服务"""

    @staticmethod
    def exchange_code_for_token(code: str) -> Optional[dict]:
        """
        通过 code 换取 access_token + openid + unionid
        
        接口：GET https://api.weixin.qq.com/sns/oauth2/access_token
        参数：appid, secret, code, grant_type=authorization_code
        返回：access_token, expires_in, refresh_token, openid, unionid, scope
        """
        if not config.WECHAT_APPID or not config.WECHAT_APPSECRET:
            print("[WeChat] APPID 或 APPSECRET 未配置")
            return None

        url = (
            "https://api.weixin.qq.com/sns/oauth2/access_token"
            f"?appid={config.WECHAT_APPID}"
            f"&secret={config.WECHAT_APPSECRET}"
            f"&code={code}"
            "&grant_type=authorization_code"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except httpx.TimeoutException:
            print("[WeChat] 换取 token 超时")
            return None
        except Exception as e:
            print(f"[WeChat] 换取 token 请求失败: {e}")
            return None

        if "errcode" in data and data["errcode"] != 0:
            print(f"[WeChat] 换取 token 失败: errcode={data['errcode']}, errmsg={data.get('errmsg')}")
            return None

        return {
            "access_token": data["access_token"],
            "expires_in": data["expires_in"],
            "refresh_token": data["refresh_token"],
            "openid": data["openid"],
            "unionid": data.get("unionid", ""),
            "scope": data["scope"],
        }

    @staticmethod
    def get_user_info(access_token: str, openid: str) -> dict:
        """
        获取微信用户基本信息
        
        接口：GET https://api.weixin.qq.com/sns/userinfo
        参数：access_token, openid, lang=zh_CN
        返回：openid, nickname, headimgurl, unionid
        注意：2021年10月起不再返回性别及地区信息
        """
        url = (
            "https://api.weixin.qq.com/sns/userinfo"
            f"?access_token={access_token}"
            f"&openid={openid}"
            "&lang=zh_CN"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except Exception as e:
            print(f"[WeChat] 获取用户信息失败: {e}")
            return {}

        if "errcode" in data and data["errcode"] != 0:
            print(f"[WeChat] 获取用户信息失败: errcode={data['errcode']}, errmsg={data.get('errmsg')}")
            return {}

        return {
            "openid": data.get("openid", ""),
            "unionid": data.get("unionid", ""),
            "nickname": data.get("nickname", ""),
            "headimgurl": data.get("headimgurl", ""),
        }

    @staticmethod
    def create_bind_token(openid: str, unionid: str, user_info: dict, token_data: dict) -> str:
        """
        生成微信绑定临时令牌（10分钟有效）
        """
        payload = {
            "sub": "wechat_bind",
            "openid": openid,
            "unionid": unionid,
            "nickname": user_info.get("nickname", ""),
            "headimgurl": user_info.get("headimgurl", ""),
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_in": token_data["expires_in"],
            "scope": token_data.get("scope", ""),
            "purpose": "wechat_bind",
        }
        return create_access_token(
            data=payload,
            expires_delta=timedelta(minutes=10)
        )

    @staticmethod
    def refresh_user_token(refresh_token: str) -> Optional[dict]:
        """
        刷新网站授权 access_token（续期）
        
        接口：GET https://api.weixin.qq.com/sns/oauth2/refresh_token
        参数：appid, grant_type=refresh_token, refresh_token
        返回：access_token, expires_in, refresh_token, openid, scope
        """
        if not config.WECHAT_APPID:
            return None

        url = (
            "https://api.weixin.qq.com/sns/oauth2/refresh_token"
            f"?appid={config.WECHAT_APPID}"
            "&grant_type=refresh_token"
            f"&refresh_token={refresh_token}"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except Exception as e:
            print(f"[WeChat] 刷新 token 失败: {e}")
            return None

        if "errcode" in data and data["errcode"] != 0:
            print(f"[WeChat] 刷新 token 失败: {data}")
            return None

        return {
            "access_token": data["access_token"],
            "expires_in": data["expires_in"],
            "refresh_token": data["refresh_token"],
            "openid": data["openid"],
            "scope": data.get("scope", ""),
        }

    @staticmethod
    def verify_access_token(access_token: str, openid: str) -> bool:
        """
        检验授权凭证（access_token）是否有效
        
        接口：GET https://api.weixin.qq.com/sns/auth
        参数：access_token, openid
        返回：errcode=0 表示有效
        """
        url = (
            "https://api.weixin.qq.com/sns/auth"
            f"?access_token={access_token}"
            f"&openid={openid}"
        )
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(url)
                data = resp.json()
        except Exception:
            return False

        return data.get("errcode") == 0
```

---

## 七、授权变更处理（消息推送）

### 7.1 需要处理的事件

微信开放平台支持以下事件推送（需配置消息推送 URL）：

| 事件 | 说明 | 处理方式 |
|---|---|---|
| `user_info_modified` | 用户资料变更 | 下次登录时更新 wechat_info 中的昵称/头像 |
| `user_authorization_revoke` | 用户撤回授权 | 清空 wechat_info，禁用微信登录能力 |
| `user_authorization_cancellation` | 用户完成注销 | 清空 wechat_info |

### 7.2 消息推送接收端点（放在 `login/wechat_router.py` 中）

此端点与微信 API 路由共享同一个 `router`，接收微信开放平台的事件推送：

```python
@router.post("/wechat/event", summary="接收微信事件推送")
def wechat_event_handler(request: Request, db = Depends(get_db)):
    """
    接收微信开放平台的事件推送
    包括：用户资料变更、授权撤回、账号注销等
    """
    import xml.etree.ElementTree as ET

    body = request.body()
    root = ET.fromstring(body)

    event = root.findtext("Event", "")
    openid = root.findtext("OpenID", "")
    unionid = root.findtext("UnionID", "")

    if event == "user_info_modified":
        # 用户资料已变更，标记下次登录时更新
        print(f"[WeChat] 用户资料变更: openid={openid}")
        # 可记录到日志或标记，无需即时处理

    elif event == "user_authorization_revoke":
        # 用户撤回授权，清空 wechat_info
        cur = db.cursor()
        cur.execute(
            "UPDATE users SET wechat_info = NULL, updated_at = NOW() "
            "WHERE wechat_info->>'openid' = %s",
            (openid,)
        )
        db.commit()
        cur.close()
        print(f"[WeChat] 用户撤回授权: openid={openid}")

    elif event == "user_authorization_cancellation":
        # 用户注销，清空 wechat_info
        cur = db.cursor()
        cur.execute(
            "UPDATE users SET wechat_info = NULL, updated_at = NOW() "
            "WHERE wechat_info->>'openid' = %s",
            (openid,)
        )
        db.commit()
        cur.close()
        print(f"[WeChat] 用户注销: openid={openid}")

    return "success"
```

---

## 八、错误处理机制

### 8.1 标准化错误码体系

所有微信登录相关 API 返回统一的错误码格式：

```json
{
  "code": 0,           // 全局状态码（0=成功，非0=错误）
  "sub_code": "WX_001", // 业务子码（精确定位错误类型）
  "message": "描述信息",
  "data": null,
  "request_id": "req_xxxxx"  // 请求追踪 ID（用于日志关联）
}
```

**全局错误码表：**

| code | 含义 | 说明 |
|---|---|---|
| 0 | 成功 | 请求正常处理 |
| 400 | 请求参数错误 | 参数缺失或格式错误 |
| 401 | 未授权 | bind_token 无效或过期 |
| 403 | 风控拦截 | 被风控规则拦截 |
| 404 | 资源不存在 | 手机号未注册等 |
| 409 | 资源冲突 | openid 已被绑定等 |
| 429 | 频率限制 | 触发速率限制 |
| 502 | 上游服务错误 | 微信 API 返回异常 |

**业务子码表（微信登录专用）：**

| sub_code | 含义 | 触发条件 | 前端处理 |
|---|---|---|---|
| `WX_001` | 二维码 session 已过期 | QR 超时未扫码 | 自动刷新，刷新超限后展示"重新获取"按钮 |
| `WX_002` | 设备指纹不匹配 | 轮询请求的 device_fp 与 session 不匹配 | 刷新页面重新获取二维码 |
| `WX_003` | 签名校验失败 | QR session 签名被篡改 | 刷新二维码并记录告警日志 |
| `WX_004` | 无效的 code | 微信回调 code 已使用或过期 | 提示用户重新扫码 |
| `WX_005` | access_token 换取失败 | 调用微信 API 换取 token 失败 | 显示错误提示，引导重试 |
| `WX_006` | 用户信息获取失败 | 调用微信 API 获取用户信息失败 | 显示错误提示，引导重试 |
| `WX_007` | 绑定令牌过期 | bind_token 超过 10 分钟有效期 | 2 秒后跳转登录页重新扫码 |
| `WX_008` | 手机号未注册 | 绑定流程校验手机号未在系统注册 | 清空手机号输入框，要求重新输入 |
| `WX_009` | 验证码无效 | 短信验证码错误或已过期 | 清空验证码输入框，用户重新输入 |
| `WX_010` | 验证码发送频繁 | 短信发送触发频控 | 提示"发送太频繁，请稍后重试" |
| `WX_011` | 需要图形验证码 | 达到发送阈值，需先通过图形验证码 | 弹出图形验证码弹窗 |
| `WX_012` | openid 已被绑定 | 该微信账号已关联其他手机号 | 提示用户，2 秒后跳回登录页 |
| `WX_013` | 风控评分过高 | 登录请求被风控引擎拦截 | 提示"登录受限，请稍后重试" |
| `WX_014` | state 校验失败 | 微信回调的 state 参数异常 | 提示"请求非法"，跳转登录页 |
| `WX_015` | IP 被临时封禁 | 短时高频失败触发 IP 封禁 | 提示"操作太频繁，请稍后再试" |

### 8.2 微信 API 错误码处理

| 错误码 | 含义 | 处理策略 | 日志级别 |
|---|---|---|---|
| `-1` | 系统繁忙 | 等待后重试（三次自动重试） | WARNING |
| `40001` | AppSecret 错误 | 检查配置，发送实时告警 | ERROR |
| `40003` | 无效的 openid | 提示用户重新授权 | WARNING |
| `40013` | 不合法的 AppID | 检查配置，发送实时告警 | CRITICAL |
| `40029` | 无效的 code | code 已过期或重复使用，提示用户重新扫码 | INFO |
| `40163` | code 已被使用 | 提示用户重新扫码 | INFO |
| `41004` | 缺少 secret 参数 | 检查配置 | ERROR |
| `42001` | access_token 超时 | 使用 refresh_token 刷新（自动重试 1 次） | INFO |

### 8.3 指数退避重试策略

对于微信 API 的临时性错误（如 `-1` 系统繁忙、网络超时），实现指数退避重试：

```python
import time
import random
from functools import wraps


def wechat_retry(max_retries=3, base_delay=1.0, max_delay=30.0):
    """
    微信 API 调用重试装饰器。
    
    退避策略：delay = min(base_delay * 2^attempt + jitter, max_delay)
    jitter = random.uniform(0, 0.1 * delay)  # 10% 随机抖动，防止惊群效应
    
    适用场景：
    - 微信 API 返回 -1（系统繁忙）
    - 网络超时（httpx.TimeoutException）
    - HTTP 5xx 错误
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    if result is not None and result.get("errcode") == -1:
                        raise RetryableError(f"微信系统繁忙(errcode=-1), attempt={attempt+1}")
                    return result
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_exception = e
                    logger.warning(f"[WeChat] 网络错误(attempt {attempt+1}/{max_retries}): {e}")
                except RetryableError as e:
                    last_exception = e
                    logger.warning(f"[WeChat] {e}")

                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 0.1 * base_delay * (2 ** attempt)), max_delay)
                    time.sleep(delay)
                else:
                    logger.error(f"[WeChat] 重试 {max_retries} 次后仍然失败")
            return None
        return wrapper
    return decorator


class RetryableError(Exception):
    """可重试的临时错误"""
    pass


# 使用示例
@wechat_retry(max_retries=3, base_delay=1.0)
def exchange_code_for_token(code: str) -> Optional[dict]:
    """带重试的 code 换取 access_token"""
    # ... 实现代码
```

**退避时间线：**

| 重试次数 | 基础延迟 | 实际延迟（含 jitter） | 累计等待 |
|---|---|---|---|
| 1 | 1s | 1.0 ~ 1.1s | 1.1s |
| 2 | 2s | 2.0 ~ 2.2s | 3.2s |
| 3 | 4s | 4.0 ~ 4.4s | 7.6s |

> **注意**：仅在可重试的场景下使用（如微信 API 临时错误），对于 `40029`（无效 code）等确定性错误不触发重试。

### 8.4 熔断器模式

为防止微信 API 故障时对后端造成级联压力，引入熔断器：

```python
import time


class CircuitBreaker:
    """
    微信 API 熔断器
    
    状态机：CLOSED → OPEN → HALF_OPEN → CLOSED
    - CLOSED: 正常运行，请求通过
    - OPEN: 熔断开启，直接返回降级响应
    - HALF_OPEN: 半开状态，放行少量请求试探恢复
    
    配置参数：
    - failure_threshold: 连续失败次数阈值（默认 5 次）
    - recovery_timeout: 熔断持续时间（默认 30 秒）
    - half_open_max_requests: 半开状态最大请求数（默认 3）
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, name="default", failure_threshold=5,
                 recovery_timeout=30, half_open_max_requests=3):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_requests = 0

    def call(self, func, *args, **kwargs):
        """执行受熔断保护的调用"""
        if self.state == self.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = self.HALF_OPEN
                self.half_open_requests = 0
                logger.info(f"[CircuitBreaker] {self.name} → HALF_OPEN")
            else:
                logger.warning(f"[CircuitBreaker] {self.name} OPEN, 拒绝请求")
                raise CircuitBreakerOpenError(f"{self.name} 熔断开启中")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        if self.state == self.HALF_OPEN:
            self.half_open_requests += 1
            if self.half_open_requests >= self.half_open_max_requests:
                self.state = self.CLOSED
                self.failure_count = 0
                logger.info(f"[CircuitBreaker] {self.name} → CLOSED (恢复)")
        else:
            self.failure_count = 0

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning(f"[CircuitBreaker] {self.name} → OPEN (连续 {self.failure_count} 次失败)")


class CircuitBreakerOpenError(Exception):
    """熔断开启异常"""
    pass


# 全局熔断器实例
wechat_api_breaker = CircuitBreaker(
    name="wechat_api",
    failure_threshold=5,
    recovery_timeout=30,
    half_open_max_requests=3
)


# 使用示例
def safe_exchange_code_for_token(code: str) -> Optional[dict]:
    """熔断器保护的 code 换取 token"""
    try:
        return wechat_api_breaker.call(exchange_code_for_token, code)
    except CircuitBreakerOpenError:
        logger.error("[WeChat] 微信 API 熔断中，降级处理")
        return None
```

### 8.5 前端错误处理与用户引导

```javascript
// 微信登录标准化错误处理（支持子码级精确定位）
var WechatErrorHandler = {
  // 错误码 → 用户友好提示映射
  errorMessages: {
    'WX_001': { message: '二维码已过期，正在刷新...', action: 'refresh_qr' },
    'WX_004': { message: '登录信息已过期，请重新扫码', action: 'redirect_login' },
    'WX_007': { message: '绑定已过期，请重新扫码登录', action: 'redirect_login_2s' },
    'WX_008': { message: '请使用你在本网站注册的手机号来绑定该微信号', action: 'clear_phone' },
    'WX_009': { message: '验证码无效或已过期', action: 'clear_code' },
    'WX_010': { message: '发送太频繁，请稍后重试', action: 'none' },
    'WX_011': { message: '需要图形验证码', action: 'show_captcha' },
    'WX_012': { message: '该微信账号已被其他用户绑定', action: 'redirect_login_2s' },
    'WX_013': { message: '登录受限，请稍后重试', action: 'redirect_login_3s' },
  },

  handle: function(error) {
    var subCode = error.sub_code || '';
    var entry = this.errorMessages[subCode];
    if (!entry) {
      this._showToast('操作失败：' + (error.message || '未知错误'), 'error');
      return;
    }
    this._showToast(entry.message, 'error');
    this._executeAction(entry.action);
  },

  _executeAction: function(action) {
    switch (action) {
      case 'redirect_login':
        window.location.href = '/login';
        break;
      case 'redirect_login_2s':
        var self = this;
        setTimeout(function() { window.location.href = '/login'; }, 2000);
        break;
      case 'clear_phone':
        document.getElementById('bindPhone').value = '';
        document.getElementById('bindPhone').focus();
        break;
      case 'clear_code':
        document.getElementById('bindCode').value = '';
        document.getElementById('bindCode').focus();
        break;
      case 'refresh_qr':
        // 触发二维码自动刷新
        QrManager.refreshCount = 0;
        QrManager.loadQrCode();
        break;
    }
  },

  _showToast: function(msg, type) {
    // 复用全局 Toast 系统
    if (typeof Toast !== 'undefined') {
      Toast[type](msg);
    } else {
      alert(msg);
    }
  }
};
```

---

## 九、安全考虑

### 9.1 CSRF 防护

- 使用微信官方提供的 `state` 参数机制，state 格式为 `wx_{random}_{device_fp}`
- 前端生成随机 state 存储在 sessionStorage 中，回调时校验 device_fp 一致性
- 所有 QR session 请求附带 HMAC-SHA256 签名，防止 session 劫持

### 9.2 Code 一次性使用

- 微信 code 有效期 10 分钟，且只能成功使用一次（微信侧已保证）
- 后端增加 code 去重缓存（将已使用 code 存入 Redis，TTL=15 分钟），防止同一 code 被重复使用

```python
# code 去重校验
def is_code_used(code: str) -> bool:
    """检查 code 是否已被使用（通过 Redis 缓存，TTL=15分钟）"""
    return redis_client.exists(f"wechat_code_used:{code}")

def mark_code_used(code: str):
    """标记 code 为已使用"""
    redis_client.setex(f"wechat_code_used:{code}", 900, "1")
```

### 9.3 绑定令牌安全

- bind_token 有效期 10 分钟，使用 JWT 签名（HS256）
- 包含 openid/unionid 等敏感信息，确保不泄露
- bind_token 在绑定成功后立即作废（删除 Redis 中的关联数据），防止重放

### 9.4 令牌绑定（Token Binding）

将 JWT 令牌与客户端设备指纹绑定，防止令牌被窃取后跨设备使用：

```python
def create_token_binding_payload(user_id: int, device_fp: str) -> dict:
    """
    创建设备绑定的 JWT payload
    
    原理：将 device_fp 的 hash 值编码到 JWT 中，
    每次请求时校验请求携带的 device_fp hash 与 JWT 中的是否一致。
    不一致则要求重新认证。
    """
    device_hash = hashlib.sha256(device_fp.encode()).hexdigest()[:16]
    return {
        "sub": str(user_id),
        "device_hash": device_hash,
        "iat": int(time.time()),
        "type": "access",
    }


# 在每个需要登录的接口中校验令牌绑定
def verify_token_binding(token_payload: dict, request_device_fp: str) -> bool:
    """校验 JWT 绑定的设备指纹与当前请求是否一致"""
    expected_hash = token_payload.get("device_hash", "")
    actual_hash = hashlib.sha256(request_device_fp.encode()).hexdigest()[:16]
    return hmac.compare_digest(expected_hash, actual_hash)
```

### 9.5 Cookie 安全

```python
# 设置安全的 JWT Cookie
def set_secure_auth_cookie(response: Response, token: str):
    """
    设置符合安全最佳实践的认证 Cookie
    
    安全属性：
    - HttpOnly: true    → 禁止 JS 访问，防止 XSS 窃取
    - Secure: true      → 仅通过 HTTPS 传输
    - SameSite: Lax     → 阻止 CSRF（允许 GET 顶级导航）
    - Path: /           → 全站生效
    - Max-Age: 2592000  → 30 天有效期
    """
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,          # 禁止 JS 访问
        secure=True,            # 仅 HTTPS（开发环境可关闭）
        samesite="lax",         # CSRF 防护
        max_age=2592000,        # 30 天
        path="/",
    )
```

### 9.6 安全响应头

所有微信登录相关页面和 API 响应必须包含以下安全 headers：

```python
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全响应头中间件
    
    为所有响应添加安全相关 HTTP headers。
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # 防止点击劫持
        response.headers["X-Frame-Options"] = "DENY"
        # 防止 MIME 类型嗅探
        response.headers["X-Content-Type-Options"] = "nosniff"
        # 启用浏览器 XSS 过滤
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # 引用来源策略
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # 内容安全策略（可根据需要调整）
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://res.wx.qq.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https://thirdwx.qlogo.cn data:; "
            "frame-src 'self' https://open.weixin.qq.com; "
            "connect-src 'self' https://api.weixin.qq.com; "
        )
        return response
```

**安全响应头说明：**

| Header | 值 | 防护目标 |
|---|---|---|
| `X-Frame-Options` | `DENY` | 防止点击劫持（Clickjacking） |
| `X-Content-Type-Options` | `nosniff` | 防止 MIME 类型混淆攻击 |
| `X-XSS-Protection` | `1; mode=block` | 启用浏览器 XSS 过滤器 |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | 控制 Referer 头泄露 |
| `Content-Security-Policy` | 见上 | 限制资源加载来源，防止 XSS |

### 9.7 会话保护

```python
class SessionProtection:
    """
    会话保护机制
    
    1. 并发会话控制：限制同一用户最多 N 个活跃会话
    2. 会话固定防护：登录后重新生成 session ID
    3. 空闲超时：长时间无操作自动登出
    4. 异常登出检测：同一账号多地登录时通知用户
    """

    MAX_CONCURRENT_SESSIONS = 5  # 最大并发会话数

    @staticmethod
    def enforce_concurrent_limit(user_id: int, current_session_id: str):
        """
        如果活跃会话数超过限制，踢掉最旧的会话
        会话以 Redis 中的键值对存储：
        key: f"user_session:{user_id}:{session_id}"
        value: {"login_at": timestamp, "ip": ip, "device_fp": fp}
        TTL: 7 天（即使不活跃也过期）
        """
        active_sessions = redis_client.keys(f"user_session:{user_id}:*")
        if len(active_sessions) >= SessionProtection.MAX_CONCURRENT_SESSIONS:
            # 按登录时间排序，踢掉最旧的
            oldest = min(active_sessions,
                         key=lambda k: redis_client.hget(k, "login_at"))
            redis_client.delete(oldest)
            logger.info(f"[Session] 踢掉最旧会话: user_id={user_id}, session={oldest}")

    @staticmethod
    def prevent_session_fixation(request, response):
        """
        登录成功后重新生成 session ID，防止会话固定攻击。
        在用户登录成功后调用。
        """
        old_session = request.cookies.get("auth_token")
        if old_session:
            # 使旧 session 失效
            redis_client.delete(f"session:{old_session}")
        # 生成新 session（JWT 本身不可变，通过 refresh token 实现轮换）
        new_token = generate_new_token()
        set_secure_auth_cookie(response, new_token)
        logger.info("[Session] 会话已轮换（防固定）")

    @staticmethod
    def check_idle_timeout(last_activity: int, timeout_seconds: int = 1800) -> bool:
        """
        检查用户是否空闲超时
        默认超时时间：30 分钟（1800 秒）
        """
        return time.time() - last_activity > timeout_seconds
```

### 9.8 数据传输安全

- 所有微信 API 调用使用 HTTPS（httpx 默认强制 HTTPS）
- 回调 URL 必须配置为 HTTPS
- 微信回调中携带的敏感信息（code、state）不在 URL 参数中二次传播
- 服务器端使用环境变量管理密钥（appid/secret），不硬编码在代码中

---

## 十、开发与测试注意事项

### 10.1 开发环境测试

- 使用微信开放平台测试号进行开发调试
- 回调地址可使用内网穿透工具（如 ngrok）暴露到公网
- 开发验证码 `888888` 可直接用于绑定流程测试

### 10.2 待办项

- [ ] 微信开放平台网站应用审核通过后，获取正式 appid/secret
- [ ] 配置正式的 redirect_uri（需与审核时提交的域名一致）
- [ ] 配置消息推送 URL 用于接收授权变更事件
- [ ] 将 IP 加入微信开放平台白名单
- [ ] 生产环境部署前测试完整扫码登录流程
- [ ] 验证用户授权撤回后的账号处理逻辑

### 10.3 相关文档链接

- [网站应用微信登录开发指南](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html)
- [授权后接口调用（UnionID）](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Authorized_Interface_Calling_UnionID.html)
- [授权用户信息变更](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/authorization_change.html)
- [获取普通 access_token](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_PC_APIs/getaccesstoken.html)
- [消息推送服务器配置](https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/message_push)
