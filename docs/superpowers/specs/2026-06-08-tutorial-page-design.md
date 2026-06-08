# Tutorial Page Design

## Goal

新增"使用教程"页面（`/tutorial`），帮助用户完成配网流程。内容从座舱说明书精简而来，聚焦 5 个配网核心步骤，顶部嵌入 B 站视频。

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `main.py` | Edit | 新增 `/tutorial` 路由 |
| `templates/tutorial.html` | Create | 教程页模板，独立浅色系风格 |
| `static/css/tutorial.css` | Create | 教程页样式 |
| `templates/index.html` | Edit | "使用教程"卡片跳转到 `/tutorial` |

## Page Structure (top to bottom)

### 1. Top Nav

复用 `index.html` 的导航栏结构（白底毛玻璃、sticky、龙虾 logo + 系统名 + 用户区）。

### 2. Video Section

嵌入 B 站播放器 iframe，可在页面内直接播放：

```html
<iframe src="//player.bilibili.com/player.html?isOutside=true&aid=116714746419798&bvid=BV18KEG6aEAJ&cid=38962661547&p=1"
  scrolling="no" border="0" frameborder="no" framespacing="0" allowfullscreen="true"></iframe>
```

视频区域使用粉色渐变背景卡片包裹，标题"视频教程"。

### 3. Step Cards (5 steps)

每张卡片结构：左侧彩色序号圆 + 右侧标题/说明 + 截图。

| Step | Title | Accent Color | Image |
|------|-------|-------------|-------|
| 1 | 连接设备热点 | #e11d48 (rose) | `1.连接wifi.jpg` |
| 2 | 填写配网信息 | #f97316 (orange) | `2.初次配网.jpg` |
| 3 | 配网成功 | #22c55e (green) | `3.配网成功.jpg` |
| 4 | 进入管理平台 | #3b82f6 (blue) | `4.平台和跳转.jpg` |
| 5 | Hermes 使用界面 | #8b5cf6 (purple) | `5.使用界面.jpg` |

每张卡片内容：
- 步骤标题 + 副标题
- 截图（OSS 外链，`max-width: 100%`，圆角）
- 操作步骤列表（`<ol>`）
- 提示框（浅色背景 + 左边框色条）

### 4. Footer

简洁页脚：`openclawbox © 2026`。

## Route

```python
@app.get("/tutorial", response_class=HTMLResponse, include_in_schema=False)
async def tutorial_page(request: Request):
    return templates.TemplateResponse("tutorial.html", {"request": request})
```

放在 `/setting` 路由附近，不需要鉴权。

## Image URLs

所有图片托管于阿里云 OSS：

1. `https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/1.%E8%BF%9E%E6%8E%A5wifi.jpg`
2. `https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/2.%E5%88%9D%E6%AC%A1%E9%85%8D%E7%BD%91.jpg`
3. `https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/3.%E9%85%8D%E7%BD%91%E6%88%90%E5%8A%9F.jpg`
4. `https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/4.%E5%B9%B3%E5%8F%B0%E5%92%8C%E8%B7%B3%E8%BD%AC.jpg`
5. `https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/5.%E4%BD%BF%E7%94%A8%E7%95%8C%E9%9D%A2.jpg`

## Tech Stack

- Tailwind CSS via CDN
- Remix Icon via CDN (`remixicon@3.5.0`)
- Google Fonts Inter
- Bilibili iframe player
- No JS framework, no build tools

## Constraints

- 独立页面，不继承 `base.html`（保持与 `index.html` 浅色系一致）
- 零 JS 逻辑，纯静态内容
- 不需要登录即可访问
- 不从数据库读取数据，无 API 调用
- 文字从座舱说明书删减，保留配网核心步骤，删掉产品参数/包装清单/DeepSeek 拓展/注意事项/售后
