#==============================================================================
# pyslang_adapter.py - pyslang 适配器
#==============================================================================

from pyslang import SyntaxTree, SyntaxKind
from typing import List, Dict, Optional

from data_models import (
    SignalDef, DriverInfo, LoadInfo, SignalChain,
    ContinuousAssignStmt, ProceduralAssignStmt,
)


def _extract_recursive(node, func, depth=0):
    if depth > 20 or not node:
        return
    func(node)
    for attr in ['statements', 'items', 'body', 'statement']:
        if hasattr(node, attr):
            child = getattr(node, attr)
            if child:
                if isinstance(child, list):
                    for x in child:
                        _extract_recursive(x, func, depth+1)
                else:
                    _extract_recursive(child, func, depth+1)


class PyslangAdapter:
    def __init__(self, tree: SyntaxTree):
        self.tree = tree
        self.module = self._get_module()
        self.module_name = "top"
        if self.module and self.module.header:
            self.module_name = self.module.header.name
            
        self.signals: Dict[str, SignalDef] = {}
        self.drivers: Dict[str, List[DriverInfo]] = {}
        self.loads: Dict[str, List[LoadInfo]] = {}
        
    def _get_module(self):
        return self.tree.root.members[0] if self.tree.root and self.tree.root.members else None
    
    def _name(self, node) -> Optional[str]:
        if not node: return None
        if hasattr(node, 'name'):
            n = node.name
            return n.value if hasattr(n, 'value') else str(n)
        if hasattr(node, 'identifier') and node.identifier:
            return node.identifier.value
        # 尝试 header.name
        if hasattr(node, 'header') and node.header:
            return node.header.name
        return None
    
    def _get_port_name(self, port) -> Optional[str]:
        """获取端口名称"""
        if hasattr(port, 'name'):
            n = port.name
            if hasattr(n, 'value'):
                return n.value
            return str(n)
        return None
    
    def _process_node(self, node):
        kind = node.kind
        
        if kind == SyntaxKind.ContinuousAssign:
            for a in node.assignments:
                lhs = self._name(a.left)
                rhs = self._name(a.right)
                if lhs and rhs:
                    stmt = ContinuousAssignStmt(lhs=lhs, rhs=rhs)
                    self.drivers.setdefault(lhs, []).append(DriverInfo(rhs, stmt))
                    self.loads.setdefault(rhs, []).append(LoadInfo(lhs, stmt))
        
        elif kind.value == 331:  # Nonblocking
            lhs = self._name(node.left)
            rhs = self._name(node.right)
            if lhs and rhs:
                stmt = ProceduralAssignStmt(lhs=lhs, rhs=rhs, blocking=False)
                self.drivers.setdefault(lhs, []).append(DriverInfo(rhs, stmt))
                self.loads.setdefault(rhs, []).append(LoadInfo(lhs, stmt))
        
        elif kind.value == 30:  # Blocking
            lhs = self._name(node.left)
            rhs = self._name(node.right)
            if lhs and rhs:
                stmt = ProceduralAssignStmt(lhs=lhs, rhs=rhs, blocking=True)
                self.drivers.setdefault(lhs, []).append(DriverInfo(rhs, stmt))
                self.loads.setdefault(rhs, []).append(LoadInfo(lhs, stmt))
    
    def parse(self) -> 'PyslangAdapter':
        if not self.module:
            return self
        
        # ports (正确遍���方式)
        h = self.module.header
        if h and hasattr(h, 'ports'):
            pl = h.ports
            if hasattr(pl, 'ports'):
                for p in pl.ports:
                    n = self._get_port_name(p)
                    if n:
                        # 检查方向
                        direction = "input"
                        if hasattr(p, 'direction'):
                            d = p.direction
                            if hasattr(d, 'name'):
                                direction = d.name.lower()
                            elif 'out' in str(d).lower():
                                direction = "output"
                        self.signals[n] = SignalDef(n, f"{self.module_name}.{n}", "port", direction)
        
        # 声明
        for m in self.module.members:
            if m.kind.value in [118, 323]:
                if hasattr(m, 'declarators'):
                    for d in m.declarators:
                        n = self._name(d)
                        if n:
                            k = "reg" if m.kind.value == 118 else "wire"
                            self.signals[n] = SignalDef(n, f"{self.module_name}.{n}", k)
        
        _extract_recursive(self.tree.root, self._process_node)
        
        return self
    
    def get_drivers(self, sig): return self.drivers.get(sig, [])
    def get_loads(self, sig): return self.loads.get(sig, [])
    
    def trace_signal(self, signal: str) -> SignalChain:
        full = f"{self.module_name}.{signal}"
        
        if signal not in self.signals:
            return SignalChain(full, signal, self.module_name, confidence="uncertain",
                            caveats=[f"Signal {signal} not found"])
        
        drivers = self.get_drivers(signal)
        loads = self.get_loads(signal)
        
        path, visited, queue = [], {signal}, list(loads)
        while queue and len(path) < 20:
            l = queue.pop(0)
            if l.signal in visited: continue
            visited.add(l.signal)
            path.append(l.signal)
            queue.extend(self.get_loads(l.signal))
        
        return SignalChain(full, signal, self.module_name, drivers, loads, path,
                         confidence="high" if drivers else "medium")

def trace_signal_from_file(f, sig):
    return PyslangAdapter(SyntaxTree.fromFile(f)).parse().trace_signal(sig)

def trace_signal_from_code(c, sig):
    return PyslangAdapter(SyntaxTree.fromText(c)).parse().trace_signal(sig)
