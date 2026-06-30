"""
/api/phone_search_device 接口单元测试

测试通过手机号查询绑定设备接口的参数校验、错误处理和成功响应。
使用 mock 替代真实数据库调用。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient


# 在 import main 之前 mock 掉数据库连接池和数据库初始化
# 避免启动时连接真实数据库
with patch("login.database._pool", None), \
     patch("login.database.init_db", return_value=None), \
     patch("quantclaw_receiver.database.ThreadedConnectionPool"), \
     patch("quantclaw_receiver.database.DatabaseManager.ensure_schema", return_value=None):

    from main import app


# 模拟 get_devices_list 返回的数据
MOCK_DEVICES_DATA = {
    "scanMode": "loop",
    "scanIntervalSec": 5,
    "pairedCount": 1,
    "pairCount": 1,
    "paired_count": 1,
    "totalKnownCount": 2,
    "pairedDevices": [
        {
            "mac": "b8:27:eb:11:22:33",
            "phone": "19006440712",
            "hostname": "quant-device-1",
            "model": "Raspberry Pi 5",
            "firmwareVersion": "2.1.0",
            "lastIp": "192.168.1.100",
            "lastSsid": "MyWiFi",
            "internetAvailable": True,
            "status": "online",
            "lastSeenAt": "2026-06-12T10:00:00Z",
            "isOnline": True,
            "ttydEnabled": True,
            "ttydPort": 7681,
            "mdnsHost": "quant-1.local",
            "httpPort": 80,
            "accessScope": "lan",
            "httpUrl": "http://192.168.1.100:80",
            "mdnsUrl": "http://quant-1.local/",
            "ttydUrl": "http://192.168.1.100:7681",
            "ssh": "ssh quant@192.168.1.100",
            "sshMdns": "ssh quant@quant-1.local",
        }
    ],
    "devices": [
        {
            "mac": "b8:27:eb:11:22:33",
            "phone": "19006440712",
            "hostname": "quant-device-1",
            "model": "Raspberry Pi 5",
            "firmwareVersion": "2.1.0",
            "lastIp": "192.168.1.100",
            "lastSsid": "MyWiFi",
            "internetAvailable": True,
            "status": "online",
            "lastSeenAt": "2026-06-12T10:00:00Z",
            "isOnline": True,
            "ttydEnabled": True,
            "ttydPort": 7681,
            "mdnsHost": "quant-1.local",
            "httpPort": 80,
            "accessScope": "lan",
            "httpUrl": "http://192.168.1.100:80",
            "mdnsUrl": "http://quant-1.local/",
            "ttydUrl": "http://192.168.1.100:7681",
            "ssh": "ssh quant@192.168.1.100",
            "sshMdns": "ssh quant@quant-1.local",
        },
        {
            "mac": "b8:27:eb:44:55:66",
            "phone": "19006440712",
            "hostname": "quant-device-2",
            "model": "Raspberry Pi 4",
            "firmwareVersion": "1.9.0",
            "lastIp": "192.168.1.101",
            "lastSsid": "MyWiFi",
            "internetAvailable": False,
            "status": "offline",
            "lastSeenAt": "2026-06-10T08:30:00Z",
            "isOnline": False,
            "ttydEnabled": False,
            "ttydPort": 7681,
            "mdnsHost": "quant-2.local",
            "httpPort": 80,
            "accessScope": "lan",
            "httpUrl": "http://192.168.1.101:80",
            "mdnsUrl": "http://quant-2.local/",
            "ttydUrl": "http://192.168.1.101:7681",
            "ssh": "ssh quant@192.168.1.101",
            "sshMdns": "ssh quant@quant-2.local",
        },
    ],
}


MOCK_EMPTY_DATA = {
    "scanMode": "loop",
    "scanIntervalSec": 5,
    "pairedCount": 0,
    "pairCount": 0,
    "paired_count": 0,
    "totalKnownCount": 0,
    "pairedDevices": [],
    "devices": [],
}


class TestPhoneSearchDevice:
    """通过手机号查询绑定设备接口测试"""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """自动 mock device_manager.get_devices_list"""
        patcher = patch("main.device_manager.get_devices_list", new_callable=AsyncMock)
        self.mock_get_devices = patcher.start()
        yield
        patcher.stop()

    def test_success_with_devices(self):
        """正常查询：手机号关联多个设备，应返回完整设备列表"""
        self.mock_get_devices.return_value = MOCK_DEVICES_DATA

        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device?phone=19006440712")

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["message"] == "ok"
        assert data["data"]["totalKnownCount"] == 2
        assert len(data["data"]["devices"]) == 2
        self.mock_get_devices.assert_called_once_with(user_phone="19006440712")

    def test_success_no_devices(self):
        """正常查询：手机号未关联任何设备，应返回空设备列表"""
        self.mock_get_devices.return_value = MOCK_EMPTY_DATA

        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device?phone=19006440712")

        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["message"] == "ok"
        assert data["data"]["totalKnownCount"] == 0
        assert len(data["data"]["devices"]) == 0

    def test_missing_phone_parameter(self):
        """缺少 phone 参数，应返回 422 参数校验错误"""
        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device")

        assert resp.status_code == 422
        data = resp.json()
        assert data["code"] == 422
        assert "phone" in data["message"].lower() or "field required" in data["message"].lower()

    def test_empty_phone_string(self):
        """phone 参数为空字符串，应返回 400 非空校验错误"""
        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device?phone=")

        assert resp.status_code == 400
        data = resp.json()
        assert data["message"] == "手机号不能为空"

    def test_invalid_phone_short(self):
        """手机号不足11位，应返回 400 格式校验错误"""
        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device?phone=1900644071")

        assert resp.status_code == 400
        data = resp.json()
        assert data["message"] == "手机号格式不正确，请输入中国大陆11位手机号"

    def test_invalid_phone_long(self):
        """手机号超过11位，应返回 400 格式校验错误"""
        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device?phone=190064407123")

        assert resp.status_code == 400
        data = resp.json()
        assert data["message"] == "手机号格式不正确，请输入中国大陆11位手机号"

    def test_invalid_phone_wrong_prefix(self):
        """手机号开头不是1[3-9]，应返回 400 格式校验错误"""
        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device?phone=11006440712")

        assert resp.status_code == 400
        data = resp.json()
        assert data["message"] == "手机号格式不正确，请输入中国大陆11位手机号"

    def test_invalid_phone_contains_letters(self):
        """手机号包含非数字字符，应返回 400 格式校验错误"""
        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device?phone=1900644071a")

        assert resp.status_code == 400
        data = resp.json()
        assert data["message"] == "手机号格式不正确，请输入中国大陆11位手机号"

    def test_no_authentication_required(self):
        """接口无认证校验：不传 Cookie 和 API Key 也能正常调用"""
        self.mock_get_devices.return_value = MOCK_EMPTY_DATA

        with TestClient(app) as client:
            # 不传任何认证信息
            resp = client.get("/api/phone_search_device?phone=19006440712")

        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_response_format_consistency(self):
        """返回格式符合项目统一的 API 规范：{code, message, data}"""
        self.mock_get_devices.return_value = MOCK_DEVICES_DATA

        with TestClient(app) as client:
            resp = client.get("/api/phone_search_device?phone=19006440712")

        assert resp.status_code == 200
        body = resp.json()
        assert "code" in body
        assert "message" in body
        assert "data" in body
        assert isinstance(body["code"], int)
        assert isinstance(body["message"], str)
        assert isinstance(body["data"], dict)
