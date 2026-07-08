"""
数据库层测试：验证双数据库架构（主库 + 配置库）
"""
import pytest
from sqlalchemy import text
from app.models.user import User
from app.models.device import Device
from app.models.pair_code import PairCode
from app.models.heartbeat_log import HeartbeatLog
from app.models.device_config import DeviceConfig
from app.core.security import get_password_hash


class TestMainDatabase:
    """主库（PostgreSQL/SQLite）测试"""

    def test_create_user(self, db):
        """测试创建用户"""
        user = User(
            username="newuser",
            email="new@example.com",
            password_hash=get_password_hash("pass123"),
            salt="salt",
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.role == "user"
        assert user.is_active is True

    def test_user_unique_constraints(self, db):
        """测试用户名和邮箱唯一约束"""
        user1 = User(username="dup", email="dup@example.com", password_hash="h", salt="s")
        db.add(user1)
        db.commit()

        user2 = User(username="dup", email="other@example.com", password_hash="h", salt="s")
        db.add(user2)
        with pytest.raises(Exception):
            db.commit()

    def test_create_device(self, db, test_user):
        """测试创建设备"""
        device = Device(
            user_id=test_user.id,
            mac_address="11:22:33:44:55:66",
            ip_address="192.168.1.50",
            hostname="my-device",
            model="rpi5",
            status="registered",
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        assert device.id is not None
        assert device.mac_address == "11:22:33:44:55:66"
        assert device.user_id == test_user.id

    def test_device_stores_interfaces_json(self, db, test_user):
        """设备存储接口列表 JSON"""
        import json
        interfaces = [
            {"name": "wlan0", "ip": "192.168.1.20", "type": "WiFi (Default)"},
            {"name": "eth0", "ip": "192.168.1.21", "type": "Ethernet"},
        ]
        device = Device(
            user_id=test_user.id,
            mac_address="aa:bb:cc:dd:ee:ff",
            interfaces_json=json.dumps(interfaces),
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        assert device.interfaces_json is not None
        parsed = json.loads(device.interfaces_json)
        assert len(parsed) == 2
        assert parsed[0]["name"] == "wlan0"
        assert parsed[1]["type"] == "Ethernet"

    def test_device_interfaces_json_nullable(self, db, test_user):
        """interfaces_json 列允许为空"""
        device = Device(
            user_id=test_user.id,
            mac_address="bb:cc:dd:ee:ff:00",
        )
        db.add(device)
        db.commit()
        db.refresh(device)

        assert device.interfaces_json is None

    def test_device_mac_unique(self, db, test_user):
        """测试 MAC 地址唯一约束"""
        d1 = Device(mac_address="aa:bb:cc:dd:ee:ff", user_id=test_user.id)
        db.add(d1)
        db.commit()

        d2 = Device(mac_address="aa:bb:cc:dd:ee:ff", user_id=test_user.id)
        db.add(d2)
        with pytest.raises(Exception):
            db.commit()

    def test_device_user_relationship(self, db, test_user, test_device):
        """测试设备-用户关系"""
        assert test_device.user is not None
        assert test_device.user.id == test_user.id
        assert test_user.devices is not None
        assert len(test_user.devices) == 1

    def test_create_pair_code(self, db, test_user):
        """测试创建配对码"""
        from datetime import datetime, timedelta
        pc = PairCode(
            user_id=test_user.id,
            code="123456",
            status="pending",
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
        db.add(pc)
        db.commit()
        db.refresh(pc)

        assert pc.id is not None
        assert pc.code == "123456"
        assert pc.status == "pending"

    def test_create_heartbeat_log(self, db, test_device):
        """测试创建心跳日志"""
        log = HeartbeatLog(
            device_id=test_device.id,
            ip_address="192.168.1.100",
            status="online",
            internet_available=True,
            uptime_seconds=3600,
            memory_usage=512.0,
            cpu_usage=25.5,
        )
        db.add(log)
        db.commit()
        db.refresh(log)

        assert log.id is not None
        assert log.device_id == test_device.id

    def test_cascade_delete_device_logs(self, db, test_device):
        """测试删除设备时级联删除心跳日志"""
        log = HeartbeatLog(device_id=test_device.id, ip_address="1.1.1.1", status="online")
        db.add(log)
        db.commit()

        db.delete(test_device)
        db.commit()

        remaining = db.query(HeartbeatLog).filter(HeartbeatLog.device_id == test_device.id).all()
        assert len(remaining) == 0


class TestSettingsDatabase:
    """配置库（SQLite）测试"""

    def test_create_device_config(self, settings_db):
        """测试创建设备配置"""
        config = DeviceConfig(
            device_id=999,
            llm_provider="deepseek",
            llm_model="deepseek-v3",
            temperature=0.8,
            max_tokens=4096,
            language="zh",
        )
        settings_db.add(config)
        settings_db.commit()
        settings_db.refresh(config)

        assert config.id is not None
        assert config.device_id == 999
        assert config.llm_provider == "deepseek"
        assert config.temperature == 0.8

    def test_device_config_no_fk_constraint(self, settings_db):
        """测试配置库无外键约束（跨库设计）"""
        config = DeviceConfig(device_id=99999, llm_provider="openai")
        settings_db.add(config)
        settings_db.commit()
        # 不会因外键约束失败
        assert config.id is not None

    def test_update_device_config(self, settings_db):
        """测试更新设备配置"""
        config = DeviceConfig(device_id=1, llm_provider="deepseek", temperature=0.5)
        settings_db.add(config)
        settings_db.commit()

        config.temperature = 0.9
        config.llm_model = "deepseek-r1"
        settings_db.commit()

        updated = settings_db.query(DeviceConfig).filter(DeviceConfig.device_id == 1).first()
        assert updated.temperature == 0.9
        assert updated.llm_model == "deepseek-r1"

    def test_device_config_default_values(self, settings_db):
        """测试配置默认值"""
        config = DeviceConfig(device_id=1)
        settings_db.add(config)
        settings_db.commit()

        assert config.llm_provider == "deepseek"
        assert config.llm_model == "deepseek-v3"
        assert config.temperature == 0.7
        assert config.max_tokens == 2048
        assert config.language == "auto"

    def test_multiple_devices_configs(self, settings_db):
        """测试多设备各自独立配置"""
        c1 = DeviceConfig(device_id=1, llm_provider="deepseek", temperature=0.5)
        c2 = DeviceConfig(device_id=2, llm_provider="openai", temperature=0.9)
        settings_db.add_all([c1, c2])
        settings_db.commit()

        configs = settings_db.query(DeviceConfig).all()
        assert len(configs) == 2

        d1_config = settings_db.query(DeviceConfig).filter(DeviceConfig.device_id == 1).first()
        assert d1_config.llm_provider == "deepseek"

        d2_config = settings_db.query(DeviceConfig).filter(DeviceConfig.device_id == 2).first()
        assert d2_config.llm_provider == "openai"
