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
    defined_in: str = ""     # 定义类 (继承块 = 父类)
    inherited: bool = False  # 是否来自父类
    solve_before: list[dict] = field(default_factory=list)
    dist: list[dict] = field(default_factory=list)


class ConstraintTracer:
    """约束关系追踪 — 遍历 CONSTRAINS / HAS_* 边 (图内 class_graph_builder 建)."""

    def __init__(self, graph: SignalGraph, hierarchy=None):
        self.graph = graph
        self.hierarchy = hierarchy

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

    def trace_neighborhood(self, prop_id: str, max_depth: int = 6,
                           max_nodes: int = 200) -> dict | None:
        """One-shot constraint neighborhood across multiple constraint blocks.

        Starts at ``prop_id`` and walks every block that constrains the current
        property (including if-condition variables).  Edges are *co-constraint*
        relations, not dataflow: two variables are connected when they appear in
        the same constraint block.  Returns raw importance metrics; do not treat
        ``degree_centrality`` as a solver-semantic proof.
        """
        root = self._resolve_type_prop(prop_id)
        if not root:
            return None
        nodes: dict[str, dict] = {
            root: {"id": root, "depth": 0, "blocks": [], "neighbors": [],
                   "path": [root]},
        }
        queue = [root]
        relations: dict[tuple[str, str], set[str]] = {}
        while queue and len(nodes) < max_nodes:
            current = queue.pop(0)
            self._expand_constraint_node(
                current, nodes, queue, relations, max_depth, max_nodes)
        return self._build_neighborhood(root, nodes, relations)

    def _expand_constraint_node(self, current: str, nodes: dict, queue: list,
                                relations: dict, max_depth: int,
                                max_nodes: int) -> None:
        """Expand one variable's blocks into co-constraint neighbors."""
        for info in self.trace(current):
            members = self._block_members(current, info)
            for other in members:
                if other == current:
                    continue
                self._link(nodes, relations, current, other, info.block_id)
                depth = nodes[current]["depth"] + 1
                if (other not in nodes and depth <= max_depth
                        and len(nodes) < max_nodes):
                    nodes[other] = {
                        "id": other, "depth": depth, "blocks": [],
                        "neighbors": [], "path": nodes[current]["path"] + [other],
                    }
                    queue.append(other)

    @staticmethod
    def _block_members(current: str, info: ConstraintInfo) -> list[str]:
        members = []
        for v in list(info.vars) + list(info.conditions):
            if v not in members:
                members.append(v)
        if current not in members:
            members.append(current)
        return members

    @staticmethod
    def _link(nodes: dict, relations: dict, current: str, other: str,
              block: str) -> None:
        key = tuple(sorted((current, other)))
        relations.setdefault(key, set()).add(block)
        for a, b in ((current, other), (other, current)):
            if a in nodes:
                if b not in nodes[a]["neighbors"]:
                    nodes[a]["neighbors"].append(b)
                if block not in nodes[a]["blocks"]:
                    nodes[a]["blocks"].append(block)

    @staticmethod
    def _build_neighborhood(root: str, nodes: dict,
                            relations: dict) -> dict:
        out_nodes = []
        for node in nodes.values():
            node["block_count"] = len(node["blocks"])
            node["degree"] = len(node["neighbors"])
            out_nodes.append(node)
        out_nodes.sort(key=lambda n: (n["depth"], n["id"]))
        node_ids = set(nodes)
        out_relations = [
            {"source": a, "target": b, "blocks": sorted(blocks)}
            for (a, b), blocks in sorted(relations.items())
            if a in node_ids and b in node_ids
        ]
        total = max(1, len(out_nodes) - 1)
        root_node = nodes[root]
        direct = root_node["degree"]
        paths = {n["id"]: n["path"] for n in out_nodes if n["id"] != root}
        summary = {
            "node_count": len(out_nodes),
            "relation_count": len(out_relations),
            "direct_degree": direct,
            "reachable_count": len(out_nodes) - 1,
            "max_depth": max((n["depth"] for n in out_nodes), default=0),
            "degree_centrality": round(direct / total, 4),
            "importance_metrics": {
                "block_count": root_node["block_count"],
                "direct_degree": direct,
                "reachable_count": len(out_nodes) - 1,
                "degree_centrality": round(direct / total, 4),
            },
        }
        return {
            "root": root, "nodes": out_nodes, "relations": out_relations,
            "paths": paths, "summary": summary,
        }

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
        prefix, _, cname = block_id.rpartition(".")
        inherited_from = (nd.extra or {}).get("inherited_from") if nd else None
        if inherited_from:
            info.defined_in = inherited_from
        elif self.hierarchy is not None and prefix:
            owners = [prefix] + list(self.hierarchy.get_ancestors(prefix))
            for owner in owners:
                if owner != prefix and self.graph.get_node(f"{owner}.{cname}") is not None:
                    info.defined_in = owner
                    break
        info.defined_in = info.defined_in or prefix
        info.inherited = bool(prefix and info.defined_in != prefix)

        # solve 节点: block -CONSTRAINS-> CONSTRAINT_SOLVE; HAS_BEFORE -> vars
        for s_node, d_node in self.graph.edges():
            if s_node != block_id:
                continue
            for e in self.graph.get_edges(s_node, d_node):
                if e.kind != EdgeKind.CONSTRAINS:
                    continue
                sn = self.graph.get_node(d_node)
                if sn is None or sn.kind.name != "CONSTRAINT_SOLVE":
                    continue
                before = []
                for s2, d2 in self.graph.edges():
                    if s2 != d_node:
                        continue
                    for e2 in self.graph.get_edges(s2, d2):
                        if e2.kind == EdgeKind.HAS_BEFORE and d2 not in before:
                            before.append(d2)
                info.solve_before.append({"node": d_node, "before": before})

        # 表达式 → 变量 (HAS_LHS) / 条件 (HAS_CONDITION); if → consequent/alternate
        for eid in expr_ids:
            en = self.graph.get_node(eid)
            if en is None:
                continue
            if (en.extra or {}).get("dist"):
                info.dist.append({"node": eid, "items": en.extra["dist"],
                                  "confidence": en.extra.get("dist_confidence", "")})
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
