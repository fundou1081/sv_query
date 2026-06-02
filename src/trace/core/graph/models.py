# ==============================================================================
# graph_models.py - 信号关系图模型
# ==============================================================================

from dataclasses import dataclass
from datetime import UTC
from enum import Enum, auto
from typing import Any

import networkx as nx


class NodeKind(Enum):
    SIGNAL = auto()
    WIRE = auto()
    REG = auto()
    PORT_IN = auto()
    PORT_OUT = auto()
    PORT_INOUT = auto()
    PARAM = auto()
    CONST = auto()
    INSTANTIATED_MODULE = auto()  # 实例节点 (top.inst)
    GENERATE_BLOCK = auto()  # generate 块节点 (top.GEN)

    # [Phase1a] Class & Constraint 节点类型
    CLASS = auto()  # class 定义节点 (packet)
    CLASS_INSTANCE = auto()  # class 实例 (top.p = new())
    CLASS_INSTANCE_PROPERTY = auto()  # class 实例成员 (top.p.addr, 通过实例访问的成员)
    CLASS_PROPERTY = auto()  # class 成员变量 (packet.addr, rand 变量)
    CONSTRAINT_BLOCK = auto()  # constraint c { ... } 命名块
    CONSTRAINT_EXPR = auto()  # 单条表达式约束
    CONSTRAINT_IF = auto()  # if 分支
    CONSTRAINT_ELSE = auto()  # else 分支
    CONSTRAINT_IMPLIES = auto()  # implication 左部 (en -> ...)
    CONSTRAINT_UNIQUE = auto()  # unique { ... }
    CONSTRAINT_SOLVE = auto()  # solve A before B
    CONSTRAINT_FOREACH = auto()  # foreach 循环
    CONSTRAINT_RANGE = auto()  # inside {0,1,2} 的集合
    EXPRESSION = auto()  # 表达式节点 (a + b, a & b)
    FUNCTION_CALL = auto()  # 函数调用节点


class EdgeKind(Enum):
    DRIVER = auto()  # 数据驱动 (q <= d)
    CLOCK = auto()  # 时钟触发 (clk -> q)
    RESET = auto()  # 异步复位 (rst_n -> q)
    CONNECTION = auto()  # 模块端口连接
    BIT_SELECT = auto()  # 位选择聚合

    # [Phase1a] Class & Constraint 边类型
    CONSTRAINS = auto()  # CLASS_PROPERTY ← 约束管控
    HAS_CONDITION = auto()  # CONSTRAINT_IF → CLASS_PROPERTY (条件变量)
    HAS_CONSEQUENT = auto()  # CONSTRAINT_IF → CONSTRAINT_EXPR (if 结果)
    HAS_ALTERNATE = auto()  # CONSTRAINT_ELSE → CONSTRAINT_EXPR (else 结果)
    HAS_LHS = auto()  # CONSTRAINT_EXPR → operand (左操作数)
    HAS_RHS = auto()  # CONSTRAINT_EXPR → operand (右操作数)
    HAS_MEMBER = auto()  # CONSTRAINT_UNIQUE → CLASS_PROPERTY (集合成员)
    HAS_LOOP_VAR = auto()  # CONSTRAINT_FOREACH → CLASS_PROPERTY (循环变量)
    HAS_BEFORE = auto()  # CONSTRAINT_SOLVE → CLASS_PROPERTY (before)
    HAS_AFTER = auto()  # CONSTRAINT_SOLVE → CLASS_PROPERTY (after)
    CONTAINS_MEMBER = auto()  # CLASS → CLASS_PROPERTY (组合/成员变量)
    IS_INSTANCE_OF = auto()  # CLASS_PROPERTY → CLASS (成员变量的类型引用)
    SUPER_CALL = auto()  # CONSTRAINT_EXPR → 被调用的父类约束 (增量扩展 super.c1)
    MEMBER_SELECT = auto()  # 实例成员访问: top.p.addr → top.p (p.addr 的 MEMBER_SELECT 边)


# [铁律16] 注意:ENABLE/DATA 不作为独立边类型
# - ENABLE: 用 TraceEdge.condition 属性替代,语义更清晰
# - DATA: 与 DRIVER 重复,保留 DRIVER 即可


