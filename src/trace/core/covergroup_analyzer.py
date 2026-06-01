# covergroup_analyzer.py - Covergroup ↔ Constraint 一致性分析器
#
# 比对 covergroup bins 与 constraint 的覆盖关系。
#
# [铁律3] 不可信则不输出

import logging
from dataclasses import dataclass

from .graph.covergroup_models import CovergroupInfo

logger = logging.getLogger(__name__)


@dataclass
class CoverageGap:
    """coverage 缺失报告"""

    kind: str  # "missing_bins" | "missing_illegal_bins" | "missing_cross"
    variable: str  # 相关变量
    description: str  # 描述
    constraint_block: str = ""  # 相关约束块
    severity: str = "warning"  # "warning" | "error"


class CovergroupAnalyzer:
    """Covergroup ↔ Constraint 一致性分析器

    输入:
    - constraint 信息 (来自 ClassGraphBuilder 的图结构)
    - covergroup 信息 (来自 CovergroupExtractor)

    输出:
    - CoverageGap 列表
    """

    def __init__(self, graph, cgs: list[CovergroupInfo]):
        """
        Args:
            graph: SignalGraph (包含 constraint 结构)
            cgs: CovergroupInfo 列表
        """
        self._graph = graph
        self._cgs = cgs

    def analyze(self, class_name: str = None) -> list[CoverageGap]:
        """执行完整分析

        Args:
            class_name: 可选，限定分析某个 class

        Returns:
            CoverageGap 列表
        """
        gaps = []

        for cg in self._cgs:
            if class_name and cg.in_class and cg.in_class != class_name:
                continue

            # 检查缺失的 cross
            gaps.extend(self._check_missing_cross(cg))

            # 检查条件约束的 illegal_bins
            gaps.extend(self._check_missing_illegal_bins(cg))

        return gaps

    # =========================================================================
    # 检查 1: 缺失的 cross coverage
    # =========================================================================

    def _check_missing_cross(self, cg: CovergroupInfo) -> list[CoverageGap]:
        """检查条件约束的变量是否在 cross 中

        逻辑: 如果 constraint 中有 if (a) { b ... } 形式的条件约束，
        则 a 和 b 应该出现在 cross 中。
        """
        gaps = []

        # 收集 coverpoint 信号名
        cp_signals = {cp.signal for cp in cg.coverpoints if cp.signal}

        # 收集已有 cross 的变量对
        cross_pairs = set()
        for cross in cg.crosses:
            items = [i for i in cross.items if i in cp_signals]
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    cross_pairs.add((items[i], items[j]))

        # 从图中找条件约束关系
        condition_pairs = self._find_condition_constraint_pairs()

        # 检查每对条件变量是否在 cross 中
        for cond_var, target_var in condition_pairs:
            if cond_var not in cp_signals or target_var not in cp_signals:
                continue

            pair = tuple(sorted([cond_var, target_var]))
            if pair not in cross_pairs:
                gaps.append(
                    CoverageGap(
                        kind="missing_cross",
                        variable=f"{cond_var} x {target_var}",
                        description=f"条件约束引用了 {cond_var} 和 {target_var}，但 covergroup 缺少 cross",
                        severity="warning",
                    )
                )

        return gaps

    def _find_condition_constraint_pairs(self) -> set[tuple[str, str]]:
        """从图中找条件约束的变量对

        通过 HAS_CONDITION 边找到条件变量，
        通过 HAS_CONSEQUENT/HAS_LHS 边找到被约束变量。

        返回: {(cond_var, target_var), ...}
        """
        from .graph.models import EdgeKind

        pairs = set()

        # 找所有 CONSTRAINT_IF 和 CONSTRAINT_IMPLIES 节点
        for node_id in self._graph.nodes():
            node = self._graph.get_node(node_id)
            if node is None:
                continue
            node_kind_str = str(node.kind)
            if "CONSTRAINT_IF" not in node_kind_str and "CONSTRAINT_IMPLIES" not in node_kind_str:
                continue

            # 找条件变量 (HAS_CONDITION 边)
            cond_vars = set()
            for src, dst in self._graph.edges():
                edge = self._graph.get_edge(src, dst)
                if edge.kind == EdgeKind.HAS_CONDITION and src == node_id:
                    # dst 是条件变量的 class property
                    # 提取变量名: packet.mode -> mode
                    var_name = dst.split(".")[-1] if "." in dst else dst
                    cond_vars.add(var_name)

            # 找被约束变量 (HAS_CONSEQUENT -> HAS_LHS)
            target_vars = set()
            for src, dst in self._graph.edges():
                edge = self._graph.get_edge(src, dst)
                if edge.kind == EdgeKind.HAS_CONSEQUENT and src == node_id:
                    # dst 是 CONSTRAINT_EXPR，继续找 HAS_LHS
                    for s2, d2 in self._graph.edges():
                        e2 = self._graph.get_edge(s2, d2)
                        if e2.kind == EdgeKind.HAS_LHS and s2 == dst:
                            var_name = d2.split(".")[-1] if "." in d2 else d2
                            target_vars.add(var_name)

            # 生成配对
            for cv in cond_vars:
                for tv in target_vars:
                    if cv != tv:
                        pairs.add((cv, tv))

        return pairs

    # =========================================================================
    # 检查 2: 缺失的 illegal_bins
    # =========================================================================

    def _check_missing_illegal_bins(self, cg: CovergroupInfo) -> list[CoverageGap]:
        """检查条件约束是否有对应的 illegal_bins

        逻辑: 对于 if (mode == 0) { addr < 64 } else { addr >= 64 }
        如果 covergroup 有 cross (mode, addr)，
        但没有 illegal_bins 标记 (mode==0, addr>=64) 的组合，
        则报告缺失。

        简化实现: 检查有 cross 且有条件约束的变量对，
        看 coverpoint 是否有 illegal_bins。
        """
        gaps = []

        # 收集有 illegal_bins 的 coverpoint
        signals_with_illegal = set()
        for cp in cg.coverpoints:
            for b in cp.bins:
                if b.kind == "illegal_bins":
                    signals_with_illegal.add(cp.signal)
                    break

        # 找有条件约束且有 cross 的变量对
        condition_pairs = self._find_condition_constraint_pairs()
        cross_signals = set()
        for cross in cg.crosses:
            cross_signals.update(cross.items)

        cp_signals = {cp.signal for cp in cg.coverpoints if cp.signal}

        for cond_var, target_var in condition_pairs:
            if cond_var not in cp_signals or target_var not in cp_signals:
                continue

            # 两个变量都在 cross 中
            if cond_var in cross_signals and target_var in cross_signals:
                # 检查目标变量是否有 illegal_bins
                if target_var not in signals_with_illegal:
                    # 检查条件变量是否有 illegal_bins
                    if cond_var not in signals_with_illegal:
                        gaps.append(
                            CoverageGap(
                                kind="missing_illegal_bins",
                                variable=target_var,
                                description=(
                                    f"条件约束 ({cond_var} -> {target_var}) 存在，"
                                    f"cross 也已定义，但缺少 illegal_bins 标记非法组合"
                                ),
                                severity="warning",
                            )
                        )

        return gaps
