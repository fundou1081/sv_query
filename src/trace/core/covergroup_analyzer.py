# covergroup_analyzer.py - Covergroup ↔ Constraint 一致性分析器
#
# [V6.9 2026-07-29] 重写：用 pyslang semantic API 直接抽取 constraint 和 covergroup
# 内容，不再依赖 graph 中的 syntax AST 节点（CONSTRAINT_IF/CONSTRAINT_IMPLIES 等）。
#
# 核心思路：
#   1. 用 semantic adapter 从 class body 中找出 constraint 块
#   2. 解析 constraint 的 if/else/implication 结构，提取 (cond_var, target_var) 对
#   3. 用 CovergroupExtractor 抽取 covergroup 的 coverpoints/crosses/illegal_bins
#   4. 做语义层面的 gap 比对

import logging
import re
from dataclasses import dataclass

from .graph.covergroup_models import CovergroupInfo

logger = logging.getLogger(__name__)


@dataclass
class CoverageGap:
    """coverage 缺失报告"""
    kind: str  # "missing_bins" | "missing_illegal_bins" | "missing_cross"
    variable: str
    description: str
    constraint_block: str = ""
    severity: str = "warning"


class CovergroupAnalyzer:
    """Covergroup ↔ Constraint 一致性分析器（semantic API 版）

    输入:
    - adapter: PyslangAdapter (semantic AST)
    - cgs: CovergroupInfo 列表

    输出:
    - CoverageGap 列表
    """

    def __init__(self, adapter, cgs: list[CovergroupInfo]):
        self._adapter = adapter
        self._cgs = cgs

    def analyze(self, class_name: str = None) -> list[CoverageGap]:
        gaps = []
        for cg in self._cgs:
            if class_name and cg.in_class and cg.in_class != class_name:
                continue
            gaps.extend(self._check_missing_cross(cg))
            gaps.extend(self._check_missing_illegal_bins(cg))
        return gaps

    # =========================================================================
    # 核心：用 semantic API 从源码中抽取 constraint 条件关系
    # =========================================================================

    def _find_condition_constraint_pairs(self) -> set[tuple[str, str]]:
        """[V6.9] 用 semantic API 从 class body 中抽取 constraint 条件关系。
        
        直接遍历 semantic ClassType 的成员（Symbol），
        找到 ConstraintBlock 后从其 syntax 层提取条件约束对。
        """
        pairs = set()
        try:
            classes = self._adapter.get_classes()
            for cls_node in classes:
                # 遍历 semantic class members (Symbols)
                for member in cls_node:
                    kind_str = str(getattr(member, "kind", ""))
                    if "ConstraintBlock" in kind_str:
                        pairs.update(self._extract_constraint_pairs(member, str(getattr(member, "name", ""))))
        except Exception as e:
            logger.warning(f"Failed to extract constraint pairs: {e}")
        return pairs

    def _extract_constraint_pairs(self, node, cls_name: str) -> set[tuple[str, str]]:
        """[V6.9] 从 semantic ConstraintBlock 的 syntax 层提取 (cond_var, target_var) 对。
        
        node 是 semantic Symbol(ConstraintBlock)，通过 node.syntax.block 获取
        syntax AST 的 ConstraintBlockSyntax，遍历其 items 找条件约束关系。
        
        支持:
          - if (cond) { expr... } else { ... }
          - if (cond) { expr... }
          - cond -> expr (implication)
        """
        pairs = set()
        kind_str = str(getattr(node, "kind", ""))
        if "ConstraintBlock" not in kind_str:
            return pairs

        # 从 semantic node 获取 syntax AST 的 constraint block
        syntax = getattr(node, "syntax", None)
        if syntax is None:
            return pairs
        block = getattr(syntax, "block", None)  # pyslang 属性名是 "block"
        if block is None:
            return pairs

        # 遍历 constraint block items
        try:
            items = block.items if hasattr(block, 'items') else []
        except Exception:
            return pairs

        for item in items:
            if item is None:
                continue
            item_kind = str(getattr(item, "kind", ""))

            # ConditionalConstraint: if (cond) { ... } else { ... }
            if "ConditionalConstraint" in item_kind:
                cond = self._extract_signals_from_node(getattr(item, "condition", None))
                cons = self._extract_signals_from_node(getattr(item, "constraints", None))
                alt = self._extract_signals_from_node(getattr(item, "elseClause", None))
                for cv in cond:
                    for tv in (cons | alt):
                        if cv != tv:
                            pairs.add((cv, tv))

            # ImplicationConstraint: cond -> expr
            elif "ImplicationConstraint" in item_kind:
                left = self._extract_signals_from_node(getattr(item, "left", None))
                right = self._extract_signals_from_node(getattr(item, "right", None))
                for cv in left:
                    for tv in right:
                        if cv != tv:
                            pairs.add((cv, tv))

        return pairs

    def _extract_signals_from_node(self, node) -> set[str]:
        """[V6.9] 从 constraint expression 节点中提取信号名。

        对 syntax AST 节点（IdentifierName / Expression）直接提取标识符。
        syntax 层只用于 constraint block 的 structural 解析，
        信号名提取用 pyslang 原生 API。
        """
        if node is None:
            return set()
        
        signals = set()
        self._walk_signals(node, signals)
        return signals

    def _walk_signals(self, node, signals: set[str]):
        """[V6.9] 递归遍历 syntax AST 节点，收集IdentifierName作为信号名。
        
        这是 syntax 独立工具的典型用法——只用于结构遍历，
        不参与 semantic 信号提取。
        """
        if node is None:
            return
        
        kind_str = str(getattr(node, "kind", ""))
        
        # IdentifierName: 提取标识符
        if "IdentifierName" in kind_str:
            # 尝试获取 semantic symbol name
            sym = getattr(node, "symbol", None)
            if sym and hasattr(sym, "name"):
                name = str(sym.name).strip()
                if name and not name.isdigit():
                    signals.add(name)
                    return
            # fallback: 从 syntax 层提取
            try:
                name = str(node).strip()
                if name and not name.isdigit():
                    signals.add(name)
            except Exception:
                pass
            return
        
        # NamedValue: semantic symbol 引用
        if "NamedValue" in kind_str:
            sym = getattr(node, "symbol", None)
            if sym and hasattr(sym, "name"):
                name = str(sym.name).strip()
                if name and not name.isdigit():
                    signals.add(name)
            return
        
        # 递归处理子节点
        for attr in ("left", "right", "operand", "condition", "expression",
                     "arguments", "elements", "items"):
            child = getattr(node, attr, None)
            if child is not None:
                if hasattr(child, "__iter__") and not isinstance(child, str):
                    try:
                        for c in child:
                            self._walk_signals(c, signals)
                    except Exception:
                        pass
                else:
                    self._walk_signals(child, signals)
        
        # 通用递归：遍历所有子属性
        try:
            if hasattr(node, "__iter__") and not isinstance(node, str):
                for child in node:
                    self._walk_signals(child, signals)
        except Exception:
            pass

    # =========================================================================
    # 检查 1: 缺失的 cross coverage
    # =========================================================================

    def _check_missing_cross(self, cg: CovergroupInfo) -> list[CoverageGap]:
        """检查条件约束的变量是否在 cross 中"""
        gaps = []
        cp_signals = {cp.signal for cp in cg.coverpoints if cp.signal}

        # 收集已有 cross 的变量对
        cross_pairs = set()
        cp_names = {cp.name for cp in cg.coverpoints if cp.name}
        name_to_signal = {cp.name: cp.signal for cp in cg.coverpoints if cp.name and cp.signal}
        for cross in cg.crosses:
            normalized = []
            for item in cross.items:
                if item in cp_signals:
                    normalized.append(item)
                elif item in name_to_signal:
                    normalized.append(name_to_signal[item])
            for i in range(len(normalized)):
                for j in range(i + 1, len(normalized)):
                    cross_pairs.add(tuple(sorted([normalized[i], normalized[j]])))

        # [V6.9] 用 semantic API 抽取 constraint pairs（替代 graph 查询）
        condition_pairs = self._find_condition_constraint_pairs()

        for cond_var, target_var in condition_pairs:
            if cond_var not in cp_signals or target_var not in cp_signals:
                continue
            pair = tuple(sorted([cond_var, target_var]))
            if pair not in cross_pairs:
                gaps.append(CoverageGap(
                    kind="missing_cross",
                    variable=f"{cond_var} x {target_var}",
                    description=f"条件约束引用了 {cond_var} 和 {target_var}，但 covergroup 缺少 cross",
                    severity="warning",
                ))
        return gaps

    # =========================================================================
    # 检查 2: 缺失的 illegal_bins
    # =========================================================================

    def _check_missing_illegal_bins(self, cg: CovergroupInfo) -> list[CoverageGap]:
        """检查条件约束是否有对应的 illegal_bins"""
        gaps = []
        signals_with_illegal = set()
        for cp in cg.coverpoints:
            for b in cp.bins:
                if b.kind == "illegal_bins":
                    signals_with_illegal.add(cp.signal)
                    break

        condition_pairs = self._find_condition_constraint_pairs()
        cross_signals = set()
        for cross in cg.crosses:
            cross_signals.update(cross.items)
        cp_signals = {cp.signal for cp in cg.coverpoints if cp.signal}

        for cond_var, target_var in condition_pairs:
            if cond_var not in cp_signals or target_var not in cp_signals:
                continue
            if cond_var in cross_signals and target_var in cross_signals:
                if target_var not in signals_with_illegal:
                    if cond_var not in signals_with_illegal:
                        gaps.append(CoverageGap(
                            kind="missing_illegal_bins",
                            variable=target_var,
                            description=(
                                f"条件约束 ({cond_var} -> {target_var}) 存在，"
                                f"cross 也已定义，但缺少 illegal_bins 标记非法组合"
                            ),
                            severity="warning",
                        ))
        return gaps
