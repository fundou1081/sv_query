"""[iter_309 / PLAN P15] `--bits` 端点归一化（paths/dataflow/impact 共用）。

输入是**信号 id + 位索引**，输出是可直接查图的节点 id 与精度标记：
  - 位节点存在 → `top.a[1]`（precision=bit）
  - 位节点缺失但总线存在 → 总线（precision=bus, coarse_fallback=true）
  - 都没有 → 原样（后续命令按"节点不存在"报错）
"""
from __future__ import annotations

import re


def parse_bits(raw: str | None) -> list[int]:
    """解析 `--bits`（逗号分隔位索引；空/None → []）。非法值抛 ValueError。"""
    if raw is None or not raw.strip():
        return []
    out = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            raise ValueError("--bits 含空值（示例: --bits 1,5）")
        try:
            value = int(token)
        except ValueError:
            raise ValueError(f"--bits 需要整数字索引，收到 {token!r}") from None
        if value < 0:
            raise ValueError("--bits 不接受负索引")
        out.append(value)
    return out


def normalize_endpoint(graph, signal: str, bit: int | None) -> dict:
    """信号 + 可选位 → 图节点 id + 精度信息。

    Returns: {requested_bit, resolved, precision, coarse_fallback}
    """
    if bit is None:
        return {"requested_bit": None, "resolved": signal,
                "precision": "bus", "coarse_fallback": False}
    if re.search(r"\[\d+\]$", signal):
        raise ValueError(
            f"信号 {signal!r} 已带位索引，不能再与 --bits 同时使用")
    candidate = f"{signal}[{bit}]"
    graph_nodes = graph.nodes() if graph is not None else ()
    if candidate in graph_nodes:
        return {"requested_bit": bit, "resolved": candidate,
                "precision": "bit", "coarse_fallback": False}
    if signal in graph_nodes:
        return {"requested_bit": bit, "resolved": signal,
                "precision": "bus", "coarse_fallback": True}
    return {"requested_bit": bit, "resolved": signal,
            "precision": "unknown", "coarse_fallback": False}
