# Tutorial Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `/tutorial` 使用教程页面，帮助用户完成 5 步配网流程。

**Architecture:** 纯静态页面，不继承 base.html，与 index.html 共享浅色系设计语言。零 JS 交互，B 站视频通过 iframe 嵌入。

**Tech Stack:** Tailwind CSS CDN + Remix Icon CDN + Google Fonts Inter + Bilibili iframe player

---

### Task 1: Create tutorial CSS

**Files:**
- Create: `static/css/tutorial.css`

- [ ] **Step 1: Write the CSS file**

```css
/* Tutorial page styles — light theme, matching index.html */
/* Step card accent borders and hover effects */

.tutorial-container {
  max-width: 896px;  /* max-w-4xl */
  margin: 0 auto;
}

.video-wrapper {
  position: relative;
  padding-bottom: 56.25%;  /* 16:9 */
  height: 0;
  overflow: hidden;
  border-radius: 1rem;
}

.video-wrapper iframe {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 1rem;
}

.step-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
  padding: 1.5rem;
  display: flex;
  gap: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.step-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 20px rgba(0,0,0,0.04);
}

.step-number {
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
  flex-shrink: 0;
}

.step-image {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: #f8fafc;
  border-radius: 0.75rem;
  text-align: center;
}

.step-image img {
  max-width: 100%;
  max-height: 360px;
  object-fit: contain;
  border-radius: 0.5rem;
}

.step-instructions ol {
  padding-left: 1.25rem;
  line-height: 1.9;
  color: #475569;
  font-size: 0.875rem;
}

.step-instructions li {
  margin-bottom: 0.25rem;
}

.step-tip {
  margin-top: 0.75rem;
  padding: 0.625rem 0.875rem;
  background: #fefce8;
  border-left: 3px solid;
  border-radius: 0 0.5rem 0.5rem 0;
  font-size: 0.8125rem;
  color: #78716c;
}

@media (max-width: 640px) {
  .step-card {
    flex-direction: column;
    padding: 1rem;
  }
}
```

- [ ] **Step 2: Verify file created**

Run: `ls -la static/css/tutorial.css`

- [ ] **Step 3: Commit**

```bash
git add static/css/tutorial.css
git commit -m "feat: add tutorial page CSS"
```

---

### Task 2: Create tutorial HTML template

**Files:**
- Create: `templates/tutorial.html`