@dataclass
class TraceNode:
    id: str
    name: str
    module: str
    kind: NodeKind
    width: tuple[int, int]
    bit_range: str | None = None
    file: str = ""
    line: int = 0
    is_clock: bool = False
    is_reset: bool = False
    is_enable: bool = False
    is_port: bool = False
    parent: str | None = None  # 方案C: 父节点ID (位选择→完整信号)
    parent_bit_start: int | None = None  # 位选在父节点中的起始位
    parent_bit_end: int | None = None  # 位选在父节点中的结束位
    modport_dir: str | None = None  # P0-3: modport direction (input/output/inout)


@dataclass
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str = ""
    condition: str = ""
    effective_condition: str = ""  # 判断清除后的条件（只保留直接相关的条件）
    condition_ast: Any | None = None  # [V2] 条件表达式 AST 节点 (供 SignalExpressionVisitor 解析)
    clock_domain: str = ""
    modport_dir: str | None = None  # P0-3: modport direction (input/output/inout)
    confidence: str = "high"
    expression: str = ""  # 驱动表达式 (如 "sreg_d", "a + b")
    bit_slice: str = ""  # 位选择 (如 "[8:1]")


@dataclass
class DriverInfo:
    """驱动信息 - 包含驱动节点及其驱动条件

    [方案C] 从 TraceNode 分离出来,因为 condition 是边的属性而非节点属性
    """

    node: TraceNode  # 驱动节点
    condition: str = ""  # 驱动条件 (来自 if 语句)
    reset_condition: str = ""  # 复位条件 (来自 if (!rst_ni))
    clock_domain: str = ""  # 时钟域
    assign_type: str = ""  # always_ff / always_comb / continuous / blocking / nonblocking
    distance: int = 1  # 驱动距离 (层级深度)
    expression: str = ""  # 驱动表达式 (如 sreg_d)
    bit_slice: str = ""  # 位选择 (如 [8:1])
    target_signal: str = ""  # 目标信号 (被驱动的信号)

    @property
    def id(self) -> str:
        return self.node.id

    @property
    def full_statement(self) -> str:
        """组装完整的驱动语句 (debug 用)

        例如: if (cond) sreg_d <= {rx, sreg_q[10:1]};
        """
        # 获取 LHS (目标信号)
        lhs = self.target_signal if self.target_signal else (self.node.id if hasattr(self, "node") else "?")

        # 组装条件
        cond = self.condition if self.condition else self.reset_condition
        if cond:
            stmt = f"if ({cond}) {lhs} "
        else:
            stmt = f"{lhs} "

        # 添加 assign_type
        assign_map = {
            "nonblocking": "<=",
            "blocking": "=",
            "continuous": "=",
        }
        assign_op = assign_map.get(self.assign_type, self.assign_type or "=")
        stmt += f"{assign_op} "

        # 添加表达式
        expr = self.expression if self.expression else "?"
        stmt += f"{expr};"

        # 添加时钟域注释
        if self.clock_domain:
            stmt += f" // @{self.clock_domain}"

        return stmt


