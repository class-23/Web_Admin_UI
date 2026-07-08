# Index Page Restyle Design

## Goal

重构 `templates/index.html` 外观样式，对齐 `cankao/index.html` 的视觉设计，功能逻辑完全保留。

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `templates/index.html` | Rewrite | HTML 结构对齐参考页，引用外部 CSS/JS |
| `static/css/index.css` | Create | 样式系统（网格背景、毛玻璃、渐变、卡片、动画） |
| `static/js/index.js` | Create | 从旧 template `<script>` 完整搬迁，逻辑零改动 |

## Visual Structure (4 zones)

### 1. Top Nav (sticky)
- 毛玻璃效果 (`backdrop-blur-md`)
- 左侧: Logo + 系统名
- 右侧: 用户头像 + 用户名 + 退出按钮（由 `checkLoginStatus()` 动态控制显示）

### 2. Device Selector Panel (焦点视觉区)
- 外层彩色阴影光环 + 内层面板（渐变底色）
- 右上角装饰水印图标
- 下拉选择框（由 `updateDeviceSelector()` 驱动）
- 设备详情卡片（名称/IP/状态，由 `updateSelectedDeviceSummary()` 更新）
- 状态提示文案（由 `getActionHint()` 驱动）

### 3. Quick Action Cards (4 cards)
- 控制面板 → `handleControlPanelClick()`
- 终端 → `handleTerminalClick()`
- 文件管理 → `handleFileManagerClick()`
- 教程 → `requireLogin('/login')`
- 禁用态沿用 `action-card-disabled` 样式

### 4. Device Info Cards
- 独立卡片网格（`renderDevices()` 重新生成 HTML）
- 每张卡片: MAC/IP/SSID/型号/固件 + 在线状态 + 刷新按钮

## JS Logic Migration

从 `templates/index.html` 的 `<script>` 块完整搬迁到 `static/js/index.js`，包括:
- `cachedDevices`, `selectedDeviceMac`, `probeInProgress` 状态变量
- `getDisplayDeviceName`, `getSelectedDevice`, `showToast`
- `fetchDevices`, `renderDevices`, `updateDeviceSelector`, `updateActionCards`
- `handleControlPanelClick`, `handleTerminalClick`, `handleFileManagerClick`
- `checkLoginStatus`, `handleLogout`, `requireLogin`
- `init()` 初始化
- 所有辅助函数

模板底部 `<script src="/static/js/index.js"></script>` 引入。

## Tech Stack

- Remix Icon (`remixicon@3.5.0`) via CDN, replaces Lucide
- Tailwind CSS via CDN (unchanged)
- Google Fonts Inter (新增，对齐参考页)
- No additional build tools

## Constraints

- 仅修改外观，不改变任何业务逻辑
- CSS/JS 放在 `static/` 目录，符合项目规范
- 保持与后端 FastAPI 路由的兼容性