- [ ] **Step 1: Write the HTML template**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>使用教程 - 龙虾盒子</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/static/css/tutorial.css">
</head>
<body class="text-slate-800 antialiased min-h-screen flex flex-col bg-slate-50">

    <div class="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-rose-400 via-orange-300 to-rose-400 z-50"></div>

    <!-- Top Nav -->
    <nav class="bg-white/70 backdrop-blur-md shadow-sm border-b border-slate-200/60 sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between h-16 items-center">
                <div class="flex items-center gap-3">
                    <a href="/" class="flex items-center gap-3 no-underline">
                        <div class="w-10 h-10 bg-gradient-to-br from-rose-50 to-rose-100 text-rose-500 rounded-xl flex items-center justify-center text-xl shadow-[0_2px_10px_-3px_rgba(225,29,72,0.3)] border border-rose-200/50">
                            🦞
                        </div>
                        <span class="font-bold text-lg tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-slate-800 to-slate-500">
                            龙虾盒子管理后台
                        </span>
                    </a>
                </div>
                <div class="flex items-center gap-3">
                    <a href="/" class="flex items-center gap-1.5 text-slate-500 hover:text-rose-500 font-medium transition-colors text-sm">
                        <i class="ri-arrow-left-line"></i>
                        返回首页
                    </a>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <main class="flex-1 px-4 sm:px-6 lg:px-8 py-8 md:py-10">
        <div class="tutorial-container">

            <!-- Page Header -->
            <div class="mb-8 text-center">
                <div class="inline-flex items-center gap-2 px-4 py-1.5 bg-rose-50 border border-rose-200 rounded-full text-sm font-bold text-rose-500 mb-4">
                    <i class="ri-book-read-line"></i> 使用教程
                </div>
                <h1 class="text-3xl font-bold text-slate-800 mb-2">快速配网指南</h1>
                <p class="text-slate-500">跟随以下步骤，几分钟即可完成设备配网，开始使用龙虾盒子</p>
            </div>

            <!-- Video Section -->
            <section class="mb-10">
                <div class="bg-gradient-to-br from-rose-50 to-orange-50 rounded-2xl p-6 md:p-8 border border-rose-100">
                    <div class="flex items-center gap-3 mb-4">
                        <div class="w-10 h-10 bg-rose-500 rounded-xl flex items-center justify-center">
                            <i class="ri-play-circle-line text-white text-xl"></i>
                        </div>
                        <div>
                            <h2 class="font-bold text-slate-800 text-lg">视频教程</h2>
                            <p class="text-sm text-slate-500">观看配网操作演示</p>
                        </div>
                    </div>
                    <div class="video-wrapper shadow-lg">
                        <iframe src="//player.bilibili.com/player.html?isOutside=true&aid=116714746419798&bvid=BV18KEG6aEAJ&cid=38962661547&p=1" scrolling="no" border="0" frameborder="no" framespacing="0" allowfullscreen="true"></iframe>
                    </div>
                </div>
            </section>

            <!-- Step Cards -->
            <section>
                <h2 class="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
                    <span class="w-1.5 h-5 bg-rose-400 rounded-full"></span> 配网步骤
                </h2>
                <div class="flex flex-col gap-5">

                    <!-- Step 1: 连接设备热点 -->
                    <div class="step-card" style="border-left: 4px solid #e11d48;">
                        <div class="step-number" style="background: #e11d48;">1</div>
                        <div class="flex-1 min-w-0">
                            <h3 class="font-bold text-slate-800 text-lg mb-1">连接设备热点</h3>
                            <p class="text-sm text-slate-500 mb-1">手机或电脑连接 Quanthermes Setup</p>
                            <div class="step-image">
                                <img src="https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/1.%E8%BF%9E%E6%8E%A5wifi.jpg" alt="连接WiFi热点" loading="lazy">
                            </div>
                            <div class="step-instructions mt-2">
                                <p class="text-sm text-slate-600 mb-2">设备接通电源后自动进入<strong>AP 模式</strong>，请按以下步骤操作：</p>
                                <ol>
                                    <li>打开手机或电脑的 WiFi 设置，搜索可用网络。</li>
                                    <li>找到名为 <strong>"Quanthermes Setup"</strong> 的 WiFi 热点，点击连接。</li>
                                    <li>连接成功后，打开浏览器，在地址栏输入 <strong>192.168.4.1</strong> 进入配网页面。</li>
                                </ol>
                                <div class="step-tip border-l-rose-400">
                                    <i class="ri-lightbulb-line text-rose-400 mr-1"></i> 如果搜不到热点，请确认设备已接通电源。热点在设备开机后约 30 秒内出现。
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Step 2: 填写配网信息 -->
                    <div class="step-card" style="border-left: 4px solid #f97316;">
                        <div class="step-number" style="background: #f97316;">2</div>
                        <div class="flex-1 min-w-0">
                            <h3 class="font-bold text-slate-800 text-lg mb-1">填写配网信息</h3>
                            <p class="text-sm text-slate-500 mb-1">输入 Wi-Fi 名称、密码及手机号</p>
                            <div class="step-image">
                                <img src="https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/2.%E5%88%9D%E6%AC%A1%E9%85%8D%E7%BD%91.jpg" alt="初次配网" loading="lazy">
                            </div>
                            <div class="step-instructions mt-2">
                                <p class="text-sm text-slate-600 mb-2">进入配网界面后，请按照图中标注填写：</p>
                                <ol>
                                    <li>在 <strong>Wi-Fi 名称</strong>栏中选择或输入您家中/公司的无线网络名称。</li>
                                    <li>在 <strong>密码</strong>栏中输入对应的 Wi-Fi 密码。</li>
                                    <li>在 <strong>电话号码</strong>栏中输入您的手机号（用于设备绑定）。</li>
                                    <li>确认信息无误后，点击<strong>"保存并连接"</strong>按钮。</li>
                                </ol>
                                <div class="step-tip border-l-orange-400">
                                    <i class="ri-lightbulb-line text-orange-400 mr-1"></i> 请确保 Wi-Fi 密码输入正确，否则设备将无法连接网络。等待 5 至 10 秒即可完成。
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Step 3: 配网成功 -->
                    <div class="step-card" style="border-left: 4px solid #22c55e;">
                        <div class="step-number" style="background: #22c55e;">3</div>
                        <div class="flex-1 min-w-0">
                            <h3 class="font-bold text-slate-800 text-lg mb-1">配网成功</h3>
                            <p class="text-sm text-slate-500 mb-1">设备网络切换提醒</p>
                            <div class="step-image">
                                <img src="https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/3.%E9%85%8D%E7%BD%91%E6%88%90%E5%8A%9F.jpg" alt="配网成功" loading="lazy">
                            </div>
                            <div class="step-instructions mt-2">
                                <p class="text-sm text-slate-600 mb-2">点击"保存并连接"后等待 5 至 10 秒，会出现以下变化：</p>
                                <ol>
                                    <li>页面显示<strong>设备网络切换提醒</strong>，表示设备正在切换到您配置的网络。</li>
                                    <li>您的手机或电脑的 WiFi 会自动<strong>切回到家中/公司的网络</strong>。</li>
                                    <li>以上现象即代表<strong>配网成功</strong>。</li>
                                </ol>
                                <div class="step-tip border-l-green-400">
                                    <i class="ri-lightbulb-line text-green-400 mr-1"></i> 配网成功后，设备会自动与您的账户绑定。后续所有管理操作均通过云端后台完成，无需重复配网。
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Step 4: 进入管理平台 -->
                    <div class="step-card" style="border-left: 4px solid #3b82f6;">
                        <div class="step-number" style="background: #3b82f6;">4</div>
                        <div class="flex-1 min-w-0">
                            <h3 class="font-bold text-slate-800 text-lg mb-1">进入管理平台</h3>
                            <p class="text-sm text-slate-500 mb-1">访问 keli.quantclaw.vip</p>
                            <div class="step-image">
                                <img src="https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/4.%E5%B9%B3%E5%8F%B0%E5%92%8C%E8%B7%B3%E8%BD%AC.jpg" alt="管理平台" loading="lazy">
                            </div>
                            <div class="step-instructions mt-2">
                                <p class="text-sm text-slate-600 mb-2">配网成功后，在电脑或手机浏览器中进行以下操作：</p>
                                <ol>
                                    <li>在浏览器地址栏输入 <strong>https://keli.quantclaw.vip</strong> 进入设备管理平台。</li>
                                    <li>在管理平台右上角选择<strong>要使用的设备</strong>。</li>
                                    <li>选择好设备后，点击右下角的<strong>"控制面板"</strong>按钮。</li>
                                </ol>
                                <div class="step-tip border-l-blue-400">
                                    <i class="ri-lightbulb-line text-blue-400 mr-1"></i> 请确保电脑/手机与设备处于同一网络环境下，否则无法正常访问管理平台。
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Step 5: Hermes 使用界面 -->
                    <div class="step-card" style="border-left: 4px solid #8b5cf6;">
                        <div class="step-number" style="background: #8b5cf6;">5</div>
                        <div class="flex-1 min-w-0">
                            <h3 class="font-bold text-slate-800 text-lg mb-1">Hermes 使用界面</h3>
                            <p class="text-sm text-slate-500 mb-1">进入智能管理界面</p>
                            <div class="step-image">
                                <img src="https://tangledup-ai-staging.oss-cn-shanghai.aliyuncs.com/H5_projectt/LongXiaZuoCang/specification/5.%E4%BD%BF%E7%94%A8%E7%95%8C%E9%9D%A2.jpg" alt="Hermes使用界面" loading="lazy">
                            </div>
                            <div class="step-instructions mt-2">
                                <p class="text-sm text-slate-600 mb-2">点击"控制面板"后，即可进入 <strong>Hermes</strong> 使用界面：</p>
                                <ol>
                                    <li>界面展示了设备的管理与对话功能区。</li>
                                    <li>在此可以管理设备模型、查看对话记录等。</li>
                                    <li>如需为设备配置 AI 模型，请参考后续拓展教程。</li>
                                </ol>
                                <div class="step-tip border-l-purple-400">
                                    <i class="ri-lightbulb-line text-purple-400 mr-1"></i> Hermes 是量迹座舱的核心管理界面，后续所有模型配置与对话均在此完成。
                                </div>
                            </div>
                        </div>
                    </div>

                </div>
            </section>

        </div>
    </main>

    <!-- Footer -->
    <footer class="mt-auto py-8 text-center text-slate-400 text-sm font-medium border-t border-slate-200">
        <p>openclawbox &copy; 2026</p>
    </footer>

