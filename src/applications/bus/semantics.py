"""
applications.bus.semantics - 协议语义机读化

[2026-06-13] 与 schema.py 区分:
  - ProtocolSchema: 用于"识别" — 名字、结构、模式 (Phase A 协议检测)
  - ProtocolSemantics: 用于"用对" — transfer 条件、valid/ready 独立性、死锁规则 (Phase C)

数据流:
  ProtocolSemantics YAML → load_semantics() → 内存对象 → bus semantics / bus deadlock 命令

设计要点
========

1. **声明式优先** — 4 个协议 (TL-UL/AXI4/AHB/APB) 用 YAML 描述, 不动 Python
2. **可执行规则** — handshake 规则是条件表达式字符串 ("a_valid && a_ready"),
   可用于匹配 graph 中的实际信号名
3. **死锁规则** — forbidden_combinational_loops 列出"valid 不能依赖 ready"等
   组合规则, 静态检测时检查
4. **不仿真** — 静态分析, 不模拟时序

使用
====

    from applications.bus.semantics import load_semantics, list_semantics

    # 列出所有可用协议
    print(list_semantics())  # ['AHB', 'APB', 'AXI4', 'TL-UL']

    # 加载指定协议
    sem = load_semantics("TL-UL")
    print(sem.handshake.transfer)  # "a_valid && a_ready"

    # 死锁规则
    for rule in sem.deadlock_rules:
        print(f"[{rule.severity}] {rule.description}")
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
class HandshakeRule:
    """单个握手规则 (e.g. valid ↔ ready 独立性)."""
    name: str
    description: str = ""
    expression: str = ""  # e.g. "a_valid && a_ready"
    forbidden: bool = False  # True = 这个表达式模式是禁止的 (e.g. combinational loop)


@dataclass
class ChannelRule:
    """单个通道的语义规则.

    Attributes:
        name: 通道名 (e.g., "A", "AW")
        direction: "request" | "response" | "data" | "address" | "write_data" | "write_resp"
        valid: valid 信号名 (canonical, e.g., "a_valid")
        ready: ready 信号名 (canonical, e.g., "a_ready")
        data: data 信号名 (canonical, e.g., "a_data"), 可选
        depends_on: 这个通道依赖的其他通道 (e.g., D depends on A for TL-UL)
    """
    name: str
    direction: str  # request/response/data/...
    valid: str
    ready: str
    data: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)


@dataclass
class DeadlockRule:
    """死锁候选检测规则.

    Attributes:
        id: 唯一 ID (e.g. "TL-UL-A-valid-must-not-depend-on-ready")
        description: 规则说明
        severity: "error" | "warning" | "info"
        kind: 规则类型
            - "no_combinational_loop": valid 不能 combinational 依赖 ready
            - "no_cross_channel_loop": 通道间不能成环
            - "response_after_request": 响应必须在请求后
            - "fifo_no_full_deadlock": FIFO 满时不能完全死锁
        channels: 适用通道列表 (空 = 全部)
        expression: 描述这个规则的人类可读表达式
    """
    id: str
    description: str
    severity: str = "warning"
    kind: str = ""
    channels: List[str] = field(default_factory=list)
    expression: str = ""


@dataclass
class ProtocolSemantics:
    """完整协议语义定义.

    Attributes:
        protocol: 协议名 (e.g., "TL-UL")
        description: 协议描述
        transfer: 通用传输条件 ("valid && ready")
        channels: 各通道规则
        deadlock_rules: 死锁候选规则列表
        forbidden_combinational_loops: 禁止的组合逻辑环列表
            (e.g. ["valid → ready", "ready → valid"])
        notes: 设计说明 (来自 YAML)
    """
    protocol: str
    description: str = ""
    transfer: str = "valid && ready"
    channels: List[ChannelRule] = field(default_factory=list)
    deadlock_rules: List[DeadlockRule] = field(default_factory=list)
    forbidden_combinational_loops: List[str] = field(default_factory=list)
    notes: str = ""

    def channel(self, name: str) -> Optional[ChannelRule]:
        """按名字查通道。"""
        for ch in self.channels:
            if ch.name == name:
                return ch
        return None

    def __repr__(self) -> str:
        return (
            f"ProtocolSemantics({self.protocol!r}, "
            f"channels={len(self.channels)}, "
            f"deadlock_rules={len(self.deadlock_rules)})"
        )


# ---------------------------------------------------------------------------
# 加载器
# ---------------------------------------------------------------------------

_DEFAULT_SEMANTICS_DIR = Path(__file__).parents[3] / "config" / "protocols" / "semantics"


@dataclass
class ProtocolSemanticsRegistry:
    """协议语义注册表 — 加载整个目录的所有协议。"""
    semantics: Dict[str, ProtocolSemantics] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.semantics)

    def get(self, name: str) -> Optional[ProtocolSemantics]:
        return self.semantics.get(name)

    def list_protocols(self) -> List[str]:
        return list(self.semantics.keys())

    @classmethod
    def from_directory(
        cls, dir_path: Union[str, Path], pattern: str = "*.yaml"
    ) -> "ProtocolSemanticsRegistry":
        """从目录加载所有 YAML 文件。"""
        dir_path = Path(dir_path)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        reg = cls()
        for yaml_file in sorted(dir_path.glob(pattern)):
            try:
                sem = ProtocolSemantics.from_yaml(yaml_file)
                reg.semantics[sem.protocol] = sem
            except Exception as e:
                import sys
                print(
                    f"Warning: failed to load {yaml_file}: {e}",
                    file=sys.stderr,
                )
        return reg


def load_semantics(
    protocol_name: str,
    dir_path: Union[str, Path, None] = None,
) -> ProtocolSemantics:
    """[A1 2026-06-13] 加载指定协议的语义定义。

    Args:
        protocol_name: 协议名 (e.g. "TL-UL", "AXI4")
        dir_path: YAML 目录 (默认 config/protocols/semantics/)

    Returns:
        ProtocolSemantics 实例

    Raises:
        FileNotFoundError: 目录或协议 YAML 不存在
    """
    dir_path = Path(dir_path) if dir_path else _DEFAULT_SEMANTICS_DIR
    reg = ProtocolSemanticsRegistry.from_directory(dir_path)
    if protocol_name not in reg.semantics:
        available = reg.list_protocols()
        raise FileNotFoundError(
            f"Semantics for protocol {protocol_name!r} not found. "
            f"Available: {available}"
        )
    return reg.semantics[protocol_name]


def list_semantics(dir_path: Union[str, Path, None] = None) -> List[str]:
    """[A1] 列出所有可用协议的语义定义。"""
    dir_path = Path(dir_path) if dir_path else _DEFAULT_SEMANTICS_DIR
    if not dir_path.exists():
        return []
    reg = ProtocolSemanticsRegistry.from_directory(dir_path)
    return reg.list_protocols()


# ---------------------------------------------------------------------------
# YAML 解析
# ---------------------------------------------------------------------------

def _as_str_list(v) -> List[str]:
    """统一转 str list。"""
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def ProtocolSemantics_from_dict(data: dict) -> ProtocolSemantics:  # noqa: N802
    """从 dict 构造 ProtocolSemantics。"""
    if "protocol" not in data:
        raise ValueError("YAML missing required field: 'protocol'")

    # channels
    channels: List[ChannelRule] = []
    for ch_data in (data.get("channels") or []):
        channels.append(ChannelRule(
            name=ch_data.get("name", ""),
            direction=ch_data.get("direction", "data"),
            valid=ch_data.get("valid", ""),
            ready=ch_data.get("ready", ""),
            data=ch_data.get("data"),
            depends_on=_as_str_list(ch_data.get("depends_on")),
        ))

    # deadlock_rules
    deadlock_rules: List[DeadlockRule] = []
    for r_data in (data.get("deadlock_rules") or []):
        deadlock_rules.append(DeadlockRule(
            id=r_data.get("id", ""),
            description=r_data.get("description", ""),
            severity=r_data.get("severity", "warning"),
            kind=r_data.get("kind", ""),
            channels=_as_str_list(r_data.get("channels")),
            expression=r_data.get("expression", ""),
        ))

    return ProtocolSemantics(
        protocol=data["protocol"],
        description=data.get("description", ""),
        transfer=data.get("transfer", "valid && ready"),
        channels=channels,
        deadlock_rules=deadlock_rules,
        forbidden_combinational_loops=_as_str_list(
            data.get("forbidden_combinational_loops")
        ),
        notes=data.get("notes", ""),
    )


# 将方法挂到 dataclass
ProtocolSemantics.from_yaml = classmethod(lambda cls, path: (
    ProtocolSemantics_from_dict(_yaml_safe_load(Path(path)))
))
