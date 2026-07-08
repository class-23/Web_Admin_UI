"""
Live API tests for the current main.py runtime.

用途：
- 这个测试文件不是测 app/ 新版架构，而是测你当前通过 `python main.py`
  启动起来的真实 HTTP 服务。
- 运行前请先启动服务：
    python -X utf8 main.py

PowerShell 推荐运行方式：
    $env:MAIN_API_BASE_URL="http://localhost:8082"
    $env:MAIN_API_PHONE="你的已注册手机号"
    $env:MAIN_API_KEY="123quant-speed"
    python -m pytest tests/test_main_live_api.py -q -s

说明：
- 这个测试会注册/更新一台测试设备，MAC 默认为 AA:BB:CC:DD:EE:91。
- 如果你不想污染当前测试设备，可以用 MAIN_TEST_MAC 改一个测试 MAC。
"""

import os
import time

import pytest
import requests


BASE_URL = os.getenv("MAIN_API_BASE_URL", "http://localhost:8082").rstrip("/")
API_KEY = os.getenv("MAIN_API_KEY", "123quant-speed")
PHONE = os.getenv("MAIN_API_PHONE", "").strip()

TEST_MAC = os.getenv("MAIN_TEST_MAC", "AA:BB:CC:DD:EE:91")
TEST_MAC_NORM = TEST_MAC.lower()
TEST_HOSTNAME = os.getenv("MAIN_TEST_HOSTNAME", "pytest-main-api-device")
TEST_IP = os.getenv("MAIN_TEST_IP", "192.168.1.191")


def _json(response: requests.Response) -> dict:
    """把响应解析成 JSON；失败时给出更清楚的报错。"""
    try:
        return response.json()
    except Exception as exc:
        pytest.fail(
            f"Response is not JSON. status={response.status_code}, "
            f"text={response.text[:500]!r}, error={exc}"
        )


def _assert_api_ok(response: requests.Response) -> dict:
    """断言接口 HTTP 状态正常，并且业务 code 为 0。"""
    data = _json(response)
    assert response.status_code == 200, data
    assert data.get("code") == 0, data
    return data


def _find_device(devices_payload: dict, mac: str) -> dict | None:
    """从 /api/devices 返回体里按 MAC 找设备。"""
    data = devices_payload.get("data") or {}
    devices = data.get("devices") or []
    mac_norm = mac.lower()
    for device in devices:
        if str(device.get("mac", "")).lower() == mac_norm:
            return device
    return None


@pytest.fixture(scope="session")
def session() -> requests.Session:
    return requests.Session()


def test_health_endpoint_is_available():
    """测试 main.py 当前服务是否存活，数据库和设备管理器健康检查是否可访问。"""
    response = requests.get(f"{BASE_URL}/api/health", timeout=10)
    data = _json(response)

    assert response.status_code == 200, data
    assert data.get("status") in {"healthy", "degraded"}, data
    assert "database" in data, data
    assert "config" in data, data


def test_device_register_heartbeat_and_devices_flow():
    """
    测试主链路：
    1. 设备注册 /api/device/register
    2. 设备心跳 /api/device/heartbeat
    3. 设备列表 /api/devices?api_key=...&phone=...
    4. 断言设备出现在列表里，并且 isOnline=true
    """
    if not PHONE:
        pytest.skip("请先设置环境变量 MAIN_API_PHONE 为已注册手机号")

    register_payload = {
        "mac": TEST_MAC,
        "hostname": TEST_HOSTNAME,
        "model": "QuantClaw-Pytest",
        "firmwareVersion": "1.0.0",
        "ssid": "pytest-wifi",
        "ip": TEST_IP,
        "ttydEnabled": True,
        "ttydPort": 7681,
        "mdnsHost": "pytest-main-api-device.local",
        "httpPort": 80,
        "accessScope": "lan",
    }

    response = requests.post(
        f"{BASE_URL}/api/device/register",
        json=register_payload,
        timeout=10,
    )
    register_data = _assert_api_ok(response)
    assert register_data["data"]["mac"] == TEST_MAC_NORM, register_data

    heartbeat_payload = {
        "mac": TEST_MAC,
        "hostname": TEST_HOSTNAME,
        "ip": TEST_IP,
        "ssid": "pytest-wifi",
        "internetAvailable": True,
        "status": "online",
        "firmwareVersion": "1.0.0",
        "ttydEnabled": True,
        "ttydPort": 7681,
        "httpPort": 80,
        "accessScope": "lan",
    }

    response = requests.post(
        f"{BASE_URL}/api/device/heartbeat",
        json=heartbeat_payload,
        timeout=10,
    )
    heartbeat_data = _assert_api_ok(response)
    assert heartbeat_data["data"].get("nextHeartbeatIntervalSec") is not None, heartbeat_data

    # 给后端数据库提交一点点时间，通常不需要，但保守起见。
    time.sleep(0.2)

    response = requests.get(
        f"{BASE_URL}/api/devices",
        params={"api_key": API_KEY, "phone": PHONE},
        timeout=10,
    )
    devices_data = _assert_api_ok(response)

    device = _find_device(devices_data, TEST_MAC)
    assert device is not None, devices_data
    assert device["hostname"] == TEST_HOSTNAME, device
    assert device["lastIp"] == TEST_IP, device
    assert device["status"] == "online", device
    assert device["isOnline"] is True, device
    assert device["internetAvailable"] is True, device


def test_cookie_login_and_current_user(session: requests.Session):
    """
    测试 Cookie 鉴权链路：
    1. 用开发验证码 888888 进行短信登录
    2. 后端写入 HttpOnly Cookie
    3. 再请求 /api/current_user，确认能识别当前用户

    这个测试依赖 MAIN_API_PHONE 对应的手机号已经注册。
    """
    if not PHONE:
        pytest.skip("请先设置环境变量 MAIN_API_PHONE 为已注册手机号")

    response = session.post(
        f"{BASE_URL}/api/login-by-sms",
        json={"phone": PHONE, "code": "888888"},
        timeout=10,
    )
    login_data = _assert_api_ok(response)
    assert login_data["message"] == "登录成功", login_data

    response = session.get(f"{BASE_URL}/api/current_user", timeout=10)
    current_user_data = _assert_api_ok(response)
    assert current_user_data["data"] is not None, current_user_data
    assert "username" in current_user_data["data"], current_user_data


def test_devices_endpoint_supports_cookie_auth_if_backend_was_fixed(session: requests.Session):
    """
    测试 /api/devices 是否支持 Cookie 登录态。

    注意：
    - 如果 main.py 里的 /api/devices 仍然是 Depends(verify_api_key_and_phone)，
      这个测试会返回 401。
    - 如果已经改成 Depends(require_auth_or_api_key)，这个测试应该通过。
    """
    if not PHONE:
        pytest.skip("请先设置环境变量 MAIN_API_PHONE 为已注册手机号")

    response = session.post(
        f"{BASE_URL}/api/login-by-sms",
        json={"phone": PHONE, "code": "888888"},
        timeout=10,
    )
    _assert_api_ok(response)

    response = session.get(f"{BASE_URL}/api/devices", timeout=10)
    data = _json(response)

    assert response.status_code == 200, (
        "如果这里是 401，说明 /api/devices 还没有改成 "
        "Depends(require_auth_or_api_key)。当前响应："
        f"{data}"
    )
    assert data.get("code") == 0, data
    assert "devices" in (data.get("data") or {}), data
