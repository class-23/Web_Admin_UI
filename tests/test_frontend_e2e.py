"""
E2E frontend tests using Playwright.
Tests all pages render correctly, dark theme is applied, and device data appears.
"""
import pytest
from playwright.sync_api import sync_playwright, Page

BASE = "http://localhost:8081"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
    page = ctx.new_page()
    yield page
    ctx.close()


# ---- Theme / Design System ----


def test_dark_theme_css_vars(page: Page):
    """Dark theme CSS custom properties are loaded."""
    page.goto(BASE + "/")
    bg = page.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--bg-deep').trim()"
    )
    accent = page.evaluate(
        "() => getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()"
    )
    assert bg, "missing --bg-deep"
    assert accent, "missing --accent"


def test_grid_dot_background(page: Page):
    """Body has the grid-dot pseudo-element background."""
    page.goto(BASE + "/")
    has_before = page.evaluate("""
        () => {
            const style = getComputedStyle(document.body, '::before');
            return style.backgroundImage.includes('radial-gradient');
        }
    """)
    assert has_before, "body::before should have radial-gradient grid dots"


# ---- Public pages ----


def test_index_page_renders(page: Page):
    """Public device monitor title and content load."""
    page.goto(BASE + "/")
    page.wait_for_selector("text=设备监控", timeout=5000)
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    assert "设备监控" in body
    assert "已注册设备" in body or "在线设备" in body


def test_index_shows_devices(page: Page):
    """Index page displays registered device data from API."""
    page.goto(BASE + "/")
    page.wait_for_selector("text=设备监控", timeout=5000)
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    assert "esp32-sensor-01" in body, f"Expected device data, body snippet: {body[:400]}"


def test_login_page_renders(page: Page):
    """Login page has form fields and correct styling."""
    page.goto(BASE + "/login")
    page.wait_for_selector("text=登录 QuantClaw", timeout=5000)
    assert page.locator("input[type='text']").count() >= 1
    assert page.locator("input[type='password']").count() >= 1
    assert page.locator("button[type='submit']").count() >= 1
    assert page.locator("a[href='/register']").count() >= 1
    assert "配对" not in page.inner_text("body")


def test_register_page_renders(page: Page):
    """Register page has form fields."""
    page.goto(BASE + "/register")
    page.wait_for_selector("text=注册 QuantClaw", timeout=5000)
    assert page.locator("input[type='text']").count() >= 1
    assert page.locator("input[type='email']").count() >= 1
    assert page.locator("input[type='password']").count() >= 2
    assert page.locator("button[type='submit']").count() >= 1


# ---- Auth flow ----


def _login(page: Page):
    """Helper: log in and wait for redirect to /dashboard."""
    page.goto(BASE + "/login")
    page.wait_for_selector("text=登录 QuantClaw", timeout=5000)
    page.fill("input[type='text']", "brucelee_test")
    page.fill("input[type='password']", "test123")
    page.click("button[type='submit']")
    page.wait_for_url("**/dashboard", timeout=5000)


def test_login_redirects_to_dashboard(page: Page):
    """Successful login redirects to /dashboard."""
    _login(page)
    assert "/dashboard" in page.url
    assert "控制面板" in page.inner_text("body")


def test_dashboard_shows_stats(page: Page):
    """Dashboard shows device count stats after login."""
    _login(page)
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    assert "控制面板" in body
    assert "设备总数" in body
    assert "在线设备" in body
    assert "离线设备" in body


def test_dashboard_shows_device_list(page: Page):
    """Dashboard lists devices after login."""
    _login(page)
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    assert "esp32-sensor-01" in body or "rpi-gateway" in body


def test_devices_page_shows_table(page: Page):
    """Devices management page shows table with devices."""
    _login(page)
    page.goto(BASE + "/devices")
    page.wait_for_selector("text=设备管理", timeout=5000)
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    assert "设备管理" in body
    assert "MAC 地址" in body
    assert "esp32-sensor-01" in body


def test_device_detail_page(page: Page):
    """Device detail page shows device info."""
    _login(page)
    page.goto(BASE + "/device/3")
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    assert "设备详情" in body
    assert "esp32-sensor-01" in body
    assert "aa:bb:cc:11:22:33" in body


def test_device_config_page(page: Page):
    """Device config page shows form."""
    _login(page)
    page.goto(BASE + "/config/3")
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    assert "设备配置" in body
    assert "LLM 配置" in body
    assert "WiFi 配置" in body
    assert "保存配置" in body


def test_pair_returns_404(page: Page):
    """Pair route is removed."""
    resp = page.request.get(BASE + "/pair")
    assert resp.status == 404


# ---- Mobile responsive ----


def test_mobile_layout(page: Page):
    """Mobile viewport renders without breaking."""
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(BASE + "/")
    page.wait_for_selector("text=设备监控", timeout=5000)
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    assert "设备监控" in body


# ---- Nav ----


def test_nav_has_no_pair_link(page: Page):
    """Navigation has no pair link."""
    page.goto(BASE + "/")
    page.wait_for_selector("text=QuantClaw", timeout=5000)
    nav_html = page.locator("nav").inner_html()
    assert "pair" not in nav_html.lower()
