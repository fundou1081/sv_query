"""[iter_309/P15 + iter_314/P18.3] `--bits` 端点归一化（paths/dataflow/impact 共用）。

支持：
  - 单 bit：`1,5` / `src=1,dst=5`
  - 范围：`7:4,3:0` / `src=7:4,dst=3:0`（按 `hi:lo`，节点缺失回退总线并标记）
  - impact 单信号：`3` 或 `3:0` / `signal=3`

输出是可直接查图的节点 id 与精度标记：
  - 位节点存在 → `top.a[1]`（precision=bit）
  - 切片节点存在 → `top.a[7:4]`（precision=bus，slice）
  - 节点缺失但总线存在 → 总线（precision=bus, coarse_fallback=true）
  - 都没有 → 原样（后续命令按"节点不存在"报错）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BitRange:
    """位/范围端点；hi/lo 已按数值归一化（hi>=lo）。"""

    hi: int
    lo: int

    @property
    def is_single(self) -> bool:
        return self.hi == self.lo

    def label(self) -> str:
        return str(self.hi) if self.is_single else f"{self.hi}:{self.lo}"


@dataclass
class BitSpec:
    """`--bits` 解析结果：位置列表或显式命名（二者互斥）。"""

    positional: list[BitRange] = field(default_factory=list)
    named: dict[str, BitRange] = field(default_factory=dict)

    def get(self, index: int, name: str) -> BitRange | None:
        if self.named:
            return self.named.get(name)
        return self.positional[index] if index < len(self.positional) else None


def _parse_range(token: str) -> BitRange:
    parts = token.split(":")
    if len(parts) > 2 or any(not p.strip() for p in parts):
        raise ValueError(f"--bits 范围格式应为 hi:lo，收到 {token!r}")
    try:
        values = [int(p.strip()) for p in parts]
    except ValueError:
        raise ValueError(f"--bits 需要整数字索引/范围，收到 {token!r}") from None
    if any(v < 0 for v in values):
        raise ValueError("--bits 不接受负索引")
    hi, lo = max(values), min(values)
    return BitRange(hi, lo)


def parse_bits(raw: str | None, names: tuple[str, ...] = ("src", "dst")) -> BitSpec:
    """解析 `--bits`（空/None → 空 spec）。

    `names` 是显式映射允许的名字（paths/dataflow: src,dst；impact: signal）。
    显式与位置写法**不可混用**；重复/未知名字报错。
    """
    if raw is None or not raw.strip():
        return BitSpec()
    tokens = [t.strip() for t in raw.split(",")]
    if any(not t for t in tokens):
        raise ValueError("--bits 含空值（示例: --bits 1,5 或 src=1,dst=5）")

    named_tokens = [t for t in tokens if "=" in t]
    if named_tokens and len(named_tokens) != len(tokens):
        raise ValueError("--bits 不能混用位置写法与显式映射（如 src=1,dst=5）")
    if named_tokens:
        named: dict[str, BitRange] = {}
        for token in tokens:
            name, _, value = token.partition("=")
            name, value = name.strip(), value.strip()
            if name not in names:
                raise ValueError(
                    f"--bits 不认识的端点名 {name!r}（可用: {', '.join(names)}）")
            if name in named:
                raise ValueError(f"--bits 端点 {name!r} 重复")
            named[name] = _parse_range(value)
        missing = [n for n in names if n not in named]
        if missing:
            raise ValueError(f"--bits 缺少端点: {', '.join(missing)}")
        return BitSpec(named=named)

    return BitSpec(positional=[_parse_range(t) for t in tokens])


def normalize_endpoint(graph, signal: str, span: BitRange | int | None) -> dict:
    """信号 + 可选位/范围 → 图节点 id + 精度信息。"""
    if span is None:
        return {"requested_bit": None, "requested_range": None,
                "resolved": signal, "precision": "bus",
                "coarse_fallback": False, "kind": "bus"}
    if isinstance(span, int):
        span = BitRange(span, span)
    if re.search(r"\[\d+(?::\d+)?\]$", signal):
        raise ValueError(
            f"信号 {signal!r} 已带位/范围索引，不能再与 --bits 同时使用")

    nodes = graph.nodes() if graph is not None else ()
    if span.is_single:
        candidate = f"{signal}[{span.hi}]"
        if candidate in nodes:
            return {"requested_bit": span.hi, "requested_range": None,
                    "resolved": candidate, "precision": "bit",
                    "coarse_fallback": False, "kind": "bit"}
        if signal in nodes:
            return {"requested_bit": span.hi, "requested_range": None,
                    "resolved": signal, "precision": "bus",
                    "coarse_fallback": True, "kind": "bit_fallback"}
        return {"requested_bit": span.hi, "requested_range": None,
                "resolved": signal, "precision": "unknown",
                "coarse_fallback": False, "kind": "bit_unknown"}

    # 范围：先按给定 hi:lo，再尝试反向（SV 两种声明顺序都可能出现）
    for cand in (f"{signal}[{span.hi}:{span.lo}]",
                 f"{signal}[{span.lo}:{span.hi}]"):
        if cand in nodes:
            return {"requested_bit": None, "requested_range": span.label(),
                    "resolved": cand, "precision": "bus",
                    "coarse_fallback": False, "kind": "range"}
    if signal in nodes:
        return {"requested_bit": None, "requested_range": span.label(),
                "resolved": signal, "precision": "bus",
                "coarse_fallback": True, "kind": "range_fallback"}
    return {"requested_bit": None, "requested_range": span.label(),
            "resolved": signal, "precision": "unknown",
            "coarse_fallback": False, "kind": "range_unknown"}
