"""
MAC 地址工具函数测试
"""
import pytest
from app.utils.quantclaw_receiver.utils import normalize_mac, mac_from_ip


class TestNormalizeMac:
    """MAC 地址标准化测试"""

    def test_valid_colon_mac(self):
        assert normalize_mac("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:dd:ee:ff"

    def test_valid_dash_mac(self):
        assert normalize_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"

    def test_valid_no_separator_mac(self):
        assert normalize_mac("AABBCCDDEEFF") == "aa:bb:cc:dd:ee:ff"

    def test_uppercase_normalized(self):
        assert normalize_mac("AA:BB:CC:DD:EE:FF") == "aa:bb:cc:dd:ee:ff"

    def test_invalid_mac_returns_none(self):
        assert normalize_mac("invalid") is None

    def test_empty_mac_returns_none(self):
        assert normalize_mac("") is None

    def test_none_mac_returns_none(self):
        assert normalize_mac(None) is None

    def test_zero_mac_returns_none(self):
        assert normalize_mac("00:00:00:00:00:00") is None

    def test_dot_separated_mac(self):
        assert normalize_mac("AA.BB.CC.DD.EE.FF") == "aa:bb:cc:dd:ee:ff"


class TestMacFromIp:
    """IP 生成虚拟 MAC 测试"""

    def test_generates_valid_mac(self):
        mac = mac_from_ip("192.168.1.100")
        assert normalize_mac(mac) is not None

    def test_deterministic(self):
        assert mac_from_ip("10.0.0.1") == mac_from_ip("10.0.0.1")

    def test_different_ips_different_macs(self):
        assert mac_from_ip("10.0.0.1") != mac_from_ip("10.0.0.2")