</body>
</html>
```

- [ ] **Step 2: Verify file created**

Run: `ls -la templates/tutorial.html`

- [ ] **Step 3: Commit**

```bash
git add templates/tutorial.html
git commit -m "feat: add tutorial page template with video and 5 step cards"
```

---

### Task 3: Add /tutorial route

**Files:**
- Modify: `main.py` — insert new route after `/setting` route (after line 315)

- [ ] **Step 1: Add the route**

Insert after line 315 (after the `/setting` route's closing `"""`):

```python


@app.get("/tutorial", response_class=HTMLResponse, include_in_schema=False)
async def tutorial_page():
    with open("templates/tutorial.html", "r", encoding="utf-8") as f:
        return f.read()
```

Note: 放在 `/setting` 和 `/file_manager` 路由之间，与现有路由风格一致。

- [ ] **Step 2: Verify route by starting server and curling**

Run: `curl -s http://localhost:8000/tutorial | head -5`
Expected: 返回 HTML，包含 `<!DOCTYPE html>` 和 `<title>使用教程`

(如果服务已在跑，先 `pkill -f uvicorn` 再重启)

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add /tutorial route"
```

---

### Task 4: Update index.html "使用教程" card

**Files:**
- Modify: `templates/index.html:166-175`

- [ ] **Step 1: Replace the card**

Replace lines 166-175 (the "使用教程" button card):

Old:
```html
                <button onclick="requireLogin('/login')" class="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/80 hover:-translate-y-1.5 hover:shadow-xl hover:shadow-emerald-500/10 hover:border-emerald-200 transition-all cursor-pointer group relative overflow-hidden text-left w-full">
                    <div class="absolute top-4 right-4 text-[10px] font-bold bg-slate-100 text-slate-500 px-2 py-1 rounded-lg border border-slate-200/50">预留功能</div>
                    <div class="w-12 h-12 bg-emerald-50 rounded-2xl flex items-center justify-center mb-5 group-hover:bg-emerald-500 group-hover:shadow-lg group-hover:shadow-emerald-500/30 transition-all duration-300">
                        <i class="ri-book-read-line text-2xl text-emerald-500 group-hover:text-white transition-colors"></i>
                    </div>
                    <h3 class="font-bold text-slate-800 mb-2 text-lg">使用教程</h3>
                    <p class="text-xs font-medium text-slate-500 leading-relaxed">
                        新手使用指南、常见问题解答<br>及设备高级玩法探秘
                    </p>
                </button>
```

New:
```html
                <button onclick="window.location.href='/tutorial'" class="bg-white rounded-2xl p-6 shadow-sm border border-slate-200/80 hover:-translate-y-1.5 hover:shadow-xl hover:shadow-emerald-500/10 hover:border-emerald-200 transition-all cursor-pointer group text-left w-full">
                    <div class="w-12 h-12 bg-emerald-50 rounded-2xl flex items-center justify-center mb-5 group-hover:bg-emerald-500 group-hover:shadow-lg group-hover:shadow-emerald-500/30 transition-all duration-300">
                        <i class="ri-book-read-line text-2xl text-emerald-500 group-hover:text-white transition-colors"></i>
                    </div>
                    <h3 class="font-bold text-slate-800 mb-2 text-lg">使用教程</h3>
                    <p class="text-xs font-medium text-slate-500 leading-relaxed">
                        新手使用指南、常见问题解答<br>及设备高级玩法探秘
                    </p>
                </button>
```

Changes: removed `"预留功能"` badge, removed `relative overflow-hidden`, changed `onclick` to navigate to `/tutorial`.

- [ ] **Step 2: Verify**

Run: `grep -n "tutorial" templates/index.html`
Expected: Shows the onclick line with `/tutorial`

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: link tutorial card to /tutorial page"
```

---

### Task 5: End-to-end verification

- [ ] **Step 1: Start server**

```bash
cd F:/DieJiaTai/Web_Admin_UI-1 && python main.py
```

- [ ] **Step 2: Open browser and test**

Open http://localhost:8000 and verify:
1. 首页"使用教程"卡片不再显示"预留功能"标签
2. 点击"使用教程"卡片 → 跳转到 `/tutorial`
3. 教程页视频 iframe 正常加载
4. 5 张步骤卡片 + 图片完整显示
5. "返回首页"按钮可用

- [ ] **Step 3: Verify unauthenticated access**

Open http://localhost:8000/tutorial directly in incognito — 应该能直接访问，不需要登录。

- [ ] **Step 4: Final commit (if any fixes)**

```bash
git add -A
git commit -m "chore: final verification fixes for tutorial page"
```
