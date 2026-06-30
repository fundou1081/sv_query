"""
applications.bus.schema - YAML 协议 schema 加载器

Phase A Session 4: 协议 schema 声明式定义

设计要点
========

1. **声明式优先** — 协议全部用 YAML 描述, 改 YAML 加协议不动 Python
2. **字段明确**:
   - protocol: 协议名 (e.g., "AXI4")
   - description: 协议描述
   - channels: {name: {required: [...], optional: [...]}}
   - signal_roles: {canonical_name: {channel, role, width?}}
   - variants: [{name, needs_signals, needs_absent_signals, ...}]
3. **加载器**:
   - `ProtocolSchema.from_yaml(path)` 加载单个
   - `ProtocolSchemaRegistry.from_directory(dir)` 加载整个目录
   - `load_protocols(dir)` 顶层工具
4. **YAML 无强制依赖** — 复用 Session 1 的 mini parser

使用
====

    from applications.bus.schema import (
        load_protocols, ProtocolSchemaRegistry, ProtocolSchema,
    )

    # 加载所有
    schemas = load_protocols("config/protocols")
    print(list(schemas.keys()))  # ['AXI4']

    # 单个
    schema = ProtocolSchema.from_yaml("config/protocols/axi4.yaml")
    print(schema.channels.keys())  # ['AW', 'W', 'B', 'AR', 'R']

    # Registry
    reg = ProtocolSchemaRegistry.from_directory("config/protocols")
    print(reg.get("AXI4").variants)  # [AXI4_FULL, AXI4_LITE, AXI4_STREAM]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

from .normalize import _yaml_safe_load


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class SignalRoleSpec:
    """单个信号的角色定义.

    Attributes:
        channel: 所属通道 (e.g., "AW", "W")
        role: 角色 (e.g., "valid", "ready", "data", "addr", "ctrl")
        width: 可选, 期望位宽
    """

    channel: str
    role: str
    width: int | None = None

    def __repr__(self) -> str:
        return f"SignalRoleSpec({self.channel}.{self.role}{f', w={self.width}' if self.width else ''})"


@dataclass
class ChannelSpec:
    """一个通道的信号定义.

    Attributes:
        name: 通道名 (e.g., "AW", "W")
        required: 必选信号名列表 (canonical)
        optional: 可选信号名列表
    """

    name: str
    required: list[str] = field(default_factory=list)
    optional: list[str] = field(default_factory=list)

    def required_count(self) -> int:
        return len(self.required)

    def total_count(self) -> int:
        return len(self.required) + len(self.optional)

    def has_signal(self, sig: str) -> bool:
        return sig in self.required or sig in self.optional

    def is_required(self, sig: str) -> bool:
        return sig in self.required

    def __repr__(self) -> str:
        return f"ChannelSpec({self.name}, required={self.required_count()}, optional={len(self.optional)})"


@dataclass
class ChannelOverride:
    """变体对某通道的评分调整.

    Attributes:
        channel: 通道名 (e.g., "A", "D")
        required: 额外需匹配的信号名 (canonical 或 normalized) — 命中后该通道视为 present
        score: 命中后 channel.score 的下界 (max(current, score))
        name_score: 命中后 channel.name_score 的下界
        pattern_score: 命中后 channel.pattern_score 的下界
    """
    channel: str
    required: list[str] = field(default_factory=list)
    score: float = 0.5
    name_score: float = 0.5
    pattern_score: float = 0.5


@dataclass
class VariantSpec:
    """协议变体.

    Attributes:
        name: 变体名 (e.g., "AXI4_FULL", "AXI4_LITE")
        description: 变体描述
        needs_signals: 必须存在的信号列表 (canonical)
        needs_absent_signals: 必须不存在的信号列表
        channel_overrides: 变体命中后对各通道评分的调整 (默认空 = 不调整)
    """

    name: str
    description: str = ""
    needs_signals: list[str] = field(default_factory=list)
    needs_absent_signals: list[str] = field(default_factory=list)
    channel_overrides: list[ChannelOverride] = field(default_factory=list)

    def override_for(self, channel: str) -> ChannelOverride | None:
        """查找此变体对该通道的 override (无则 None)."""
        for ov in self.channel_overrides:
            if ov.channel == channel:
                return ov
        return None

    def __repr__(self) -> str:
        return (
            f"VariantSpec({self.name}, needs={len(self.needs_signals)}, "
            f"absent={len(self.needs_absent_signals)}, "
            f"overrides={len(self.channel_overrides)})"
        )


@dataclass
class ProtocolSchema:
    """完整协议定义."""

    protocol: str
    description: str = ""
    channels: dict[str, ChannelSpec] = field(default_factory=dict)
    signal_roles: dict[str, SignalRoleSpec] = field(default_factory=dict)
    variants: list[VariantSpec] = field(default_factory=list)

    def required_count(self) -> int:
        return sum(ch.required_count() for ch in self.channels.values())

    def total_signal_count(self) -> int:
        return sum(ch.total_count() for ch in self.channels.values())

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> ProtocolSchema:
        """从 YAML 文件加载."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"YAML not found: {path}")
        data = _yaml_safe_load(path)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> ProtocolSchema:
        """从 dict 构造, 校验必要字段."""
        if "protocol" not in data:
            raise ValueError("YAML missing required field: 'protocol'")

        # channels
        channels: dict[str, ChannelSpec] = {}
        for ch_name, ch_data in (data.get("channels") or {}).items():
            if "required" not in ch_data:
                raise ValueError(
                    f"Channel '{ch_name}' missing required field: 'required'"
                )
            req_names = [s["name"] if isinstance(s, dict) else s
                         for s in ch_data.get("required", [])]
            opt_names = [s["name"] if isinstance(s, dict) else s
                         for s in ch_data.get("optional", [])]
            channels[ch_name] = ChannelSpec(
                name=ch_name,
                required=req_names,
                optional=opt_names,
            )

        # signal_roles
        signal_roles: dict[str, SignalRoleSpec] = {}
        for sig_name, role_data in (data.get("signal_roles") or {}).items():
            if isinstance(role_data, dict):
                signal_roles[sig_name] = SignalRoleSpec(
                    channel=role_data.get("channel", ""),
                    role=role_data.get("role", ""),
                    width=role_data.get("width"),
                )

        # variants
        variants: list[VariantSpec] = []
        for v_data in (data.get("variants") or []):
            # 加载 channel_overrides (默认空)
            overrides: list[ChannelOverride] = []
            for ov_data in (v_data.get("channel_overrides") or []):
                overrides.append(ChannelOverride(
                    channel=ov_data.get("channel", ""),
                    required=list(ov_data.get("required", [])),
                    score=float(ov_data.get("score", 0.5)),
                    name_score=float(ov_data.get("name_score", 0.5)),
                    pattern_score=float(ov_data.get("pattern_score", 0.5)),
                ))
            variants.append(VariantSpec(
                name=v_data.get("name", ""),
                description=v_data.get("description", ""),
                needs_signals=list(v_data.get("needs_signals", [])),
                needs_absent_signals=list(v_data.get("needs_absent_signals", [])),
                channel_overrides=overrides,
            ))

        return cls(
            protocol=data["protocol"],
            description=data.get("description", ""),
            channels=channels,
            signal_roles=signal_roles,
            variants=variants,
        )

    def __repr__(self) -> str:
        return (
            f"ProtocolSchema({self.protocol!r}, "
            f"channels={list(self.channels.keys())}, "
            f"variants={[v.name for v in self.variants]})"
        )


@dataclass
class ProtocolSchemaRegistry:
    """协议 schema 注册表 — 加载整个目录的所有协议."""

    protocols: dict[str, ProtocolSchema] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.protocols)

    def get(self, name: str) -> ProtocolSchema | None:
        return self.protocols.get(name)

    def list_protocols(self) -> list[str]:
        return list(self.protocols.keys())

    @classmethod
    def from_directory(
        cls, dir_path: Union[str, Path], pattern: str = "*.yaml"
    ) -> ProtocolSchemaRegistry:
        """从目录加载所有 YAML 文件."""
        dir_path = Path(dir_path)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        reg = cls()
        for yaml_file in sorted(dir_path.glob(pattern)):
            try:
                schema = ProtocolSchema.from_yaml(yaml_file)
                reg.protocols[schema.protocol] = schema
            except Exception as e:
                # 不让一个坏文件影响其他加载
                import sys
                print(
                    f"Warning: failed to load {yaml_file}: {e}",
                    file=sys.stderr,
                )
        return reg


def load_protocols(dir_path: Union[str, Path]) -> dict[str, ProtocolSchema]:
    """顶层工具: 加载目录下所有协议 schema."""
    reg = ProtocolSchemaRegistry.from_directory(dir_path)
    return reg.protocols
