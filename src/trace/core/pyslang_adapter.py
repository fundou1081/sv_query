# ==============================================================================
# pyslang_adapter.py - 适配器
# 使用 SemanticCollector 模式
# ==============================================================================


from data_models import (
    CombinationalDriverCollector,
    ConnectionEdge,
    DriverCollector,
    SequentialDriverCollector,
    SignalChain,
    SignalNode,
    new_signal_chain,
    new_signal_node,
)

from trace.core._pyslang_compat import SyntaxKind, SyntaxTree  # [Stage 6] v10/v11 兼容


class PyslangAdapter:
    def __init__(self, tree: SyntaxTree):
        self.tree = tree
        self.module = self._get_module()
        self.module_name = "top"
        if self.module and self.module.header:
            self.module_name = self.module.header.name

        self.nodes: dict[str, SignalNode] = {}
        self.drivers: dict[str, list[ConnectionEdge]] = {}
        self.loads: dict[str, list[ConnectionEdge]] = {}

        # 收集器
        self.driver_clf = DriverCollector
        self.seq_clf = SequentialDriverCollector
        self.comb_clf = CombinationalDriverCollector

    def _get_module(self):
        return self.tree.root.members[0] if self.tree.root and self.tree.root.members else None

    def _name(self, node) -> str | None:
        if not node:
            return None
        if hasattr(node, "name"):
            n = node.name
            return n.value if hasattr(n, "value") else str(n)
        if hasattr(node, "identifier") and node.identifier:
            return node.identifier.value
        return None

    def _port_name(self, port_node) -> str | None:
        if hasattr(port_node, "declarator"):
            decl = port_node.declarator
            return self._name(decl)
        return self._name(port_node)

    def _edge_type(self, kind_value: int) -> str:
        if SequentialDriverCollector.accepts(kind_value):
            return "seq_driver"
        elif CombinationalDriverCollector.accepts(kind_value):
            return "comb_driver"
        else:
            return "driver"

    def _process_node(self, node):
        kind_value = node.kind.value

        if not DriverCollector.accepts(kind_value):
            return

        try:
            lhs = self._name(node.left)
            rhs = self._name(node.right)
        except Exception:
            return

        if not lhs or not rhs:
            return

        edge_type = self._edge_type(kind_value)

        driver_edge = ConnectionEdge(source=rhs, sink=lhs, edge_type=edge_type)
        self.drivers.setdefault(lhs, []).append(driver_edge)
        self.loads.setdefault(rhs, []).append(ConnectionEdge(source=lhs, sink=rhs, edge_type="load"))

    def _parse(self):
        def visitor(node: object) -> None:
            if node.kind.name == "ImplicitAnsiPort":
                n = self._port_name(node)
                if n:
                    self.nodes[n] = new_signal_node(f"{self.module_name}.{n}", 1, is_port=True)
            self._process_node(node)

        self.tree.root.visit(visitor)

    def parse(self) -> "PyslangAdapter":
        if not self.module:
            return self

        self._parse()

        for m in self.module.members:
            if m.kind.value == SyntaxKind.DataDeclaration.value:
                if hasattr(m, "declarators"):
                    for d in m.declarators:
                        n = self._name(d)
                        if n and n not in self.nodes:
                            self.nodes[n] = new_signal_node(f"{self.module_name}.{n}", 1, is_reg=True)
            elif m.kind.value == SyntaxKind.NetDeclaration.value:
                if hasattr(m, "declarators"):
                    for d in m.declarators:
                        n = self._name(d)
                        if n and n not in self.nodes:
                            self.nodes[n] = new_signal_node(f"{self.module_name}.{n}", 1)

        return self

    def get_drivers(self, s: str) -> list:
        return self.drivers.get(s, [])

    def get_loads(self, s: str) -> list:
        return self.loads.get(s, [])

    def trace_signal(self, signal: str) -> SignalChain:
        full = f"{self.module_name}.{signal}"

        if signal not in self.nodes:
            return new_signal_chain(full, confidence="uncertain", caveats=[f"Signal {signal} not found"])

        drivers = self.get_drivers(signal)
        loads = self.get_loads(signal)

        # 分类
        via_assign = [e.source for e in drivers if e.edge_type == "driver"]
        via_seq = [e.source for e in drivers if e.edge_type == "seq_driver"]
        via_comb = [e.source for e in drivers if e.edge_type == "comb_driver"]

        # BFS
        path, visited = [], {signal}
        queue = list(loads)
        while queue and len(path) < 20:
            item = queue.pop(0)
            if item.source in visited:
                continue
            visited.add(item.source)
            path.append(item.source)
            queue.extend(self.get_loads(item.source))

        return new_signal_chain(
            full,
            drivers=drivers,
            loads=loads,
            data_path=path,
            via_assign=via_assign,
            via_seq=via_seq,
            via_comb=via_comb,
            confidence="high" if drivers else "medium",
        )
