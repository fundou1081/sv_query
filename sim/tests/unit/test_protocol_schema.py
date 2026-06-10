"""
test_protocol_schema.py
========================
Phase A Session 4: YAML 协议 schema 加载器

测试覆盖:
  - 单个 YAML 加载 (axi4.yaml)
  - YAML 字段校验 (channels, signal_roles, variants)
  - Registry 加载多个 schema
  - 自定义 schema 扩展
  - YAML 错误处理
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from applications.bus.schema import (
    ProtocolSchema,
    ProtocolSchemaRegistry,
    ChannelSpec,
    SignalRoleSpec,
    VariantSpec,
    load_protocols,
)


# ---------------------------------------------------------------------------
# 单个 schema 加载
# ---------------------------------------------------------------------------

class TestLoadAXI4Schema:
    def test_load_default_axi4(self):
        """默认 config/protocols/axi4.yaml 必须存在并可加载."""
        schema = ProtocolSchema.from_yaml("config/protocols/axi4.yaml")
        assert schema.protocol == "AXI4"
        assert schema.description

    def test_axi4_has_5_channels(self):
        schema = ProtocolSchema.from_yaml("config/protocols/axi4.yaml")
        assert "AW" in schema.channels
        assert "W" in schema.channels
        assert "B" in schema.channels
        assert "AR" in schema.channels
        assert "R" in schema.channels

    def test_axi4_aw_required_signals(self):
        schema = ProtocolSchema.from_yaml("config/protocols/axi4.yaml")
        aw = schema.channels["AW"]
        assert "awvalid" in aw.required
        assert "awready" in aw.required
        assert "awaddr" in aw.required

    def test_axi4_aw_optional_signals(self):
        schema = ProtocolSchema.from_yaml("config/protocols/axi4.yaml")
        aw = schema.channels["AW"]
        assert "awlen" in aw.optional
        assert "awsize" in aw.optional
        assert "awburst" in aw.optional
        assert "awid" in aw.optional

    def test_axi4_signal_roles(self):
        schema = ProtocolSchema.from_yaml("config/protocols/axi4.yaml")
        assert "awvalid" in schema.signal_roles
        assert schema.signal_roles["awvalid"].channel == "AW"
        assert schema.signal_roles["awvalid"].role == "valid"

    def test_axi4_variants(self):
        """AXI4 应该有 AXI4_FULL 和 AXI4_LITE 两个变体."""
        schema = ProtocolSchema.from_yaml("config/protocols/axi4.yaml")
        names = {v.name for v in schema.variants}
        assert "AXI4_FULL" in names
        assert "AXI4_LITE" in names


# ---------------------------------------------------------------------------
# ChannelSpec 数据结构
# ---------------------------------------------------------------------------

class TestChannelSpec:
    def test_required_and_optional(self):
        ch = ChannelSpec(
            name="AW",
            required=["awvalid", "awready", "awaddr"],
            optional=["awlen", "awsize"],
        )
        assert ch.name == "AW"
        assert len(ch.required) == 3
        assert len(ch.optional) == 2

    def test_required_count(self):
        ch = ChannelSpec(name="W", required=["wvalid", "wready", "wdata"], optional=[])
        assert ch.required_count() == 3

    def test_total_count(self):
        ch = ChannelSpec(name="AW", required=["a", "b"], optional=["c", "d", "e"])
        assert ch.total_count() == 5

    def test_has_signal(self):
        ch = ChannelSpec(name="AW", required=["awvalid"], optional=["awlen"])
        assert ch.has_signal("awvalid")
        assert ch.has_signal("awlen")
        assert not ch.has_signal("unknown")


# ---------------------------------------------------------------------------
# SignalRoleSpec 数据结构
# ---------------------------------------------------------------------------

class TestSignalRoleSpec:
    def test_basic(self):
        s = SignalRoleSpec(channel="AW", role="valid")
        assert s.channel == "AW"
        assert s.role == "valid"

    def test_with_width(self):
        s = SignalRoleSpec(channel="AW", role="ctrl", width=8)
        assert s.width == 8

    def test_repr(self):
        s = SignalRoleSpec(channel="AW", role="valid")
        # 不应崩溃
        s_repr = repr(s)
        assert "AW" in s_repr


# ---------------------------------------------------------------------------
# VariantSpec 数据结构
# ---------------------------------------------------------------------------

class TestVariantSpec:
    def test_needs_signals(self):
        v = VariantSpec(name="AXI4_FULL", needs_signals=["awlen", "wstrb"])
        assert v.name == "AXI4_FULL"
        assert "awlen" in v.needs_signals
        assert "wstrb" in v.needs_signals

    def test_needs_absent(self):
        v = VariantSpec(name="AXI4_LITE", needs_absent_signals=["awlen", "wstrb"])
        assert v.name == "AXI4_LITE"
        assert "awlen" in v.needs_absent_signals

    def test_repr(self):
        v = VariantSpec(name="AXI4_FULL")
        # 不应崩溃
        repr(v)


# ---------------------------------------------------------------------------
# ProtocolSchema 数据结构
# ---------------------------------------------------------------------------

class TestProtocolSchema:
    def test_basic(self):
        schema = ProtocolSchema(
            protocol="TEST",
            description="Test protocol",
            channels={},
            signal_roles={},
            variants=[],
        )
        assert schema.protocol == "TEST"
        assert schema.description == "Test protocol"

    def test_required_count(self):
        """统计所有通道的 required 信号总数."""
        schema = ProtocolSchema(
            protocol="TEST",
            channels={
                "AW": ChannelSpec("AW", ["a", "b", "c"], []),
                "W": ChannelSpec("W", ["d", "e"], []),
            },
            signal_roles={},
            variants=[],
        )
        assert schema.required_count() == 5

    def test_repr(self):
        schema = ProtocolSchema(
            protocol="TEST",
            channels={"AW": ChannelSpec("AW", ["a"], [])},
            signal_roles={},
            variants=[],
        )
        # 不应崩溃
        repr(schema)


# ---------------------------------------------------------------------------
# ProtocolSchemaRegistry
# ---------------------------------------------------------------------------

class TestProtocolSchemaRegistry:
    def test_load_default_dir(self):
        """默认 config/protocols/ 目录加载所有 YAML."""
        reg = ProtocolSchemaRegistry.from_directory("config/protocols")
        assert "AXI4" in reg.protocols
        assert reg.count >= 1

    def test_get_protocol(self):
        reg = ProtocolSchemaRegistry.from_directory("config/protocols")
        schema = reg.get("AXI4")
        assert schema is not None
        assert schema.protocol == "AXI4"

    def test_get_unknown_protocol_returns_none(self):
        reg = ProtocolSchemaRegistry.from_directory("config/protocols")
        assert reg.get("UNKNOWN") is None

    def test_list_protocols(self):
        reg = ProtocolSchemaRegistry.from_directory("config/protocols")
        protos = reg.list_protocols()
        assert "AXI4" in protos


# ---------------------------------------------------------------------------
# load_protocols 顶层工具
# ---------------------------------------------------------------------------

class TestLoadProtocols:
    def test_load_protocols(self):
        schemas = load_protocols("config/protocols")
        assert "AXI4" in schemas
        assert isinstance(schemas["AXI4"], ProtocolSchema)


# ---------------------------------------------------------------------------
# YAML 错误处理
# ---------------------------------------------------------------------------

class TestYAMLErrors:
    def test_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ProtocolSchema.from_yaml(tmp_path / "nonexistent.yaml")

    def test_missing_required_fields(self, tmp_path):
        """YAML 缺少 protocol 字段应报错."""
        bad_yaml = """
description: missing protocol field
channels: {}
"""
        bad_path = tmp_path / "bad.yaml"
        bad_path.write_text(bad_yaml)
        with pytest.raises(ValueError, match="protocol"):
            ProtocolSchema.from_yaml(bad_path)

    def test_invalid_channel_format(self, tmp_path):
        """channel 缺少 required 字段."""
        bad_yaml = """
protocol: BAD
channels:
  AW:
    optional: [awlen]
"""
        bad_path = tmp_path / "bad.yaml"
        bad_path.write_text(bad_yaml)
        with pytest.raises(ValueError, match="required"):
            ProtocolSchema.from_yaml(bad_path)


# ---------------------------------------------------------------------------
# 性能
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_load_5_yaml_fast(self):
        import time
        start = time.time()
        for _ in range(5):
            ProtocolSchema.from_yaml("config/protocols/axi4.yaml")
        elapsed = time.time() - start
        assert elapsed < 0.5
