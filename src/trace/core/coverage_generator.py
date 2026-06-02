# ==============================================================================
# coverage_generator.py - Control Coverage Generator
#
# 核心类: ControlCoverageGenerator
# 职责:
#   1. 找含输入信号的 if/case 控制块
#   2. 解析驱动表达式, 提取原子信号 (含位选)
#   3. 沿 driver 链递归展开
#   4. 生成 coverage 模板
#
# 复用:
#   - SignalGraph.find_drivers()
#   - ControlFlowGraph.find_control_blocks()
#   - DataFlowGraph (后续)
# ==============================================================================

import re
from typing import Callable

from .coverage_models import (
    AtomicSignal,
    DecompositionResult,
    EvidenceStep,
)
from .graph.models import NodeKind


class ControlCoverageGenerator:
    """控制覆盖度生成器

    Args:
        graph: SignalGraph (包含 driver 关系)
        cfg: ControlFlowGraph (可选, 用于找 if/case 块)
        source_provider: 源码懒加载函数 file -> str
    """

    # 字面量模式: 1, 8'hFF, 32'd100, 4'b1011, 16'h0F0F, 0, 0.5
    # 匹配: 数字(可选宽度'(基数字面量))
    LITERAL_PATTERN = re.compile(
        r"""
        ^\s*                       # 可选前导空白
        (?:
            \d+'(s?[dhbHoO])[0-9a-fA-FxXzZ?]+  # 8'hFF, 4'b1011, 16'd100
          | \d+'\.[0-9]+           # 1.5
          | \d+\.\d*                # 1. or 1.5
          | \d+                     # 123
        )
        \s*$                       # 可选尾部空白
        """,
        re.VERBOSE,
    )

    # 标识符模式 (含位选): a, a[3:0], a[5], data_in, module.signal
    # 捕获:
    #   group 1: base_name (e.g., "a", "data_in")
    #   group 2: bit_range (e.g., "3:0", "5", "[3:0][1:0]") 或 None
    # 重要: 包含后续位选链, 但不跨空格/运算符
    IDENTIFIER_PATTERN = re.compile(
        r"""
        (                           # group 1: 完整标识符 (含位选链)
            [A-Za-z_][A-Za-z0-9_]*   # 标识符
            (?:\[(?:\d+:\d+|\d+)\])*  # 位选链: [3:0][1:0]
        )
        """,
        re.VERBOSE,
    )

    # SystemVerilog 字面量: 8'hFF, 32'd100, 4'b1011, 4'bx, 4'bz
    LITERAL_PATTERN = re.compile(
        r"^\s*\d+'(s?[dhbHoO])[0-9a-fA-FxXzZ?]+\s*$"
    )

    def __init__(
        self,
        graph,
        cfg=None,
        source_provider: Callable[[str], str] | None = None,
    ):
        self._graph = graph
        self._cfg = cfg
        self._source_provider = source_provider

    def decompose(
        self,
        signals: list[str],
        max_signals: int = 5,
        max_depth: int = 10,
    ) -> DecompositionResult:
        """分解信号到原子

        Args:
            signals: 用户输入的信号列表
            max_signals: 信号树最大数量 (默认 5)
            max_depth: driver 链最大深度

        Returns:
            DecompositionResult
        """
        raise NotImplementedError("decompose() 将在后续 cycle 实现")

    def _parse_expression_to_atomics(self, expr: str) -> list[AtomicSignal]:
        """解析表达式字符串为原子信号列表

        识别位选 (a[3:0]), 过滤字面量, 保留所有出现的有意义信号。

        Args:
            expr: 表达式字符串 (如 "a & b", "a[3:0] | b[7:4]", "g < f")

        Returns:
            AtomicSignal 列表 (按出现顺序, 自动去重)
        """
        if not expr or not expr.strip():
            return []

        # 预处理: 去掉字面量 (避免识别为标识符)
        # 匹配: 数字'(base)value, 如 4'b1011, 8'hFF, 32'd100
        literal_re = re.compile(
            r"\b\d+'(s?[dhbHoO])[0-9a-fA-FxXzZ?]+\b"
        )
        expr_cleaned = literal_re.sub(" ", expr)

        seen = set()  # 去重用 (full_name)
        result = []

        for match in self.IDENTIFIER_PATTERN.finditer(expr_cleaned):
            full_identifier = match.group(1)

            # 跳过 SystemVerilog 关键字
            if full_identifier in (
                "logic", "wire", "reg", "input", "output", "inout",
                "module", "always", "assign", "if", "else", "case",
                "begin", "end", "posedge", "negedge", "or", "and",
            ):
                continue

            # 跳过纯数字
            if full_identifier.isdigit():
                continue

            # 拆分 base_name 和 bit_range 部分
            base_name, bit_select = self._split_identifier(full_identifier)

            # 去重
            if full_identifier in seen:
                continue
            seen.add(full_identifier)

            result.append(AtomicSignal(
                name=full_identifier,
                base_name=base_name,
                bit_range=bit_select,
            ))

        return result

    def _split_identifier(self, full: str) -> tuple[str, tuple[int, int] | None]:
        """拆分完整标识符为 (base_name, bit_range)

        Examples:
            "a" -> ("a", None)
            "a[3:0]" -> ("a", (3, 0))
            "a[5]" -> ("a", (5, 5))
            "data[7:0][3:0]" -> ("data", (7, 0))  # 取最外层

        Returns:
            (base_name, bit_range)
        """
        # 取第一个 [x:y] 或 [x]
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)(\[(\d+)(?::(\d+))?\])", full)
        if not m:
            return (full, None)
        base = m.group(1)
        high = int(m.group(3))
        low = int(m.group(4)) if m.group(4) else high
        return (base, (high, low))

    def _is_module_port(self, node) -> bool:
        """检测信号节点是否为模块端口

        端口是 driver 链的停止边界 - 不再向上追踪。

        Args:
            node: TraceNode 实例

        Returns:
            True 如果是模块端口 (PORT_IN/OUT/INOUT)
        """
        if node is None:
            return False
        if getattr(node, "is_port", False):
            return True
        # 双重保险: 检查 kind
        kind = getattr(node, "kind", None)
        if kind in (NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.PORT_INOUT):
            return True
        return False

    def _trace_drivers(
        self,
        signal: str,
        bit_range: tuple[int, int] | None,
        depth: int,
        max_depth: int,
        visited: set,
    ) -> list[AtomicSignal]:
        """沿 driver 链递归追踪

        Args:
            signal: 起点信号 ID
            bit_range: 起点信号的位选 (透传给 driver)
            depth: 当前深度
            max_depth: 最大深度
            visited: 已访问集合 (避免循环)

        Returns:
            追踪到的原子信号列表
        """
        # 1. 终止条件: 已访问
        if signal in visited:
            return []
        # 2. 终止条件: 超过最大深度
        if depth >= max_depth:
            return []
        # 3. 终止条件: 节点不存在
        node = self._graph.get_node(signal) if self._graph else None
        if node is None:
            return []
        # 4. 终止条件: 端口
        if self._is_module_port(node):
            return []

        visited.add(signal)
        result = []

        # 5. 找所有 driver
        drivers = self._graph.find_drivers(signal)
        if not drivers:
            return []

        for driver_node in drivers:
            driver_id = driver_node.id
            # 找对应的边
            edge = self._graph.get_edge(driver_id, signal)
            if edge is None:
                continue

            # 获取 driver 表达式
            expr = getattr(edge, "expression", "") or ""

            # 解析表达式 -> 原子信号
            atomics = self._parse_expression_to_atomics(expr)

            # 记录 evidence (为每个原子附加 driver 链证据)
            step = EvidenceStep(
                step_type="driver_chain",
                description=f"{driver_id} -> {signal}: {expr}",
                from_signal=signal,
                to_signals=[a.name for a in atomics],
            )
            for atomic in atomics:
                atomic.evidence.append(step)
            result.extend(atomics)

            # 递归追踪每个 driver 的源
            for atomic in atomics:
                sub_atomics = self._trace_drivers(
                    atomic.base_name,
                    atomic.bit_range,
                    depth + 1,
                    max_depth,
                    visited.copy(),
                )
                # 为子原子添加 evidence
                for sub in sub_atomics:
                    sub.evidence.append(EvidenceStep(
                        step_type="recursive",
                        description=f"tracing driver of {atomic.base_name}",
                        from_signal=atomic.base_name,
                        to_signals=[a.name for a in sub_atomics],
                    ))
                result.extend(sub_atomics)

        return result


# ==============================================================================
# Cycle 3: Driver 链追踪 + 端口检测
# ==============================================================================

