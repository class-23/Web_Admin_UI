# 本次对话修改记录

> 文档记录了本次对话中对项目代码的所有修改内容，包括数据库架构调整、后端代码修改和前端页面调整。

---

## 一、修改概览

| 修改类别 | 涉及文件 | 修改内容 |
|---------|---------|---------|
| 数据库架构 | `login/database.py` | 删除 `miyao_key` 字段 |
| 后端路由 | `login/routers/auth_router.py` | 删除注册时写入 `miyao_key` |
| 前端页面 | `templates/register.html` | 删除密钥输入表单及相关 JS |
| 数据验证 | `login/schemas.py` | 删除 `secret_key` 字段及验证器 |

---

## 二、详细修改记录

### 1. `login/database.py`

**修改目的**：从 `users` 表中移除 `miyao_key` 字段

**修改内容**：

**原始代码（第 63-72 行）：**
```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    miyao_key VARCHAR(100) NOT NULL DEFAULT '',  -- 被删除
    password VARCHAR(255) NOT NULL,
    password_changed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
```

**修改后代码：**
```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    password_changed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
)
```

**新增迁移代码（第 73-84 行）：**
```sql
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'miyao_key'
    ) THEN
        ALTER TABLE users DROP COLUMN miyao_key;
    END IF;
END
$$;
```

---

### 2. `login/routers/auth_router.py`

**修改目的**：注册时不再写入 `miyao_key`

**修改位置**：第 59-62 行

**原始代码：**
```python
cur.execute(
    "INSERT INTO users (phone, username, password, miyao_key) VALUES (%s,%s,%s,%s) RETURNING id",
    (req.phone, req.username, hashed_pw, req.secret_key)
)
```

**修改后代码：**
```python
cur.execute(
    "INSERT INTO users (phone, username, password) VALUES (%s,%s,%s) RETURNING id",
    (req.phone, req.username, hashed_pw)
)
```

---

### 3. `templates/register.html`

**修改目的**：完全移除注册页面中的密钥输入功能

#### 3.1 删除 HTML 表单组（第 328-334 行）

**原始代码：**
```html
<div class="form-group">
  <label>输入你配网时的密钥</label>
  <div class="input-wrapper">
    <input type="text" id="secretKey" placeholder="请输入你配网时的密钥(仅支持数字与字母)" autocomplete="off">
  </div>
  <div id="secretKeyError" class="error-text"></div>
</div>
```

**修改后**：此段代码被完全删除

#### 3.2 删除 JavaScript 变量声明（第 373, 384 行）

**原始代码：**
```javascript
var secretKeyInput = document.getElementById('secretKey');
var secretKeyError = document.getElementById('secretKeyError');
```

**修改后**：此两行被删除

#### 3.3 删除验证函数（第 427-429 行）

**原始代码：**
```javascript
function validateSecretKey(value) {
  return /^[a-zA-Z0-9]+$/.test(value);
}
```

**修改后**：此函数被删除

#### 3.4 删除事件监听器（第 566-580 行）

**原始代码：**
```javascript
secretKeyInput.addEventListener('input', function () {
  var val = secretKeyInput.value;
  if (val && !validateSecretKey(val)) {
    setError(secretKeyError, secretKeyInput, '密钥只能包含数字和字母');
  } else {
    setError(secretKeyError, secretKeyInput, '');
  }
});

secretKeyInput.addEventListener('blur', function () {
  var val = secretKeyInput.value.trim();
  if (val && !validateSecretKey(val)) {
    setError(secretKeyError, secretKeyInput, '密钥只能包含数字和字母');
  }
});
```

**修改后**：此段代码被删除

#### 3.5 删除表单验证逻辑（第 645, 668-676 行）

**原始代码：**
```javascript
var secretKey = secretKeyInput.value.trim();
// ...
if (!secretKey) {
  setError(secretKeyError, secretKeyInput, '请输入注册密钥');
  valid = false;
} else if (!validateSecretKey(secretKey)) {
  setError(secretKeyError, secretKeyInput, '密钥只能包含数字和字母');
  valid = false;
} else {
  setError(secretKeyError, secretKeyInput, '');
}
```

**修改后**：此段代码被删除

#### 3.6 删除请求体中的字段（第 706 行）

**原始代码：**
```javascript
body: JSON.stringify({
  phone: phone,
  username: username,
  code: code,
  secret_key: secretKey,  // 被删除
  password: password,
  confirm_password: confirmPassword
})
```

**修改后代码：**
```javascript
body: JSON.stringify({
  phone: phone,
  username: username,
  code: code,
  password: password,
  confirm_password: confirmPassword
})
```

---

### 4. `login/schemas.py`

**修改目的**：从注册请求模型中移除 `secret_key` 字段及验证器

#### 4.1 删除字段定义（第 21 行）

**原始代码：**
```python
class RegisterRequest(BaseModel):
    phone: str
    username: str
    code: str
    secret_key: str  # 被删除
    password: str
    confirm_password: str
```

**修改后代码：**
```python
class RegisterRequest(BaseModel):
    phone: str
    username: str
    code: str
    password: str
    confirm_password: str
```

#### 4.2 删除验证器（第 46-51 行）

**原始代码：**
```python
@field_validator("secret_key")
@classmethod
def validate_secret_key(cls, v):
    if not re.match(r"^[a-zA-Z0-9]+$", v):
        raise ValueError("密钥只能包含数字和字母")
    return v
```

**修改后**：此验证器被删除

---

## 三、修改汇总

| 文件 | 修改类型 | 影响范围 |
|------|---------|---------|
| `login/database.py` | 表结构修改 | 删除 `miyao_key` 字段，添加迁移逻辑 |
| `login/routers/auth_router.py` | SQL 修改 | INSERT 语句移除 `miyao_key` |
| `templates/register.html` | UI 修改 | 删除密钥输入表单及相关 JS |
| `login/schemas.py` | 数据验证 | 删除 `secret_key` 字段及验证器 |

**总删除行数**：约 50+ 行代码

**修改原则**：仅移除与密钥相关的代码，不影响其他功能模块

---

## 四、验证结果

| 验证项 | 状态 |
|--------|------|
| 应用启动 | ✅ 正常 |
| 数据库连接 | ✅ 正常 |
| 健康检查接口 | ✅ 正常响应 |
| 注册页面 | ✅ 已移除密钥相关内容 |

---

**文档创建时间**：2026-05-22
**文档版本**：v1.0