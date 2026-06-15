# Device Delete Feature Design

## Goal

设备信息卡片增加删除功能，用户可自行删除已有设备。两步点击确认防止误操作。

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `quantclaw_receiver/database.py` | Edit | 新增 `delete_device(mac)` 方法 |
| `quantclaw_receiver/device_manager.py` | Edit | 新增 `delete_device(mac)` 代理 |
| `main.py` | Edit | 新增 `DELETE /api/devices/{mac}` 路由 |
| `static/js/index.js` | Edit | 卡片底部增加两步确认删除按钮 |

## Backend

### Database Layer (`database.py`)

```python
def delete_device(self, mac: str) -> dict[str, Any]:
    def _delete(conn):
        cur = conn.cursor()
        cur.execute("DELETE FROM devices WHERE mac = %s", (mac,))
        conn.commit()
        return {"deleted": cur.rowcount > 0}
    return self.with_db(_delete)
```

### Manager Layer (`device_manager.py`)

```python
async def delete_device(self, mac: str) -> dict[str, Any]:
    return self.db_manager.delete_device(mac)
```

### API Route (`main.py`)

```python
@app.delete("/api/devices/{mac}", tags=["设备管理"], summary="删除设备")
async def delete_device(
    mac: str,
    user = Depends(require_auth_or_api_key),
    db = Depends(get_db),
):
    result = await device_manager.delete_device(mac)
    return {"code": 0, "message": "ok", "data": result}
```

## Frontend

### Delete Button UI

每张设备卡片 footer 区改为左右布局：
- 左侧：刷新按钮（保持原样）
- 右侧：删除按钮（灰色垃圾桶图标）

两态切换：
- **默认态**：灰底 `<i class="ri-delete-bin-line"></i>` 图标按钮
- **确认态**：红底 + 文字"确认删除"，`confirmTimer` 3 秒后自动复位

### JS Logic

```js
function handleDeleteDevice(mac) {
    // 两次点击检测
    if (pendingDeleteMac === mac) {
        // 第二次点击，执行删除
        clearTimeout(confirmTimer);
        performDelete(mac);
        return;
    }
    // 第一次点击，进入确认态
    pendingDeleteMac = mac;
    confirmTimer = setTimeout(() => { pendingDeleteMac = null; reRender(); }, 3000);
    reRender(); // 刷新卡片外观
}
```

## Constraints

- 删除需认证（复用现有 `require_auth_or_api_key`）
- 两步确认，3 秒超时自动复位
- 删除成功后自动刷新设备列表
- 不改变现有 API 响应格式
