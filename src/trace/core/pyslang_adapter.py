#==============================================================================
# pyslang_adapter.py - pyslang 适配器
# 先完成基础版本，未来持续改进
#==============================================================================

from typing import List, Dict, Optional
from dataclasses import dataclass
from pyslang import SyntaxTree, SyntaxKind

@dataclass
class SignalDef:
    name: str
    full_name: str
    kind: str
    
class PyslangAdapter:
    """pyslang 适配器 - 使用 visitor 遍历 AST"""
    
    def __init__(self, tree: SyntaxTree):
        self.tree = tree
        self.module = self._get_module()
        self.signals: Dict[str, SignalDef] = {}
        self.drivers: Dict[str, List[str]] = {}
        self._results: List[tuple] = []
        
    def _get_module(self):
        if self.tree.root.members:
            return self.tree.root.members[0]
        return None
    
    def _get_name_str(self, node) -> Optional[str]:
        if not node:
            return None
        if hasattr(node, 'name'):
            name = node.name
            if hasattr(name, 'value'):
                return name.value
            return str(name)
        if hasattr(node, 'identifier'):
            ident = node.identifier
            if hasattr(ident, 'value'):
                return ident.value
        return None
    
    def _visitor(self, node):
        """pyslang visitor 回调"""
        kind = getattr(node, 'kind', None)
        
        # ContinuousAssign
        if kind == SyntaxKind.ContinuousAssign:
            for assign in node.assignments:
                lhs = self._get_name_str(assign.left)
                rhs = self._get_name_str(assign.right)
                if lhs and rhs:
                    self.drivers.setdefault(lhs, []).append(rhs)
        
        # NonblockingAssign
        elif kind == SyntaxKind.NonblockingAssignmentExpression:
            lhs = self._get_name_str(node.left)
            rhs = self._get_name_str(node.right)
            if lhs and rhs:
                self.drivers.setdefault(lhs, []).append(rhs)
    
    def parse(self) -> 'PyslangAdapter':
        if not self.module:
            return self
            
        module_name = self.module.header.name if self.module.header else "unknown"
        
        self._parse_ports(module_name)
        self._parse_data_declarations(module_name)
        
        # 使用 visitor 遍历
        self.tree.root.visit(self._visitor)
        
        return self
    
    def _parse_ports(self, module_name: str):
        header = self.module.header
        if not header or not header.ports:
            return
        for port in header.ports:
            name = self._get_name_str(port)
            if name:
                self.signals[name] = SignalDef(
                    name=name,
                    full_name=f"{module_name}.{name}",
                    kind="port"
                )
    
    def _parse_data_declarations(self, module_name: str):
        for member in self.module.members:
            kind = member.kind
            if kind not in [SyntaxKind.NetDeclaration, SyntaxKind.DataDeclaration]:
                continue
            if not hasattr(member, 'declarators'):
                continue
            for decl in member.declarators:
                name = self._get_name_str(decl)
                if name:
                    sig_kind = "wire" if kind == SyntaxKind.NetDeclaration else "reg"
                    self.signals[name] = SignalDef(
                        name=name,
                        full_name=f"{module_name}.{name}",
                        kind=sig_kind
                    )
    
    def get_drivers(self, signal: str) -> List[str]:
        return self.drivers.get(signal, [])
    
    def dump(self) -> dict:
        return {
            "signals": {k: v.kind for k, v in self.signals.items()},
            "drivers": self.drivers
        }
