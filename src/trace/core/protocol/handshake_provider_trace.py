"""
trace.core.protocol.handshake_provider_trace - Phase B 真实 handshake 集成

Phase A v4: TraceBasedHandshakeProvider

设计要点
========

1. **依赖 graph**: 需要 SignalTracer + graph (从 SV 编译得到)
2. **对每个 (valid, ready) 锚点**:
   - 调 `trace_fanin_detailed(ready)` 拿 DriverInfo 列表
   - 调 `detect_handshake_type_with_node()` 拿 HandshakeInfo
   - 转成 HandshakeInfoLite (避免 DriverInfo 依赖)
3. **缓存结果**: 同一 (valid, ready) 对不重复 trace
4. **失败回退**: trace 失败返 None, 让 NameBased 接管

使用
====

    from trace.core.protocol.handshake_provider_trace import (
        TraceBasedHandshakeProvider, make_trace_based_provider,
    )
    from trace.core.protocol.sv_extractor import SVSignalExtractor
    from trace.core.query.signal import SignalTracer

    ext = SVSignalExtractor.from_file("axi_dp_ram.sv")
    ext.extract_all_modules()
    tracer = ext._get_tracer()
    graph = tracer.build_graph()
    st = SignalTracer(graph)

    provider = TraceBasedHandshakeProvider(st, graph)
    info = provider.get_handshake("awvalid", "awready")
    # HandshakeInfoLite(awvalid/awready, type=STANDARD_AXI, ch=AW)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .handshake_provider import (
    HandshakeInfoLite,
    HandshakeProvider,
)


_logger = logging.getLogger(__name__)


class TraceBasedHandshakeProvider(HandshakeProvider):
    """基于 Phase B trace 的真实握手分析.

    与 NameBasedHandshakeProvider 区别:
    - NameBased: 只看信号名, 所有 valid+ready 都返 STANDARD_AXI
    - TraceBased: 跑真实 trace, 区分 STANDARD_AXI / COMBINATIONAL_BP / REGISTERED_BP / 透传 等

    要求:
    - SignalTracer (提供 trace_fanin_detailed)
    - graph (提供节点查询)
    - 模块名 (可选, 用于解析相对路径)
    """

    def __init__(
        self,
        signal_tracer=None,
        graph=None,
        module: Optional[str] = None,
    ):
        self._tracer = signal_tracer
        self._graph = graph
        self._module = module
        # 缓存: (valid, ready) → HandshakeInfoLite
        self._cache: Dict[Tuple[str, str], Optional[HandshakeInfoLite]] = {}

    @property
    def tracer(self):
        return self._tracer

    @tracer.setter
    def tracer(self, value):
        self._tracer = value
        self._cache.clear()

    def set_context(self, signal_tracer, graph, module: Optional[str] = None):
        """设置 graph context (用于每次 scan 重置)."""
        self._tracer = signal_tracer
        self._graph = graph
        self._module = module
        self._cache.clear()

    def get_handshake(
        self, valid: str, ready: str
    ) -> Optional[HandshakeInfoLite]:
        """基于 trace 返回 (valid, ready) 真实 handshake.

        Returns:
            HandshakeInfoLite 或 None (trace 失败 / 信号不存在)
        """
        # 缓存
        key = (valid, ready)
        if key in self._cache:
            return self._cache[key]

        if not self._tracer or not self._graph:
            return None

        info = self._trace_handshake(valid, ready)
        self._cache[key] = info
        return info

    # ----- 内部 -----

    def _trace_handshake(
        self, valid: str, ready: str
    ) -> Optional[HandshakeInfoLite]:
        """实际 trace 一对 (valid, ready)."""
        try:
            # 1) 找 ready 节点 (trace fanin)
            ready_node = self._resolve_node(ready)
            if not ready_node:
                _logger.debug(f"Cannot resolve ready node: {ready}")
                return self._fallback_unknown(valid, ready)

            # 2) 跑 trace_fanin_detailed
            dis = self._tracer.trace_fanin_detailed(ready_node, module=self._module)
            if dis is None:
                return self._fallback_unknown(valid, ready)

            # 3) 调 detect_handshake_type_with_node
            from trace.core.handshake_detector import detect_handshake_type_with_node
            hi = detect_handshake_type_with_node(
                signal=ready_node,
                driver_infos=dis,
                node_kind=None,  # 暂不传, 让 Phase B 自己判断
                counterpart_hint=valid,
            )

            # 4) 转换成 HandshakeInfoLite
            return HandshakeInfoLite(
                valid=valid,
                ready=ready,
                handshake_type=hi.handshake_type or "UNKNOWN",
                channel=hi.channel or "UNKNOWN",
            )
        except Exception as e:
            _logger.debug(f"Trace handshake failed for ({valid}, {ready}): {e}")
            return self._fallback_unknown(valid, ready)

    def _resolve_node(self, name: str) -> Optional[str]:
        """解析信号名为 graph 节点 ID.

        策略:
        1. 如果是 hierarchical (含 .), 直接用
        2. 如果是 bare name, 尝试 (a) module.name (b) bare name in graph
        """
        if not self._graph:
            return None

        # 1. 已 hierarchical
        if "." in name and name in self._graph.nodes():
            return name

        # 2. 尝试 module.name
        if self._module:
            mod_name = f"{self._module}.{name}"
            if mod_name in self._graph.nodes():
                return mod_name

        # 3. bare name (可能多个, 取第一个)
        for node in self._graph.nodes():
            # 匹配: node.endswith(name) 且中间是 . (不是 [ 这种 array access)
            if node == name or node.endswith(f".{name}"):
                return node

        return None

    @staticmethod
    def _fallback_unknown(valid: str, ready: str) -> HandshakeInfoLite:
        """Trace 失败时的 fallback."""
        return HandshakeInfoLite(
            valid=valid,
            ready=ready,
            handshake_type="UNKNOWN",
            channel="UNKNOWN",
        )


def make_trace_based_provider(
    signal_tracer=None,
    graph=None,
    module: Optional[str] = None,
) -> TraceBasedHandshakeProvider:
    """工厂函数: 创建 TraceBasedHandshakeProvider."""
    return TraceBasedHandshakeProvider(
        signal_tracer=signal_tracer,
        graph=graph,
        module=module,
    )
