"""
Unit tests for the current quantclaw_receiver/utils.py helpers.

说明：
- 这个文件测的是当前 main.py 主线使用的 quantclaw_receiver/utils.py。
- 不依赖真实 PostgreSQL。
- 不需要启动 main.py。
- 不需要真实设备。
- 主要覆盖 MAC 标准化、签名、时间、payload 解析、默认值补齐、设备行转换等工具函数。

运行：
    python -m pytest tests/test_main_quantclaw_utils.py -q
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from quantclaw_receiver import utils


# =========================
# Signature helpers
# =========================

def test_make_sign_generates_expected_hmac_sha256():
    method = "POST"
    path = "/api/device/heartbeat"
    timestamp = "2026-06-01T16:31:00Z"
    body = b'{"mac":"AA:BB:CC:DD:EE:01"}'
    secret = "unit-secret"

    body_sha256 = hashlib.sha256(body).hexdigest()
    payload = f"{method}\n{path}\n{timestamp}\n{body_sha256}"
    expected = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert utils.make_sign(method, path, timestamp, body, secret) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("sha256=ABCDEF", "abcdef"),
        ("SHA256=ABCDEF", "abcdef"),
        ("  abcDEF  ", "abcdef"),
    ],
)
def test_normalize_signature(raw, expected):
    assert utils.normalize_signature(raw) == expected


# =========================
# Time helpers
# =========================

def test_parse_utc_timestamp_accepts_z_suffix():
    dt = utils.parse_utc_timestamp("2026-06-01T16:31:00Z")

    assert dt == datetime(2026, 6, 1, 16, 31, 0, tzinfo=timezone.utc)


def test_parse_utc_timestamp_accepts_naive_datetime_string_as_utc():
    dt = utils.parse_utc_timestamp("2026-06-01T16:31:00")

    assert dt == datetime(2026, 6, 1, 16, 31, 0, tzinfo=timezone.utc)


def test_parse_utc_timestamp_returns_none_for_invalid_value():
    assert utils.parse_utc_timestamp("not-a-time") is None
    assert utils.parse_utc_timestamp(None) is None


def test_server_time_str_uses_utc_z_format():
    value = utils.server_time_str()

    assert value.endswith("Z")
    assert utils.parse_server_time(value) is not None


def test_parse_server_time_handles_datetime_and_string():
    naive = datetime(2026, 6, 1, 16, 31, 0)
    aware = datetime(2026, 6, 1, 16, 31, 0, tzinfo=timezone.utc)
    text = "2026-06-01T16:31:00Z"

    assert utils.parse_server_time(naive) == aware
    assert utils.parse_server_time(aware) == aware
    assert utils.parse_server_time(text) == aware


def test_format_server_time_returns_empty_for_invalid_value():
    assert utils.format_server_time("invalid") == ""


def test_format_server_time_normalizes_datetime_to_z_string():
    dt = datetime(2026, 6, 1, 16, 31, 0, tzinfo=timezone.utc)

    assert utils.format_server_time(dt) == "2026-06-01T16:31:00Z"


# =========================
# MAC helpers
# =========================

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("AA:BB:CC:DD:EE:FF", "aa:bb:cc:dd:ee:ff"),
        ("AA-BB-CC-DD-EE-FF", "aa:bb:cc:dd:ee:ff"),
        ("AABBCCDDEEFF", "aa:bb:cc:dd:ee:ff"),
        ("aa bb cc dd ee ff", "aa:bb:cc:dd:ee:ff"),
        ("aa_bb_cc_dd_ee_ff", "aa:bb:cc:dd:ee:ff"),
        ("aabb.ccdd.eeff", "aa:bb:cc:dd:ee:ff"),
        ("  AA:BB:CC:DD:EE:FF  ", "aa:bb:cc:dd:ee:ff"),
    ],
)
def test_normalize_mac_accepts_common_formats(raw, expected):
    assert utils.normalize_mac(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        None,
        123,
        "",
        "not-a-mac",
        "AA:BB:CC:DD:EE",
        "GG:BB:CC:DD:EE:FF",
        "00:00:00:00:00:00",
    ],
)
def test_normalize_mac_rejects_invalid_values(raw):
    assert utils.normalize_mac(raw) is None


def test_mac_from_ip_is_stable_and_locally_administered_unicast():
    mac1 = utils.mac_from_ip("192.168.1.100")
    mac2 = utils.mac_from_ip("192.168.1.100")
    mac3 = utils.mac_from_ip("192.168.1.101")

    assert mac1 == mac2
    assert mac1 != mac3
    assert utils.normalize_mac(mac1) == mac1

    first_octet = int(mac1.split(":")[0], 16)
    assert first_octet & 0x02 == 0x02  # locally administered
    assert first_octet & 0x01 == 0x00  # unicast


def test_extract_macs_finds_unique_normalized_macs_from_nested_value():
    value = {
        "primary": "AA:BB:CC:DD:EE:01",
        "nested": {
            "text": "seen aa:bb:cc:dd:ee:01 and 11:22:33:44:55:66"
        },
    }

    assert utils.extract_macs(value) == [
        "aa:bb:cc:dd:ee:01",
        "11:22:33:44:55:66",
    ]


# =========================
# Primitive parsing helpers
# =========================

@pytest.mark.parametrize(
    "raw, expected",
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        ("true", True),
        ("yes", True),
        ("online", True),
        ("enabled", True),
        ("false", False),
        ("no", False),
        ("offline", False),
        ("disabled", False),
        ("", False),
        (["yes"], True),
        ([""], False),
    ],
)
def test_parse_bool_common_values(raw, expected):
    assert utils.parse_bool(raw, default=False) is expected


def test_parse_bool_returns_default_for_unknown_value():
    assert utils.parse_bool("unknown", default=True) is True
    assert utils.parse_bool("unknown", default=False) is False


@pytest.mark.parametrize(
    "raw, default, expected",
    [
        ("123", 0, 123),
        (123, 0, 123),
        (None, 7, 7),
        ("bad", 7, 7),
    ],
)
def test_as_int(raw, default, expected):
    assert utils.as_int(raw, default=default) == expected


def test_first_value_returns_first_item_for_list():
    assert utils.first_value(["a", "b"]) == "a"
    assert utils.first_value([]) == ""
    assert utils.first_value("x") == "x"


def test_pick_returns_first_non_empty_value():
    payload = {
        "a": "",
        "b": None,
        "c": "value",
        "d": "later",
    }

    assert utils.pick(payload, "a", "b", "c", "d", default="fallback") == "value"
    assert utils.pick(payload, "missing", default="fallback") == "fallback"


# =========================
# Request body / header helpers
# =========================

def test_parse_text_body_parses_json_object():
    result = utils.parse_text_body(b'{"mac":"AA:BB:CC:DD:EE:01","status":"online"}')

    assert result == {"mac": "AA:BB:CC:DD:EE:01", "status": "online"}


def test_parse_text_body_wraps_json_non_object_as_payload():
    assert utils.parse_text_body(b'["a","b"]') == {"payload": ["a", "b"]}
    assert utils.parse_text_body(b'"hello"') == {"payload": "hello"}


def test_parse_text_body_parses_form_encoded_text():
    result = utils.parse_text_body(b"mac=AA%3ABB%3ACC%3ADD%3AEE%3A01&status=online")

    assert result == {
        "mac": "AA:BB:CC:DD:EE:01",
        "status": "online",
    }


def test_parse_text_body_falls_back_to_payload_text():
    assert utils.parse_text_body(b"plain text body") == {"payload": "plain text body"}


def test_parse_text_body_empty_returns_empty_dict():
    assert utils.parse_text_body(b"") == {}
    assert utils.parse_text_body(b"   ") == {}


def test_client_ip_from_headers_prefers_device_ip_then_forwarded_ip():
    assert utils.client_ip_from_headers({"x-device-ip": "10.0.0.8"}, "127.0.0.1") == "10.0.0.8"
    assert utils.client_ip_from_headers({"x-forwarded-for": "10.0.0.9, 10.0.0.10"}, "127.0.0.1") == "10.0.0.9"
    assert utils.client_ip_from_headers({"x-real-ip": "10.0.0.11"}, "127.0.0.1") == "10.0.0.11"
    assert utils.client_ip_from_headers({}, "127.0.0.1") == "127.0.0.1"


# =========================
# Payload normalization
# =========================

def test_normalize_payload_defaults_for_register_with_aliases(monkeypatch):
    monkeypatch.setattr(utils, "LOCAL_IPV4_ADDRS", {"127.0.0.1", "0.0.0.0"})

    raw_payload = {
        "MAC": "AA-BB-CC-DD-EE-01",
        "host": "unit-device",
        "deviceModel": "QuantClaw-Test",
        "firmware_version": "1.2.3",
        "last_ssid": "unit-wifi",
        "device_ip": "192.168.1.200",
        "ttyd": "enabled",
        "ttyd_port": "7682",
        "mdns": "unit-device.local",
        "http_port": "8080",
        "access_scope": "lan",
    }

    mac, payload = utils.normalize_payload_defaults(
        "/api/device/register",
        raw_payload,
        client_ip="192.168.1.10",
    )

    assert mac == "aa:bb:cc:dd:ee:01"
    assert payload["mac"] == "aa:bb:cc:dd:ee:01"
    assert payload["hostname"] == "unit-device"
    assert payload["model"] == "QuantClaw-Test"
    assert payload["firmwareVersion"] == "1.2.3"
    assert payload["ssid"] == "unit-wifi"
    assert payload["ip"] == "192.168.1.200"
    assert payload["ttydEnabled"] is True
    assert payload["ttydPort"] == 7682
    assert payload["mdnsHost"] == "unit-device.local"
    assert payload["httpPort"] == 8080
    assert payload["accessScope"] == "lan"
    assert payload["_observedMacs"][0] == "aa:bb:cc:dd:ee:01"
    assert payload["timestamp"]


def test_normalize_payload_defaults_for_register_generates_mac_from_ip_when_mac_missing(monkeypatch):
    monkeypatch.setattr(utils, "LOCAL_IPV4_ADDRS", {"127.0.0.1", "0.0.0.0"})

    mac, payload = utils.normalize_payload_defaults(
        "/api/device/register",
        {"ip": "192.168.1.201"},
        client_ip="192.168.1.10",
    )

    assert mac == utils.mac_from_ip("192.168.1.201")
    assert payload["mac"] == mac
    assert payload["hostname"] == "device-192-168-1-201"
    assert payload["model"] == ""


def test_normalize_payload_defaults_replaces_local_ip_with_real_client_ip(monkeypatch):
    monkeypatch.setattr(utils, "LOCAL_IPV4_ADDRS", {"127.0.0.1", "0.0.0.0"})

    mac, payload = utils.normalize_payload_defaults(
        "/api/device/register",
        {"mac": "AA:BB:CC:DD:EE:02", "ip": "127.0.0.1"},
        client_ip="192.168.1.55",
    )

    assert mac == "aa:bb:cc:dd:ee:02"
    assert payload["ip"] == "192.168.1.55"


def test_normalize_payload_defaults_for_heartbeat_sets_status_and_internet(monkeypatch):
    monkeypatch.setattr(utils, "LOCAL_IPV4_ADDRS", {"127.0.0.1", "0.0.0.0"})

    mac, payload = utils.normalize_payload_defaults(
        "/api/device/heartbeat",
        {
            "macAddress": "AA:BB:CC:DD:EE:03",
            "lastIp": "192.168.1.203",
            "internet": "yes",
            "state": "online",
            "firmware": "2.0.0",
            "ttydEnabled": "true",
        },
        client_ip="192.168.1.10",
    )

    assert mac == "aa:bb:cc:dd:ee:03"
    assert payload["internetAvailable"] is True
    assert payload["status"] == "online"
    assert payload["firmwareVersion"] == "2.0.0"
    assert payload["ttydEnabled"] is True
    assert payload["ttydPort"] == 7681
    assert payload["httpPort"] == 80


def test_normalize_payload_defaults_keeps_interfaces_list(monkeypatch):
    monkeypatch.setattr(utils, "LOCAL_IPV4_ADDRS", {"127.0.0.1", "0.0.0.0"})

    interfaces = [{"name": "wlan0", "ip": "192.168.1.204"}]
    _, payload = utils.normalize_payload_defaults(
        "/api/device/heartbeat",
        {
            "mac": "AA:BB:CC:DD:EE:04",
            "ip": "192.168.1.204",
            "interfaces": interfaces,
        },
        client_ip="192.168.1.10",
    )

    assert payload["interfaces"] == interfaces


def test_normalize_payload_defaults_non_list_interfaces_becomes_empty_list(monkeypatch):
    monkeypatch.setattr(utils, "LOCAL_IPV4_ADDRS", {"127.0.0.1", "0.0.0.0"})

    _, payload = utils.normalize_payload_defaults(
        "/api/device/heartbeat",
        {
            "mac": "AA:BB:CC:DD:EE:05",
            "ip": "192.168.1.205",
            "interfaces": "not-a-list",
        },
        client_ip="192.168.1.10",
    )

    assert payload["interfaces"] == []


# =========================
# Row conversion
# =========================

def make_device_row(last_seen_at):
    return {
        "mac": "aa:bb:cc:dd:ee:01",
        "phone": "19900000001",
        "hostname": "unit-device",
        "model": "QuantClaw-Test",
        "firmware_version": "1.0.0",
        "ip": "192.168.1.100",
        "ssid": "unit-wifi",
        "internet_available": True,
        "status": "online",
        "last_seen_at": last_seen_at,
        "ttyd_enabled": True,
        "ttyd_port": 7681,
        "mdns_host": "unit-device.local",
        "http_port": 80,
        "access_scope": "lan",
    }


def test_row_to_device_marks_recent_heartbeat_online():
    now = datetime(2026, 6, 1, 16, 40, 0, tzinfo=timezone.utc)
    row = make_device_row(now - timedelta(seconds=60))

    device = utils.row_to_device(row, now)

    assert device["isOnline"] is True
    assert device["status"] == "online"
    assert device["lastIp"] == "192.168.1.100"
    assert device["lastSsid"] == "unit-wifi"
    assert device["internetAvailable"] is True
    assert device["ttydEnabled"] is True
    assert device["httpUrl"] == "http://192.168.1.100:80"
    assert device["mdnsUrl"] == "http://unit-device.local/"
    assert device["ttydUrl"] == "http://192.168.1.100:7681"
    assert device["ssh"] == "ssh quant@192.168.1.100"
    assert device["sshMdns"] == "ssh quant@unit-device.local"


def test_row_to_device_marks_stale_heartbeat_offline_even_if_status_online():
    now = datetime(2026, 6, 1, 16, 40, 0, tzinfo=timezone.utc)
    row = make_device_row(now - timedelta(seconds=utils.ONLINE_HEARTBEAT_TIMEOUT_SEC + 1))

    device = utils.row_to_device(row, now)

    assert device["status"] == "online"
    assert device["isOnline"] is False


def test_row_to_device_handles_missing_mdns_host():
    now = datetime(2026, 6, 1, 16, 40, 0, tzinfo=timezone.utc)
    row = make_device_row(now)
    row["mdns_host"] = ""

    device = utils.row_to_device(row, now)

    assert device["mdnsUrl"] == ""
    assert device["sshMdns"] == ""
