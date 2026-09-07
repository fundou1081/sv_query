# ==============================================================================
# query/constraint.py - Constraint 关系追踪 (iter_153 C3)
#
# 架构决策 D4: 约束 = 声明式关系 (CONSTRAINS/HAS_* 边), 非数据流 —
# 独立 tracer, 不走数据 fanin (iter_139 原则)。范式可复用 covergroup。
#
# 回答: "这个 (rand) 属性受哪些约束?" / "约束块约束了哪些变量?"
# ==============================================================================
from dataclasses import dataclass, field

from ..graph.models import EdgeKind, NodeKind, SignalGraph


@dataclass
class ConstraintInfo:
    """单个约束块对某属性的约束信息."""

    block_id: str            # CONSTRAINT_BLOCK (packet.c_addr)
    vars: list[str] = field(default_factory=list)      # 被约束变量 (HAS_LHS 目标)
    conditions: list[str] = field(default_factory=list)  # 条件变量 (if 约束 HAS_CONDITION)
    expr_count: int = 0      # 块内表达式数


class ConstraintTracer:
    """约束关系追踪 — 遍历 CONSTRAINS / HAS_* 边 (图内 class_graph_builder 建)."""

    def __init__(self, graph: SignalGraph):
        self.graph = graph

    def trace(self, prop_id: str) -> list[ConstraintInfo]:
        """查属性受哪些约束.

        prop_id 支持:
        - 类型级属性 (packet.addr)
        - 实例属性 (top.p.addr) — 自动经 MEMBER_SELECT 反向解析类型属性
          (约束定义在类型级, 作用于所有实例 — D3)
        """
        type_prop = self._resolve_type_prop(prop_id)
        if not type_prop:
            return []

        # 反向 CONSTRAINS: 谁约束 type_prop (约束块 / class — 只留 CONSTRAINT_BLOCK)
        block_ids = []
        for s, d in self.graph.edges():
            if d != type_prop:
                continue
            for e in self.graph.get_edges(s, d):
                if e.kind != EdgeKind.CONSTRAINS:
                    continue
                nd = self.graph.get_node(s)
                if nd and nd.kind.name == "CONSTRAINT_BLOCK":
                    block_ids.append(s)

        out = []
        for block_id in sorted(set(block_ids)):
            info = self._analyze_block(block_id)
            if info:
                out.append(info)
        return out

    # ------------------------------------------------------------------
    def _resolve_type_prop(self, prop_id: str) -> str | None:
        """实例属性 (top.p.addr / top.e.p.addr) → 类型属性 (packet.addr).

        路径 1: 反向 MEMBER_SELECT (CLASS_INSTANCE_PROPERTY 有出边到类型成员,
        iter_152 实证)。路径 2 (fallback): 实例前缀 → IS_INSTANCE_OF → 类 →
        成员链走类型 (iter_153 单级 top.p.addr; **iter_168 嵌套
        top.e.p.addr**: 逐级实例前缀 (最长优先) + class 类型成员递归 —
        env.p 成员槽 tb_env.p 经 IS_INSTANCE_OF → packet, 续 addr →
        packet.addr)。REG 化的实例属性 (被 always_ff 驱动, kind=REG) 可能
        无 MEMBER_SELECT 出边 — 路径 2 兜底。
        """
        node = self.graph.get_node(prop_id)
        if node is not None and node.kind.name == "CLASS_PROPERTY":
            return prop_id
        # 路径 1: s(prop_id) -MEMBER_SELECT-> d(类型成员)
        for s, d in self.graph.edges():
            if s != prop_id:
                continue
            for e in self.graph.get_edges(s, d):
                if e.kind != EdgeKind.MEMBER_SELECT:
                    continue
                nd = self.graph.get_node(d)
                if nd and nd.kind.name == "CLASS_PROPERTY":
                    return d
        # 路径 2: <实例前缀>.<成员链> — 逐级前缀 (最长优先) 解析实例类,
        # 成员链沿 class 类型递归 (嵌套实例 top.e.p.addr)。
        parts = prop_id.split(".")
        for k in range(len(parts) - 1, 0, -1):
            inst_id = ".".join(parts[:k])
            cls = self._isa_class(inst_id)
            if not cls:
                continue
            type_member = self._walk_member_type(cls, parts[k:])
            if type_member:
                return type_member
        return None

    def _isa_class(self, inst_id: str) -> str | None:
        """实例节点 → IS_INSTANCE_OF 类型 (无实例节点/非实例 → None)."""
        nd = self.graph.get_node(inst_id)
        if nd is None or nd.kind.name != "CLASS_INSTANCE":
            return None
        for s, d in self.graph.edges():
            if s != inst_id:
                continue
            for e in self.graph.get_edges(s, d):
                if e.kind == EdgeKind.IS_INSTANCE_OF:
                    return d
        return None

    def _walk_member_type(self, cls: str, parts: list[str]) -> str | None:
        """类型成员链: packet + ['addr'] → packet.addr; env 成员 p 是 class
        类型 → 经 tb_env.p IS_INSTANCE_OF 续下一段 (嵌套 top.e.p.addr)."""
        if not parts:
            return None
        head, rest = parts[0], parts[1:]
        nid = f"{cls}.{head}"
        nd = self.graph.get_node(nid)
        if nd is None:
            return None
        if nd.kind.name == "CLASS_PROPERTY" and not rest:
            return nid
        if nd.kind.name == "CLASS_INSTANCE" and rest:
            sub_cls = self._isa_class(nid)
            if sub_cls:
                return self._walk_member_type(sub_cls, rest)
        return None

    def _analyze_block(self, block_id: str) -> ConstraintInfo | None:
        """分析约束块: 约束变量 (expr 的 HAS_LHS) + 条件变量 (if HAS_CONDITION)."""
        nd = self.graph.get_node(block_id)
        if nd is None or nd.kind.name != "CONSTRAINT_BLOCK":
            return None
        info = ConstraintInfo(block_id=block_id)

        # 块内表达式: block -CONSTRAINS-> expr 节点
        expr_ids = []
        for s, d in self.graph.edges():
            if s != block_id:
                continue
            for e in self.graph.get_edges(s, d):
                if e.kind != EdgeKind.CONSTRAINS:
                    continue
                en = self.graph.get_node(d)
                if en and en.kind.name in ("CONSTRAINT_EXPR", "CONSTRAINT_IF", "CONSTRAINT_ELSE"):
                    expr_ids.append(d)
        info.expr_count = len(expr_ids)

        # 表达式 → 变量 (HAS_LHS) / 条件 (HAS_CONDITION); if → consequent/alternate
        for eid in expr_ids:
            en = self.graph.get_node(eid)
            if en is None:
                continue
            for s, d in self.graph.edges():
                if s != eid:
                    continue
                for e in self.graph.get_edges(s, d):
                    if e.kind == EdgeKind.HAS_LHS and d not in info.vars:
                        info.vars.append(d)
                    elif e.kind == EdgeKind.HAS_CONDITION and d not in info.conditions:
                        info.conditions.append(d)
            # if 的 consequent/alternate 表达式继续收 (expr 层)
            for s, d in self.graph.edges():
                if s != eid:
                    continue
                for e in self.graph.get_edges(s, d):
                    if e.kind in (EdgeKind.HAS_CONSEQUENT, EdgeKind.HAS_ALTERNATE):
                        for s2, d2 in self.graph.edges():
                            if s2 == d:
                                for e2 in self.graph.get_edges(s2, d2):
                                    if e2.kind == EdgeKind.HAS_LHS and d2 not in info.vars:
                                        info.vars.append(d2)
        return info
