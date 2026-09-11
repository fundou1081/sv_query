# ports_ifaces.py — SemanticAdapter 的 ports_ifaces 域 mixin (iter_176 分域搬迁)
#
# 方法名/签名与原 SemanticAdapter 完全一致 (API 面冻结测试锁定);
# `self` 即 SemanticAdapter 实例 (状态: _root/_compiler/_target_module/
# _fixed_names/_genvar_context/_spec_members 等), 无独立状态。
"""ports_ifaces 域: 端口/接口/modport"""
import logging
from typing import Callable, Iterator

import pyslang

from ..._safe import _safe_attr, _safe_str, clean_name, safe_attr, safe_str
from ..ast_utils import is_syntax_list, iter_syntax_list

logger = logging.getLogger(__name__)


class PortsIfacesMixin:
    """ports_ifaces 域方法集 (mixin — 由 SemanticAdapter 组合)"""

    def get_interfaces(self) -> list:
        """获取所有接口定义 (Semantic AST)"""
        interfaces = []

        # Use _compiler.get_compilation().getDefinitions() to get all definitions
        if self._compiler:
            compilation = self._compiler.get_compilation()
            for defn in compilation.getDefinitions():
                kind_str = str(defn.kind)
                # Check if it's a Definition
                if "Definition" in kind_str and hasattr(defn, "syntax"):
                    # Check syntax.kind for InterfaceDeclaration
                    syntax_kind = str(getattr(defn.syntax, "kind", ""))
                    if "Interface" in syntax_kind:
                        interfaces.append(defn)

        return interfaces



    def get_modport_declarations(self, interface) -> list:
        """获取 interface 的 modport 声明 (Semantic AST)"""
        modports = []
        if not interface:
            return modports

        # Get modports from interface.syntax.members
        if hasattr(interface, "syntax"):
            syntax = interface.syntax
            if hasattr(syntax, "members") and syntax.members:
                for member in syntax.members:
                    member_kind = str(getattr(member, "kind", ""))
                    if "Modport" in member_kind:
                        modports.append(member)

        return modports



    def get_modport_info(self, modport) -> dict:
        """获取 modport 详细信息 (名称、方向、端口列表) (Semantic AST)"""
        info = {"name": "", "direction": "", "ports": []}

        if modport is None:
            return info

        try:
            # Get modport name from ModportItem list
            if hasattr(modport, "items") and modport.items:
                for item in modport.items:
                    item_name = _safe_attr(item, "name", None)
                    if item_name:
                        info["name"] = str(item_name).strip()

                    # Get port directions from item.ports (AnsiPortListSyntax)
                    if hasattr(item, "ports") and item.ports:
                        # ports is AnsiPortListSyntax containing:
                        #   v10: [Token(open paren), SeparatedList, Token(close paren)]
                        #        SeparatedList 内部是 ModportSimplePortList + Comma 交替
                        #   v11: [Token(open paren), ModportSimplePortList, Token(close paren)]
                        #        ports[1] 直接是 ModportSimplePortList
                        sep_list = item.ports[1] if len(item.ports) > 1 else None
                        if sep_list and hasattr(sep_list, "__iter__"):
                            # v10: 是 SeparatedList, 里面是 ModportSimplePortListSyntax
                            # v11: 本身是 ModportSimplePortListSyntax
                            for port_item in (iter_syntax_list(sep_list) if is_syntax_list(sep_list) else [sep_list]):
                                port_kind = getattr(port_item, "kind", None)
                                port_kind_str = str(port_kind) if port_kind else ""

                                if "ModportSimplePortList" in port_kind_str:
                                    # direction is on the ModportSimplePortList
                                    direction = getattr(port_item, "direction", None)
                                    if direction:
                                        info["direction"] = str(direction)

                                    # ports is AnsiPortListSyntax with ModportNamedPort items
                                    port_names = getattr(port_item, "ports", None)
                                    if port_names and hasattr(port_names, "__iter__"):
                                        # v10: ports_names 是 SeparatedList (ModportNamedPort + Comma)
                                        # v11: ports_names 直接是 ModportNamedPort
                                        for pn in (iter_syntax_list(port_names) if is_syntax_list(port_names) else [port_names]):
                                            pn_kind = getattr(pn, "kind", None)
                                            if pn_kind and "ModportNamedPort" in str(pn_kind):
                                                pn_name = _safe_attr(pn, "name", None)
                                                if pn_name:
                                                    info["ports"].append(str(pn_name).strip())
        except Exception as e:
            logger.warning("提取失败: %s", e)

        return info



    def get_port_declarations(self, module) -> list:
        """获取模块的端口声明

        Semantic AST: 从 DefinitionSymbol.body 遍历查找 PortSymbol
        """
        ports = []

        # DefinitionSymbol 有 body 属性,遍历其成员
        if hasattr(module, "body") and module.body:
            body = module.body
            for member in body:
                kind_str = str(getattr(member, "kind", ""))
                if "Port" in kind_str:
                    ports.append(member)

        return ports



    def get_port_names(self, module) -> list[str]:
        """获取模块的端口名称列表"""
        ports = self.get_port_declarations(module)
        names = []
        for port in ports:
            name = _safe_attr(port, "name", None)
            if name:
                names.append(str(name))
        return names



    def get_port_name(self, port_decl) -> str:
        """获取单个端口声明的名称"""
        name = _safe_attr(port_decl, "name", None)
        if name:
            # [Bug-fix 2026-06-13] safe_str() 防 binary garbage
            return _safe_str(name)
        return "unknown"



    def get_port_name_and_direction(self, port_decl) -> tuple:
        """获取端口名称和方向

        Returns:
            (name: str, direction: str) - direction: 'input', 'output', 'inout'
        """
        name = None
        direction = "input"  # 默认

        try:
            if hasattr(port_decl, "name"):
                # [Bug-fix 2026-06-13] safe_str() 防 binary garbage
                name = _safe_str(port_decl.name)
        except (UnicodeDecodeError, TypeError):
            name = None

        # 检查端口方向
        if hasattr(port_decl, "direction"):
            dir_val = port_decl.direction
            if hasattr(dir_val, "name"):
                # [Bug-fix 2026-06-13] safe_str() 防 binary garbage
                dir_str = _safe_str(dir_val.name).lower()
                # [FIX] Check inout BEFORE output, since 'inout' contains 'out'
                if "inout" in dir_str:
                    direction = "inout"
                elif "out" in dir_str:
                    direction = "output"
                else:
                    direction = "input"

        return (name, direction)



    def extract_port_width(self, port_decl, scope=None) -> tuple:
        """提取端口位宽

        Uses the semantic type.range (which has resolved left/right values)
        rather than declaredType.width (which only works for literal integers).

        Returns:
            (width: int, msb: int, lsb: int)
        """
        # Semantic AST: use port.type which has pre-resolved range from compiler
        port_type = getattr(port_decl, "type", None)
        if port_type:
            # PackedArrayType has range with left/right already evaluated
            if hasattr(port_type, "range") and port_type.range:
                r = port_type.range
                left = int(r.left) if hasattr(r.left, "value") else int(r.left)
                right = int(r.right) if hasattr(r.right, "value") else int(r.right)
                msb = max(left, right)
                lsb = min(left, right)
                return (msb, lsb)
            # ScalarType -> 1 bit
            elif hasattr(port_type, "kind") and "ScalarType" in str(port_type.kind):
                return (1, 0)

        # Fallback: try declaredType.width for literal values
        declared_type = getattr(port_decl, "declaredType", None)
        if declared_type:
            if hasattr(declared_type, "width"):
                w = declared_type.width
                if hasattr(w, "value") and w.value is not None:
                    try:
                        v = int(w.value)
                        return (v, 0, v - 1)
                    except (ValueError, TypeError) as _e:
                        logger.debug("提取失败 ((ValueError, TypeError)): %s", _e)
                        pass

        # 默认 1 位
        return (1, 0, 0)

    # =========================================================================
    # 赋值语句
    # =========================================================================



    def get_interface_modport_signals(self, interface_name: str, modport_name: str) -> dict[str, str]:
        """[P0-3] 获取 interface 中指定 modport 的所有信号及其方向

        Args:
            interface_name: 接口名称 (如 "bus_if")
            modport_name: modport 名称 (如 "master")

        Returns:
            Dict[signal_name, direction], 如 {"data": "output", "addr": "input"}
        """
        result = {}

        interfaces = self.get_interfaces()
        for iface in interfaces:
            # 获取 interface 名称
            # [FIX] Semantic AST: DefinitionSymbol has syntax.header, not direct header
            iface_def_name = None
            header = None
            members = None

            # Check if iface is a DefinitionSymbol (semantic adapter returns this)
            if hasattr(iface, "syntax"):
                # Access via syntax for DefinitionSymbol
                header = getattr(iface.syntax, "header", None)
                members = getattr(iface.syntax, "members", None)
            elif hasattr(iface, "header"):
                # Direct header/members for other cases
                header = iface.header
                members = iface.members

            if header and hasattr(header, "name"):
                # [Bug-fix 2026-06-13] header.name.value / str() 都可能返 binary garbage
                # 还要防 .value 访问本身 raise UnicodeDecodeError
                try:
                    if hasattr(header.name, "value"):
                        iface_def_name = _safe_str(header.name.value)
                    else:
                        iface_def_name = _safe_str(header.name)
                except (UnicodeDecodeError, TypeError):
                    iface_def_name = None

            if iface_def_name != interface_name:
                continue

            # 在 interface members 中找 ModportDeclaration
            if members:
                for member in members:
                    kind = str(getattr(member, "kind", ""))
                    if "ModportDeclaration" not in kind:
                        continue

                    # 处理 items (v10: SeparatedList SyntaxNode, v11: plain list,
                    # 或者是单个 ModportItem 节点)
                    items_node = getattr(member, "items", None)
                    if not items_node:
                        continue

                    if is_syntax_list(items_node):
                        # v10 SeparatedList / v11 plain list
                        items_list = iter_syntax_list(items_node)
                    else:
                        # 单个 ModportItem 节点
                        items_list = [items_node]

                    for item in items_list:
                        item_kind_str = str(getattr(item, "kind", ""))
                        if "ModportItem" not in item_kind_str:
                            continue

                        item_name = _safe_attr(item, "name", None)
                        if not item_name:
                            continue
                        # [Bug-fix 2026-06-13] 防御 binary garbage
                        if hasattr(item_name, "value"):
                            actual_name = _safe_str(item_name.value)
                        else:
                            actual_name = _safe_str(item_name)
                        if actual_name != modport_name:
                            continue

                        # 解析 ports (AnsiPortListSyntax)
                        if hasattr(item, "ports"):
                            ports = item.ports
                            if hasattr(ports, "ports"):
                                actual_ports = ports.ports
                                # actual_ports can be a SeparatedList of ModportSimplePortList
                                if hasattr(actual_ports, "__iter__") and not isinstance(actual_ports, str):
                                    if is_syntax_list(actual_ports):
                                        ports_list = iter_syntax_list(actual_ports)
                                    else:
                                        ports_list = [actual_ports]
                                else:
                                    ports_list = [actual_ports] if actual_ports else []

                                for p in ports_list:
                                    p_kind_str = str(getattr(p, "kind", ""))
                                    if "ModportSimplePortList" not in p_kind_str:
                                        continue

                                    direction = str(getattr(p, "direction", "")).lower().strip()
                                    ports_node = getattr(p, "ports", None)

                                    # Extract signal names from ports_node
                                    # ports_node can be SeparatedList of ModportNamedPort
                                    if (
                                        ports_node
                                        and hasattr(ports_node, "__iter__")
                                        and not isinstance(ports_node, str)
                                    ):
                                        if is_syntax_list(ports_node):
                                            sig_nodes = iter_syntax_list(ports_node)
                                        else:
                                            sig_nodes = [ports_node]
                                    else:
                                        sig_nodes = [ports_node] if ports_node else []

                                    for sig_node in sig_nodes:
                                        sig_kind_str = str(getattr(sig_node, "kind", ""))

                                        # Handle ModportNamedPort: has .name attribute
                                        if "ModportNamedPort" in sig_kind_str:
                                            sig_name_attr = _safe_attr(sig_node, "name", None)
                                            if sig_name_attr:
                                                # [Bug-fix 2026-06-13] .value / str() 都可能返 binary garbage
                                                # 还要防 .value 访问本身 raise UnicodeDecodeError
                                                try:
                                                    if hasattr(sig_name_attr, "value"):
                                                        sig_name = _safe_str(sig_name_attr.value)
                                                    else:
                                                        sig_name = _safe_str(sig_name_attr)
                                                except (UnicodeDecodeError, TypeError):
                                                    sig_name = None
                                                if sig_name:
                                                    result[sig_name] = direction
                                        # Handle simple identifier strings
                                        elif "Identifier" in sig_kind_str or sig_kind_str == "SyntaxKind.VariableDim":
                                            sig_name = _safe_attr(sig_node, "value", None) or str(sig_node)
                                            sig_name = sig_name.strip()
                                            if sig_name:
                                                result[sig_name] = direction

        return result



    def get_interface_members(self, interface_port_symbol) -> list[str]:
        """获取 interface 端口的成员信号列表

        Args:
            interface_port_symbol: InterfacePortSymbol (from body.lookupName('ifc'))

        Returns:
            List[str]: 成员信号名称列表，如 ['data', 'valid']
        """
        members = []

        try:
            # Get interface definition from InterfacePortSymbol
            iface_def = getattr(interface_port_symbol, "interfaceDef", None)
            if not iface_def:
                return members

            # Get members from syntax.members
            if hasattr(iface_def, "syntax"):
                syntax = iface_def.syntax
                if hasattr(syntax, "members"):
                    for m in syntax.members:
                        # DataDeclarationSyntax has declarators
                        if hasattr(m, "declarators"):
                            for decl in m.declarators:
                                if hasattr(decl, "name"):
                                    name = decl.name
                                    if hasattr(name, "value"):
                                        members.append(str(name.value).strip())
                                    else:
                                        members.append(str(name).strip())
        except Exception as e:
            logger.warning("提取失败: %s", e)

        return members