class SignalGraph(nx.DiGraph):
    def __init__(self):
        super().__init__()
        self._node_data: dict[str, TraceNode] = {}
        # [FIX] 支持同一 (src, dst) 的多条边 (不同 condition)
        self._edge_data: dict[tuple[str, str], list[TraceEdge]] = {}
        self._port_to_internal: dict[str, str] = {}  # {inst_port_id: child_signal_id}

    def get_port_to_internal(self) -> dict[str, str]:
        """获取端口到内部信号的映射"""
        return self._port_to_internal

    def get_internal_signal(self, inst_port_id: str) -> str | None:
        """查询实例端口对应的内部信号

        Args:
            inst_port_id: 实例端口路径,如 'top.u_dut.clk'

        Returns:
            内部信号路径,如 'dut.clk',或 None
        """
        return self._port_to_internal.get(inst_port_id)

    def add_trace_node(self, node: TraceNode):
        self._node_data[node.id] = node
        super().add_node(node.id)

    def add_trace_edge(self, edge: TraceEdge):
        # [铁律4] 不允许创建孤儿节点:如果目标节点不存在则创建 placeholder
        # [FIX] 字面量节点(如 4'b1011, 8'h42)创建为 CONST 类型节点
        def _is_literal(node_id: str) -> bool:
            """检查是否为字面量常量"""
            if node_id and len(node_id) >= 3:
                # 匹配 4'b0, 1'b1, 4'b1011, 8'hFF, 11'd0 等
                if "'" in node_id and node_id[0].isdigit():
                    return True
            return False

        for node_id in [edge.src, edge.dst]:
            if node_id not in self._node_data:
                if _is_literal(node_id):
                    # 字面量创建为 CONST 类型节点
                    parts = node_id.split(".", 1)
                    module = parts[0] if len(parts) > 1 else ""
                    name = parts[1] if len(parts) > 1 else node_id
                    literal_node = TraceNode(id=node_id, name=name, module=module, kind=NodeKind.CONST, width=(0, 0))
                    self._node_data[node_id] = literal_node
                    super().add_node(node_id)
                else:
                    parts = node_id.split(".", 1)
                    module = parts[0] if len(parts) > 0 else ""
                    name = parts[1] if len(parts) > 1 else node_id

                    placeholder = TraceNode(id=node_id, name=name, module=module, kind=NodeKind.SIGNAL, width=(0, 0))
                    self._node_data[node_id] = placeholder
                    super().add_node(node_id)

        # [FIX] 支持同一 (src, dst) 多条边：append 到列表，不去重
        # 只要 (src, dst, kind, condition) 完全相同才去重
        key = (edge.src, edge.dst)

        if key not in self._edge_data:
            self._edge_data[key] = []

        # 检查是否完全重复（所有属性都相同）
        for existing_edge in self._edge_data[key]:
            if (
                existing_edge.kind == edge.kind
                and existing_edge.condition == edge.condition
                and existing_edge.assign_type == edge.assign_type
                and existing_edge.expression == edge.expression
            ):
                return  # 完全重复，跳过

        # 添加新边到列表
        self._edge_data[key].append(edge)
        super().add_edge(edge.src, edge.dst)

        # 自动计算 effective_condition
        if edge.condition and not edge.effective_condition:
            edge.effective_condition = SignalGraph.compute_effective_condition(edge.condition)

    def set_node_modport_dir(self, node_id: str, modport_dir: str):
        """[P0-3] 设置已有节点的 modport_dir 属性"""
        if node_id in self._node_data:
            self._node_data[node_id].modport_dir = modport_dir

    def get_node(self, node_id: str) -> TraceNode | None:
        return self._node_data.get(node_id)

    def get_edge(self, src: str, dst: str) -> TraceEdge | None:
        """获取 (src, dst) 的第一条边（向后兼容，按优先级排序）"""
        edges = self._edge_data.get((src, dst), [])
        if not edges:
            return None
        # 返回排序后的第一条（优先级最高）
        return self._sort_edges(edges)[0]

    def get_edges(self, src: str, dst: str) -> list[TraceEdge]:
        """获取 (src, dst) 的所有边（按优先级排序）"""
        edges = self._edge_data.get((src, dst), [])
        return self._sort_edges(edges)

    @staticmethod
    def compute_effective_condition(condition: str) -> str:
        """计算判断清除后的条件

        从嵌套条件中提取直接相关的条件。
        例如:
            - '!!rst_n && state == DONE' -> 'state == DONE'
            - 'en && a' -> 'a'
            - 'state == IDLE' -> 'state == IDLE'

        规则:
            1. 如果 condition 中包含 '&&' 或 '||'
            2. 提取最后一个逻辑单元（通常是状态判断或信号本身）
            3. 忽略简单的 reset 条件（如 '!rst_n'）
        """
        if not condition or "&&" not in condition:
            return condition

        import re

        # 移除空格
        stripped = condition.replace(" ", "")

        # 分割 && 部分
        parts = stripped.split("&&")

        # 找最后一个包含 == 或 =~ 或信号引用的部分
        for part in reversed(parts):
            part = part.strip()
            # 跳过 reset 条件
            if re.match(r"^(!|~~|~)rst", part, re.IGNORECASE):
                continue
            if re.match(r"^(!|~~|~)reset", part, re.IGNORECASE):
                continue
            # 保留其他部分
            return part

        return condition

    def set_lifo_order(self, state_values: list[str]):
        """设置 LIFO 顺序的状态值列表，用于边排序

        Args:
            state_values: 状态值列表，按语义优先级升序排列
                         后面的状态优先级更高 (LIFO)
                         例如: ['REQ', 'DONE', 'IDLE'] 表示 IDLE 优先级最高
        """
        self._lifo_priority = {sv: i for i, sv in enumerate(state_values)}

    def _sort_edges(self, edges: list[TraceEdge]) -> list[TraceEdge]:
        """边排序：reset 条件优先，然后按 LIFO 顺序（from_state 优先级）"""
        lifo_priority = getattr(self, "_lifo_priority", {})

        def edge_priority(e: TraceEdge) -> tuple:
            # reset 条件 = 不包含 && 或 || 且包含 rst/reset
            is_reset = False
            if e.condition:
                stripped = e.condition.replace(" ", "")
                has_logical = "&&" in stripped or "||" in stripped
                has_reset = "rst" in stripped.lower() or "reset" in stripped.lower()
                is_reset = has_reset and not has_logical

            # 提取 from_state (从 condition 中找 state == X)
            from_state = None
            if e.condition and not is_reset:
                import re

                m = re.search(r"state\s*(?:==|===)\s*(\w+)", e.condition)
                if m:
                    from_state = m.group(1)

            # LIFO 优先级：from_state 在预定义列表中的位置
            # 列表后面的状态优先级更高 (LIFO)
            state_priority = len(lifo_priority)  # 默认最低（不在列表中）
            if from_state in lifo_priority:
                pos = lifo_priority[from_state]
                state_priority = len(lifo_priority) - pos  # 逆序：后面的优先级高

            # (是否是 reset, LIFO 优先级, condition 长度, condition 字符串)
            return (not is_reset, state_priority, len(e.condition or ""), e.condition or "")

        return sorted(edges, key=edge_priority)

    def find_drivers(self, signal_id: str) -> list[TraceNode]:
        return [self.get_node(n) for n in self.predecessors(signal_id)]

    def find_loads(self, signal_id: str) -> list[TraceNode]:
        return [self.get_node(n) for n in self.successors(signal_id)]

    def find_path(self, src_id: str, dst_id: str) -> list[str]:
        try:
            return nx.shortest_path(self, src_id, dst_id)
        except nx.NetworkXNoPath:
            return []

    def find_all_paths(self, src_id: str, dst_id: str, max_depth: int = 10) -> list[list[str]]:
        try:
            return list(nx.all_simple_paths(self, src_id, dst_id, cutoff=max_depth))
        except Exception:
            return []

    def detect_cycles(self) -> list[list[str]]:
        try:
            return list(nx.simple_cycles(self))
        except Exception:
            return []

    def stats(self) -> dict:
        return {
            "nodes": self.number_of_nodes(),
            "edges": self.number_of_edges(),
        }

    # ==============================================================================
    # Snapshot 序列化 - 支持完整 SignalGraph 持久化
    # [铁律13] 金标准测试优先
    # ==============================================================================

    def to_dict(self) -> dict:
        """[Golden] 完整序列化 SignalGraph 为可 JSON 化的字典

        金标准输出格式:
        {
            "version": "1.0",
            "created_at": "ISO timestamp",
            "node_count": int,
            "edge_count": int,
            "port_to_internal": Dict[str, str],
            "nodes": [
                {"id": str, "name": str, "module": str, "kind": str, ...},
                ...
            ],
            "edges": [
                {"src": str, "dst": str, "kind": str, ...},
                ...
            ]
        }
        """
        nodes_data = []
        for node_id in self.nodes():
            node = self._node_data.get(node_id)
            if node:
                nodes_data.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "module": node.module,
                        "kind": node.kind.name if isinstance(node.kind, NodeKind) else str(node.kind),
                        "width": list(node.width),
                        "bit_range": node.bit_range,
                        "file": node.file,
                        "line": node.line,
                        "is_clock": node.is_clock,
                        "is_reset": node.is_reset,
                        "is_enable": node.is_enable,
                        "is_port": node.is_port,
                        "parent": node.parent,
                        "parent_bit_start": node.parent_bit_start,
                        "parent_bit_end": node.parent_bit_end,
                        "modport_dir": node.modport_dir,
                    }
                )

        edges_data = []
        for src, dst in self.edges():
            edges = self._edge_data.get((src, dst), [])
            for edge in edges:
                edges_data.append(
                    {
                        "src": edge.src,
                        "dst": edge.dst,
                        "kind": edge.kind.name if isinstance(edge.kind, EdgeKind) else str(edge.kind),
                        "assign_type": edge.assign_type,
                        "condition": edge.condition,
                        "clock_domain": edge.clock_domain,
                        "modport_dir": edge.modport_dir,
                        "confidence": edge.confidence,
                    }
                )

        return {
            "version": "1.0",
            "created_at": "",  # 由调用方填充
            "node_count": len(nodes_data),
            "edge_count": len(edges_data),
            "port_to_internal": dict(self._port_to_internal),
            "nodes": nodes_data,
            "edges": edges_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SignalGraph":
        """[Golden] 从字典反序列化重建 SignalGraph

        金标准:
        - 遍历 nodes 重建 TraceNode
        - 遍历 edges 重建 TraceEdge
        - 恢复 port_to_internal 映射
        """
        graph = cls()

        # 恢复 port_to_internal
        if "port_to_internal" in data:
            graph._port_to_internal.update(data["port_to_internal"])

        # 恢复节点
        for node_dict in data.get("nodes", []):
            kind_str = node_dict.get("kind", "SIGNAL")
            # 尝试解析 NodeKind 枚举
            try:
                kind = NodeKind[kind_str]
            except (KeyError, TypeError):
                kind = NodeKind.SIGNAL

            node = TraceNode(
                id=node_dict["id"],
                name=node_dict.get("name", ""),
                module=node_dict.get("module", ""),
                kind=kind,
                width=tuple(node_dict.get("width", [0, 0])),
                bit_range=node_dict.get("bit_range"),
                file=node_dict.get("file", ""),
                line=node_dict.get("line", 0),
                is_clock=node_dict.get("is_clock", False),
                is_reset=node_dict.get("is_reset", False),
                is_enable=node_dict.get("is_enable", False),
                is_port=node_dict.get("is_port", False),
                parent=node_dict.get("parent"),
                parent_bit_start=node_dict.get("parent_bit_start"),
                parent_bit_end=node_dict.get("parent_bit_end"),
                modport_dir=node_dict.get("modport_dir"),
            )
            graph.add_trace_node(node)

        # 恢复边
        for edge_dict in data.get("edges", []):
            kind_str = edge_dict.get("kind", "DRIVER")
            # 尝试解析 EdgeKind 枚举
            try:
                kind = EdgeKind[kind_str]
            except (KeyError, TypeError):
                kind = EdgeKind.DRIVER

            edge = TraceEdge(
                src=edge_dict["src"],
                dst=edge_dict["dst"],
                kind=kind,
                assign_type=edge_dict.get("assign_type", ""),
                condition=edge_dict.get("condition", ""),
                clock_domain=edge_dict.get("clock_domain", ""),
                modport_dir=edge_dict.get("modport_dir"),
                confidence=edge_dict.get("confidence", "high"),
            )
            graph.add_trace_edge(edge)

        return graph

    def to_json(self, indent: int = 2) -> str:
        """[Golden] 序列化为 JSON 字符串"""
        import json

        data = self.to_dict()
        return json.dumps(data, indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "SignalGraph":
        """[Golden] 从 JSON 字符串反序列化"""
        import json

        data = json.loads(json_str)
        return cls.from_dict(data)

    def save_snapshot(self, path: str, tag: str = "", git_commit: str = "", files: list = None):
        """[Golden] 保存快照到文件

        Args:
            path: 快照文件路径
            tag: 快照标签(如 "v1.2.3" 或 "feature-x")
            git_commit: Git commit hash
            files: 相关的源文件列表
        """
        import json
        from datetime import datetime

        data = self.to_dict()
        data["tag"] = tag
        data["git_commit"] = git_commit
        data["files"] = files or []
        data["created_at"] = datetime.now(UTC).isoformat()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load_snapshot(cls, path: str) -> "SignalGraph":
        """[Golden] 从文件加载快照"""
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
