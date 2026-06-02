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

        主入口. 对于每个信号:
        1. 收集带 condition 的 incoming edges (复用 _collect_condition_edges)
        2. 从 condition 提取原子信号 (复用 _parse_expression_to_atomics)
        3. 沿 driver 链追踪每个原子 (复用 _trace_drivers)
        4. 合并去重所有原子信号
        5. 检查是否超 max_signals (报错/truncated)

        Args:
            signals: 用户输入的信号列表
            max_signals: 信号树最大数量 (默认 5)
            max_depth: driver 链最大深度

        Returns:
            DecompositionResult
        """
        result = DecompositionResult(original_signal=", ".join(signals))

        if not signals:
            result.error = "No signals provided"
            return result

        # V1: 只处理第一个信号 (后续可扩展为多信号)
        primary = signals[0]

        # 跨模块检测
        if self._is_cross_module(primary):
            result.error = (
                f"信号 {primary} 跨模块, 当前版本不支持. "
                f"请指定顶层模块信号 (如 top.x)."
            )
            return result

        # Step 1: 收集带 condition 的 incoming edges
        cond_edges = self._collect_condition_edges(primary)
        result.control_blocks = cond_edges  # 临时: 把 edges 作为 control_blocks 返回

        # Step 2: 收集所有原子信号 (从 condition + driver 表达式)
        all_atomics: list[AtomicSignal] = []
        seen: set[str] = set()  # 去重

        for edge in cond_edges:
            # 1. 从 condition 提取原子 (如 "en")
            cond = edge.effective_condition or edge.condition or ""
            cond_atomics = self._parse_expression_to_atomics(cond)
            for a in cond_atomics:
                if a.name not in seen:
                    seen.add(a.name)
                    all_atomics.append(a)

            # 2. 从 driver 表达式提取原子 (如 "c & d")
            expr = getattr(edge, "expression", "") or ""
            expr_atomics = self._parse_expression_to_atomics(expr)
            for a in expr_atomics:
                if a.name not in seen:
                    seen.add(a.name)
                    all_atomics.append(a)

        # 3. 沿 driver 链追踪所有原子
        # 用 primary 作为 context 推导完整 ID
        for atomic in list(all_atomics):
            recurse_id = self._resolve_signal_id(atomic.base_name, primary)
            sub_atomics = self._trace_drivers(
                recurse_id,
                atomic.bit_range,
                depth=1,
                max_depth=max_depth,
                visited=set(),
            )
            for sa in sub_atomics:
                if sa.name not in seen:
                    seen.add(sa.name)
                    all_atomics.append(sa)

        # Step 3: 限制 max_signals
        if len(all_atomics) > max_signals:
            result.atomic_signals = all_atomics[:max_signals]
            result.signal_count = len(all_atomics)
            result.truncated = True
            result.error = (
                f"Decomposition exceeds max_signals ({max_signals}): "
                f"found {len(all_atomics)} signals"
            )
        else:
            result.atomic_signals = all_atomics
            result.signal_count = len(all_atomics)

        result.depth_reached = max_depth
        return result

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

    def _collect_condition_edges(self, signal: str) -> list:
        """收集驱动该信号的所有带 condition 的边

        复用: graph.predecessors() 找所有 incoming edges

        Args:
            signal: 目标信号 ID

        Returns:
            TraceEdge 列表, 每条都有 effective_condition
        """
        if self._graph is None:
            return []

        result = []
        # SignalGraph 是 NetworkX DiGraph, predecessors 返回所有前驱节点 ID
        try:
            for src in self._graph.predecessors(signal):
                edge = self._graph.get_edge(src, signal)
                if edge is None:
                    continue
                # 优先用 effective_condition (去 reset), 回退到 raw condition
                cond = getattr(edge, "effective_condition", "") or ""
                if not cond:
                    cond = getattr(edge, "condition", "") or ""
                if cond:
                    result.append(edge)
        except Exception:
            return []
        return result

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
            signal: 起点信号完整 ID (如 "top.a")
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
            # 注意: 用 driver_id (完整 ID) 而非 atomic.base_name (可能已去模块前缀)
            for atomic in atomics:
                # 构造完整 ID: 如果 base_name 已含模块前缀, 直接用
                recurse_id = self._resolve_signal_id(atomic.base_name, driver_id)
                sub_atomics = self._trace_drivers(
                    recurse_id,
                    atomic.bit_range,
                    depth + 1,
                    max_depth,
                    visited.copy(),
                )
                # 为子原子添加 evidence
                for sub in sub_atomics:
                    sub.evidence.append(EvidenceStep(
                        step_type="recursive",
                        description=f"tracing driver of {recurse_id}",
                        from_signal=recurse_id,
                        to_signals=[a.name for a in sub_atomics],
                    ))
                result.extend(sub_atomics)

        return result

    def _resolve_signal_id(self, name: str, context_id: str) -> str:
        """解析信号名为完整 ID

        如果 name 已含模块前缀 (含 '.') 则直接返回,
        否则用 context_id 的模块前缀构造.

        Args:
            name: 简单名 (如 "a") 或完整 ID (如 "top.a")
            context_id: 上下文信号 ID (用于推导模块前缀)

        Returns:
            完整信号 ID
        """
        if "." in name:
            return name
        # 提取 context_id 的模块前缀
        if "." in context_id:
            prefix = context_id.rsplit(".", 1)[0]
            return f"{prefix}.{name}"
        return name

    def _is_cross_module(self, signal_id: str) -> bool:
        """检测信号 ID 是否跨模块

        信号 ID 格式:
        - "a" -> 单点, 不跨模块
        - "top.x" -> 双点 (模块.信号), 不跨模块
        - "top.sub.x" -> 三点, 跨模块

        Args:
            signal_id: 完整信号 ID

        Returns:
            True 如果是跨模块引用
        """
        if not signal_id:
            return False
        # 双点以下 (1个点分隔) 不算跨模块
        # 三点以上算跨模块
        parts = signal_id.split(".")
        return len(parts) > 2

    def _extract_atomics_from_ast(self, ast_node) -> list:
        """从 AST 节点提取原子信号

        [V2] 使用 SignalExpressionVisitor 解析 AST 节点,
        比字符串解析更准确 (支持复杂宏, typedef, 嵌套表达式).

        Args:
            ast_node: pyslang 表达式节点 (或类似可调用 extract() 的对象)

        Returns:
            AtomicSignal 列表
        """
        if ast_node is None:
            return []

        # 优先用 SignalExpressionVisitor (如果有 pyslang adapter)
        adapter = getattr(self._graph, "_adapter", None)
        if adapter is not None:
            try:
                from .visitors.signal_expression_visitor import SignalExpressionVisitor
                visitor = SignalExpressionVisitor(adapter)
                sr = visitor.extract(ast_node)
                if sr and sr.all_signals:
                    return self._convert_signal_result_to_atomics(sr, ast_node)
            except Exception:
                pass  # Fallback to string parsing

        # Fallback: 转为字符串
        try:
            text = str(ast_node).strip()
            return self._parse_expression_to_atomics(text)
        except Exception:
            return []

    def _convert_signal_result_to_atomics(self, sr, ast_node) -> list:
        """将 SignalResult 转为 AtomicSignal 列表

        Args:
            sr: SignalResult 实例
            ast_node: 原始 AST 节点 (用于 evidence)

        Returns:
            AtomicSignal 列表 (按出现顺序, 自动去重)
        """
        if not sr or not sr.all_signals:
            return []

        seen = set()
        result = []
        for name in sr.all_signals:
            if not name or name in seen:
                continue
            # 跳过字面量
            if name.isdigit() or self._is_simple_literal(name):
                continue
            seen.add(name)

            base_name, bit_range = self._split_identifier(name)
            atomic = AtomicSignal(
                name=name,
                base_name=base_name,
                bit_range=bit_range,
            )
            # 添加 evidence
            atomic.evidence.append(EvidenceStep(
                step_type="ast_extract",
                description=f"AST extract: {name} (kind={sr.kind_name or '?'})",
                from_signal=str(ast_node)[:50] if ast_node else "",
                to_signals=[name],
            ))
            result.append(atomic)
        return result

    def _is_simple_literal(self, name: str) -> bool:
        """检测是否为简单字面量 (4'b1011, 8'hFF)"""
        import re
        return bool(re.match(r"^\d+'(s?[dhbHoO])[0-9a-fA-FxXzZ?]+$", name))

    def _extract_condition_atomic(self, edge, src_signal: str) -> list:
        """从 TraceEdge 提取条件中的原子信号

        [V2] 优先用 condition_ast, 回退到字符串解析.

        Args:
            edge: TraceEdge 实例
            src_signal: 起点信号 (作为 context)

        Returns:
            AtomicSignal 列表
        """
        if edge is None:
            return []

        # 优先: 用 AST
        ast_node = getattr(edge, "condition_ast", None)
        if ast_node is not None:
            return self._extract_atomics_from_ast(ast_node)

        # Fallback: 用字符串 (effective_condition 优先, 然后 condition)
        cond = getattr(edge, "effective_condition", "") or ""
        if not cond:
            cond = getattr(edge, "condition", "") or ""
        return self._parse_expression_to_atomics(cond)

    def generate_coverage_markdown(self, result) -> str:
        """生成 Markdown 格式的分解报告

        Args:
            result: DecompositionResult 实例

        Returns:
            Markdown 文本
        """
        lines: list[str] = []

        # 标题
        lines.append("# 控制覆盖度分解报告")
        lines.append("")

        # 概要
        lines.append("## 概要")
        lines.append("")
        lines.append(f"- **原始信号**: `{result.original_signal}`")
        lines.append(
            f"- **原子信号数**: {result.signal_count} "
            f"({'超出限制' if result.truncated else 'OK'})"
        )
        lines.append(f"- **分解深度**: {result.depth_reached}")
        lines.append(f"- **控制块数**: {len(result.control_blocks)}")
        lines.append("")

        # 错误信息
        if result.error:
            lines.append("## ⚠️ 错误")
            lines.append("")
            lines.append(f"```\n{result.error}\n```")
            lines.append("")

        # 原子信号清单
        lines.append("## 原子信号清单")
        lines.append("")
        if not result.atomic_signals:
            lines.append("(无)")
        else:
            for i, sig in enumerate(result.atomic_signals, 1):
                lines.append(f"### {i}. `{sig.name}`")
                lines.append("")
                # 位选
                if sig.bit_range is not None:
                    high, low = sig.bit_range
                    if high == low:
                        lines.append(f"- **位选**: [{high}]")
                    else:
                        lines.append(f"- **位选**: [{high}:{low}]")
                else:
                    lines.append("- **位选**: 完整")
                # 源位置
                if sig.source and not sig.source.is_empty():
                    lines.append(f"- **源位置**: `{sig.source}`")
                # 证据链
                if sig.evidence:
                    lines.append("- **证据链**:")
                    for step in sig.evidence:
                        lines.append(f"  - ({step.step_type}) {step.description}")
                lines.append("")

        # 控制块详情
        if result.control_blocks:
            lines.append("## 控制块详情")
            lines.append("")
            for i, block in enumerate(result.control_blocks, 1):
                lines.append(f"### 控制块 #{i}")
                lines.append("")
                # block 可能是 TraceEdge 或 ControlBlock
                if hasattr(block, "effective_condition"):
                    cond = block.effective_condition or block.condition or ""
                    expr = getattr(block, "expression", "") or ""
                    lines.append(f"- **条件**: `{cond}`")
                    lines.append(f"- **驱动表达式**: `{expr}`")
                    src = getattr(block, "src", "")
                    dst = getattr(block, "dst", "")
                    if src and dst:
                        lines.append(f"- **边**: `{src}` → `{dst}`")
                else:
                    lines.append(f"- {block}")
                lines.append("")

        # 提示
        lines.append("---")
        lines.append("")
        lines.append("> 💡 **下一步**:")
        if result.atomic_signals:
            lines.append("> ")
            lines.append(f"> 将 {len(result.atomic_signals)} 个原子信号添加到 covergroup:")
            lines.append("> ")
            lines.append("> ```systemverilog")
            lines.append(f"> covergroup cg_{result.original_signal.replace('.', '_')} @ (posedge clk);")
            lines.append(">     // 自动生成的 cross 覆盖")
            names_str = ", ".join(s.name for s in result.atomic_signals)
            lines.append(f">     cross {names_str} {{")
            lines.append(">         // bins 由工具根据关键值生成")
            lines.append(">     }")
            lines.append("> endgroup")
        else:
            lines.append("> 无原子信号可生成")
        lines.append("")

        return "\n".join(lines)


# ==============================================================================
# Cycle 3: Driver 链追踪 + 端口检测
# ==============================================================================

