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
            # [V6.9] 纯 semantic AST 路径：通过 root.visit 找到所有 ConstraintBlock，
            #          从其 .constraints.list 中提取 condition/target 信号对
            classes = self._adapter.get_classes()
            for cls_node in classes:
                self._extract_pairs_from_class(cls_node, pairs)
        except Exception as e:
            logger.warning(f"Failed to extract constraint pairs: {e}")
        return pairs

    def _extract_pairs_from_class(self, cls_node, pairs: set):
        """[V6.9 semantic AST] 遍历 class 的 semantic AST 子节点，
        找到 ConstraintBlockSymbol，从中提取条件约束对。"""
        def visitor(node):
            kind = str(getattr(node, "kind", ""))
            if "ConstraintBlock" not in kind:
                return
            constraints = getattr(node, "constraints", None)
            if not constraints:
                return
            clist = getattr(constraints, "list", None)
            if not clist:
                return
            for ci in clist:
                cik = str(getattr(ci, "kind", ""))
                if "Conditional" in cik:
                    self._add_conditional_pairs(ci, pairs)
                elif "Implication" in cik:
                    self._add_implication_pairs(ci, pairs)
        # Use root.visit through the class node
        from trace.core.semantic_adapter import SemanticAdapter
        root = getattr(self._adapter, "_root", None)
        if root:
            root.visit(visitor)


    def _add_conditional_pairs(self, node, pairs: set):
        """[V6.9 semantic AST] 从 ConditionalConstraint 提取 (cond_var, target_var) 对"""
        pred = getattr(node, "predicate", None)
        ifbody = getattr(node, "ifBody", None)
        elsebody = getattr(node, "elseBody", None)
        cond = set(self._adapter._extract_signals_from_expr(pred) if pred else [])
        cons = set(self._expr_signals(ifbody))
        alt = set(self._expr_signals(elsebody))
        for cv in cond:
            for tv in (cons | alt):
                if cv and tv and cv != tv:
                    pairs.add((cv, tv))

    def _add_implication_pairs(self, node, pairs: set):
        """[V6.9 semantic AST] 从 ImplicationConstraint 提取 (pred_var, target_var) 对"""
        pred = getattr(node, "predicate", None)
        body = getattr(node, "body", None)
        pred_sigs = set(self._adapter._extract_signals_from_expr(pred) if pred else [])
        body_sigs = set(self._expr_signals(body))
        # [V6.9 fix] body 可能是 ConstraintList (多重约束), 需要展开提取信号
        if not body_sigs and body:
            clist = getattr(body, "list", None)
            if clist:
                for ci in clist:
                    body_sigs |= set(self._expr_signals(ci))
        for cv in pred_sigs:
            for tv in body_sigs:
                if cv and tv and cv != tv:
                    pairs.add((cv, tv))

    def _expr_signals(self, node) -> list[str]:
        """[V6.9 semantic AST] 从 ExpressionConstraint 或 ConstraintList 提取信号名"""
        if node is None:
            return []
        # ExpressionConstraint: 取 .expr
        expr = getattr(node, "expr", None)
        if expr is not None:
            return self._adapter._extract_signals_from_expr(expr)
        # [V6.9 fix] ConstraintList: 展开 .list 中每个 ExpressionConstraint
        clist = getattr(node, "list", None)
        if clist:
            sigs = []
            for ci in clist:
                e = getattr(ci, "expr", None)
                if e:
                    sigs.extend(self._adapter._extract_signals_from_expr(e))
            return sigs
        return []


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
