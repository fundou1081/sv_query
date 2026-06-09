# ==============================================================================
# semantic_adapter.py - Semantic AST 适配器
#
# 将 Semantic AST (RootSymbol) 适配为 GraphBuilder 期望的接口
# 遵循铁律1: 必须使用 Semantic AST (Compilation + getRoot())
# ==============================================================================

import sys
from .._safe import _safe_attr, _safe_str
from typing import Callable, Iterator

# 确保 pyslang bindings 在 path 中
PYSLLANG_BINDINGS_PATH = "/Users/fundou/my_dv_proj/slang/build/bindings"
if PYSLLANG_BINDINGS_PATH not in sys.path:
    sys.path.insert(0, PYSLLANG_BINDINGS_PATH)

import pyslang
from trace.core._pyslang_compat import is_syntax_list, iter_syntax_list  # [Stage 6] v10/v11 兼容


class SemanticAdapter:
    """
    Semantic AST 适配器

    将 Semantic AST (RootSymbol) 适配为统一接口,供 GraphBuilder 使用。

    主要差异 (Semantic AST vs SyntaxTree):
    - RootSymbol 包含 InstanceSymbol 列表,而非 ModuleDeclaration 列表
    - InstanceSymbol.body 包含模块成员
    - 使用 root.visit(callback) 遍历
    - 节点是语义符号 (Symbol),不是语法节点 (SyntaxNode)
    """

    def __init__(self, root, compiler=None):
        """
        Args:
            root: Semantic AST root (RootSymbol from comp.getRoot())
            compiler: Optional SVCompiler for accessing getDefinitions()
        """
        self._root = root
        self._compiler = compiler
        self._fixed_names = {}  # id(cls) -> name (pyslang Unicode bug workaround)

    @property
    def root(self):
        """返回 Semantic AST root"""
        return self._root

    @property
    def parser(self):
        """兼容属性: 返回 self 用于模拟 parser.trees"""
        return self

    @property
    def trees(self):
        """兼容属性: 返回空字典 (Semantic AST 不需要 trees)"""
        return {}

    def items(self):
        """兼容方法: 返回空迭代器 (Semantic AST 不使用 SyntaxTree)"""
        return iter([])

    def get_source_location(self, node) -> tuple:
        """获取节点的源码位置

        [Stage 1] 从 semantic_node.syntax.sourceRange + SourceManager 拿真实位置
        之前返回空值 (注释说"需要从 SyntaxTree 获取"), 现已修复.

        Returns:
            tuple: (filename, line, column, offset)
            - filename: str, 源文件路径 (如 "test.sv")
            - line: int, 1-indexed 起始行
            - column: int, 0-indexed 起始列
            - offset: int, 结束 offset (备用)

        如果节点无 syntax 信息 (e.g., 虚拟节点), 返回空位置
        """
        if node is None:
            return ("", 0, 0, 0)
        # 拿 syntax 节点
        # 兼容两种情况: 1) node 是 semantic node (有 .syntax 属性)
        #               2) node 本身是 syntax node (直接有 .sourceRange)
        syn = getattr(node, "syntax", None)
        if syn is None:
            # 可能是 syntax node 直接 (如 IntegerVectorExpressionSyntax)
            syn = node if getattr(node, "sourceRange", None) is not None else None
        if syn is None:
            return ("", 0, 0, 0)
        sr = getattr(syn, "sourceRange", None)
        if sr is None:
            return ("", 0, 0, 0)

        # 拿 SourceManager
        # 兼容传 SVCompiler 或 Compilation 两种情况
        try:
            compiler_or_comp = self._compiler
            if hasattr(compiler_or_comp, "get_compilation"):
                sm = compiler_or_comp.get_compilation().sourceManager
            else:
                sm = compiler_or_comp.sourceManager
        except AttributeError:
            return ("", 0, 0, 0)

        # 拿文件路径
        try:
            filename = sm.getFileName(sr.start)
        except Exception:
            filename = ""

        # 拿 line/column
        try:
            line = sm.getLineNumber(sr.start)
            col = sm.getColumnNumber(sr.start)
        except Exception:
            line, col = 0, 0

        return (filename, line, col, sr.end.offset)

    def get_source_text(self, node) -> str:
        """[Stage 2] 获取节点所在文件的完整源码

        Args:
            node: semantic AST node (或 syntax node, 有 .sourceRange 即可)

        Returns:
            str: 文件完整源码, 失败返回空字符串

        使用 pyslang SourceManager.getSourceText (避免自己读文件)
        """
        if node is None:
            return ""
        syn = getattr(node, "syntax", None) or node
        sr = getattr(syn, "sourceRange", None)
        if sr is None:
            return ""
        try:
            sm = self._compiler.get_compilation().sourceManager
            buf = sr.start.buffer
            if buf is None:
                return ""
            return sm.getSourceText(buf)
        except Exception:
            return ""

    # =========================================================================
    # 模块和实例相关
    # =========================================================================

    def get_modules(self) -> list:
        """获取所有模块定义 (InstanceSymbol)

        Semantic AST 中,每个模块定义对应一个 InstanceSymbol。
        我们从 root 遍历获取所有 InstanceSymbol,包括嵌套的。
        """
        modules = []
        seen_ids = set()

        def collect_instances(node):
            if node is None:
                return

            try:
                kind = getattr(node, "kind", None)
                kind_str = str(kind) if kind else "None"
            except (UnicodeDecodeError, Exception):
                kind_str = "None"

            try:
                name = _safe_attr(node, "name", None)
            except (UnicodeDecodeError, Exception):
                name = None
            # 工作绕过: pyslang 某些情况下 name 会返回二进制乱码
            if isinstance(name, bytes):
                try:
                    name = name.decode("utf-8", errors="replace")
                except Exception:
                    name = "_bin_"
            try:
                name_str = self._safe_str(name) if name else "_anon_"
            except (UnicodeDecodeError, Exception):
                name_str = "_bad_"

            key = (kind_str, name_str)
            if key in seen_ids:
                return
            seen_ids.add(key)

            if kind_str == "SymbolKind.Instance":
                modules.append(node)
                # 递归收集嵌套实例
                body = getattr(node, "body", None)
                if isinstance(body, pyslang.InstanceBodySymbol):
                    for child in body:
                        collect_instances(child)

        # 遍历 root.topInstances 获取顶级模块实例
        for inst in self._root.topInstances:
            collect_instances(inst)

        # [FIX] 如果 topInstances 为空(例如只有参数化模块定义但没有实例化),
        # 从 compilationUnits 获取模块定义
        if not modules and self._compiler:
            comp = self._compiler.get_compilation()
            root = self._compiler.get_root()

            # 尝试从 DefinitionSymbol 获取模块定义
            for unit in self._root.compilationUnits:

                def collect_from_compilation(comp_node):
                    nonlocal modules
                    if comp_node is None:
                        return

                    kind = getattr(comp_node, "kind", None)
                    kind_str = str(kind) if kind else "None"
                    name = _safe_attr(comp_node, "name", None)
                    # 工作绕过: pyslang 某些情况下 name 会返回二进制乱码
                    if isinstance(name, bytes):
                        try:
                            name = name.decode("utf-8", errors="replace")
                        except Exception:
                            name = "_bin_"
                    name_str = self._safe_str(name) if name else "_anon_"

                    key = (kind_str, name_str)
                    if key in seen_ids:
                        return
                    seen_ids.add(key)

                    # DefinitionSymbol - 表示模块定义(用于参数化模块)
                    if kind_str == "SymbolKind.Definition":
                        # 尝试从 DefinitionSymbol 获取 InstanceSymbol
                        def_result = comp.tryGetDefinition(name_str, root)
                        if hasattr(def_result, "definition") and def_result.definition:
                            inst = def_result.definition
                            # Wrap DefinitionSymbol in a pseudo-InstanceSymbol-like wrapper
                            modules.append(inst)

                    # 递归遍历 children
                    if hasattr(comp_node, "children"):
                        for child in comp_node.children:
                            collect_from_compilation(child)

                if hasattr(unit, "members"):
                    for member in unit.members:
                        collect_from_compilation(member)

        return modules

    def get_module_instances(self) -> list:
        """获取所有模块实例 (SemanticInstanceWrapper)

        递归遍历所有模块的 body,找出嵌套的实例

        Args:
            trees: 兼容 SyntaxTree 接口,此参数被忽略

        Returns:
            SemanticInstanceWrapper 列表,包装 InstanceSymbol
        """
        wrappers = []
        # 使用 (kind, name) 作为唯一标识,而非 hash
        # pyslang 对象池会导致不同对象共享 hash,id() 也不稳定
        visited_names = set()

        def find_instances(node, parent_path=""):
            if node is None:
                return

            kind = getattr(node, "kind", None)
            kind_str = str(kind) if kind else "None"
            try:
                name = node.name
            except (UnicodeDecodeError, TypeError, Exception):
                name = None
            name_str = self._safe_str(name) if name else "_anon_"

            # path_str 用于 GenerateBlock/GenerateBlockArray 的递归传递
            # 初始化为 parent_path，确保在所有分支都有定义
            path_str = parent_path

            # 使用 (kind, name, hierarchical_path) 作为唯一标识
            # 对于数组实例元素 (如 u_duts[0]),name 相同但 hierarchical_path 不同
            try:
                hp = node.hierarchicalPath
            except (UnicodeDecodeError, TypeError, Exception):
                hp = None
            hp_str = self._safe_str(hp) if hp else ""
            key = (kind_str, name_str, hp_str)
            if key in visited_names:
                return
            visited_names.add(key)

            # 直接的 InstanceSymbol
            if kind_str == "SymbolKind.Instance":
                # 检查是否是 Definition (顶层模块定义) vs 嵌套实例
                # InstanceSymbol 同时用于顶层定义和嵌套实例
                # DefinitionSymbol 的 hierarchicalPath 是模块名本身 (如 "top", "unused")
                # 嵌套实例的 hierarchicalPath 包含父路径 (如 "top.sub")
                hierarchical_path = _safe_attr(node, "hierarchicalPath", None)
                path_str = str(hierarchical_path) if hierarchical_path else ""

                # 如果是顶层定义 (路径中不包含 '.') 且 parent_path 为空
                # 则认为是顶层模块定义,跳过不添加
                # 但仍然递归检查其 body 是否包含嵌套实例
                if not parent_path and "." not in path_str and path_str:
                    # 是顶层模块定义,递归检查其 body
                    body = getattr(node, "body", None)
                    if isinstance(body, pyslang.InstanceBodySymbol):
                        for child in body:
                            find_instances(child, path_str)
                    return

                parent_name = parent_path if parent_path else None
                wrappers.append(SemanticInstanceWrapper(node, parent_module=parent_name))
                # 递归检查 body 中的嵌套实例
                body = getattr(node, "body", None)
                if isinstance(body, pyslang.InstanceBodySymbol):
                    for child in body:
                        find_instances(child, f"{parent_path}.{name_str}" if parent_path else name_str)

            # GenerateBlockArray: 遍历 entries 找到其中的实例
            elif kind_str == "SymbolKind.GenerateBlockArray":
                entries = getattr(node, "entries", None)
                gen_name = name_str
                if entries:
                    for _idx, entry in enumerate(entries):
                        # entry 是 GenerateBlock,迭代它获取实例
                        for child in entry:
                            child_kind = str(getattr(child, "kind", ""))
                            if "Instance" in child_kind:
                                # 使用 hierarchicalPath 构建完整路径
                                hp = _safe_attr(child, "hierarchicalPath", None)
                                if hp:
                                    hp_str = str(hp)
                                    # hp_str 是完整路径如 'top.gen[0].u_dut'
                                    # 提取父路径: 去掉最后一个 '.' 及之后的实例名
                                    last_dot = hp_str.rfind(".")
                                    if last_dot > 0:
                                        child_path = hp_str[:last_dot]
                                    else:
                                        child_path = hp_str
                                else:
                                    # 后备: 使用旧逻辑
                                    child_path = f"{parent_path}.{gen_name}.{getattr(child, 'name', '_anon')}"
                                find_instances(child, child_path)

            # GenerateBlock: 直接迭代获取实例
            elif kind_str == "SymbolKind.GenerateBlock":
                for child in node:
                    find_instances(child, path_str)

            # InstanceArray: dut u_duts[0:3]; - 数组实例化
            elif kind_str == "SymbolKind.InstanceArray":
                elements = getattr(node, "elements", None)
                if elements:
                    for idx, elem in enumerate(elements):
                        elem_kind = str(getattr(elem, "kind", ""))
                        if "Instance" in elem_kind:
                            # 使用 arrayName 和 arrayPath 构建完整名称
                            arr_name = getattr(elem, "arrayName", None) or name_str
                            arr_path = getattr(elem, "arrayPath", None)
                            if arr_path and hasattr(arr_path, "__iter__") and not isinstance(arr_path, str):
                                idx_str = f"[{arr_path[0]}]"
                            else:
                                idx_str = f"[{idx}]"
                            full_name = f"{arr_name}{idx_str}"
                            child_path = f"{parent_path}.{full_name}" if parent_path else full_name
                            find_instances(elem, child_path)

        # 遍历 root 下的所有项
        for item in self._root:
            find_instances(item)

        return wrappers

    def get_module_name(self, module) -> str:
        """获取模块名称

        Semantic AST: 对于 InstanceSymbol,返回 definition.name;
                      对于 DefinitionSymbol,返回 name
        """
        try:
            kind_str = str(getattr(module, "kind", ""))
        except (UnicodeDecodeError, Exception):
            return "_unknown_"

        if "Instance" in kind_str:
            # InstanceSymbol: definition.name 是模块类型
            # 注意: pyslang 在某些 CVA6 类型上访问 .name 会触发 UnicodeDecodeError
            try:
                defn = getattr(module, "definition", None)
                if defn is not None:
                    # 不用 hasattr - 直接尝试 get
                    name = _safe_attr(defn, "name", None)
                    if name is not None:
                        return str(name)
            except (UnicodeDecodeError, Exception):
                return "_inst_"

        try:
            name = _safe_attr(module, "name", None)
            if name is not None:
                return str(name)
        except (UnicodeDecodeError, Exception):
            return "_bad_"
        return "unknown"

    def get_classes(self) -> list:
        """获取所有类定义（包括 package 内的 class）"""
        classes = []

        # 遍历所有 CompilationUnit [铁律1]
        for comp_unit in self._root:
            kind = str(getattr(comp_unit, "kind", ""))
            # Instance 需要用 body 遍历
            if "Instance" in kind:
                if hasattr(comp_unit, "body"):
                    for item in comp_unit.body:
                        kind_str = str(getattr(item, "kind", ""))
                        if "Class" in kind_str:
                            classes.append(item)
                continue
            if "CompilationUnit" not in kind:
                continue
            try:
                for item in comp_unit:
                    try:
                        kind_str = str(getattr(item, "kind", ""))
                    except UnicodeDecodeError:
                        continue
                    if "Class" in kind_str:
                        classes.append(item)
                    # 进入 Package 查找 class
                    elif "Package" in kind_str:
                        try:
                            for child in item:
                                try:
                                    ck = str(getattr(child, "kind", ""))
                                except UnicodeDecodeError:
                                    continue
                                if "Class" in ck:
                                    classes.append(child)
                        except (TypeError, UnicodeDecodeError):
                            pass
            except (TypeError, UnicodeDecodeError):
                pass

        # 去重（Semantic AST 和 SyntaxTree 可能都找到了同一个 class）
        seen = set()
        unique_classes = []
        for c in classes:
            try:
                name = str(_safe_attr(c, "name", "")).strip()
            except UnicodeDecodeError:
                unique_classes.append(c)
                continue
            if name not in seen:
                seen.add(name)
                unique_classes.append(c)
        classes = unique_classes

        # pyslang Unicode bug 兜底：用 sourceRange 从源码提取类名
        self._fix_unicode_class_names(classes)

        # 去重
        seen = set()
        unique_classes = []
        for c in classes:
            name = self.get_class_name(c)
            if name and name not in seen:
                seen.add(name)
                unique_classes.append(c)
            elif not name:
                unique_classes.append(c)

        return unique_classes

    def get_class_name(self, cls) -> str:
        """获取 class 名称（处理 Unicode bug）"""
        fixed = self._fixed_names.get(id(cls))
        if fixed:
            return fixed
        try:
            return str(_safe_attr(cls, "name", "")).strip()
        except UnicodeDecodeError:
            return ""

    def _fix_unicode_class_names(self, classes: list):
        """修复 pyslang Unicode bug 导致的类名损坏

        通过 syntax.sourceRange.offset 从 compiler._sources 提取类名。
        存储到 self._fixed_names 字典（pyslang 对象不允许设置属性）。
        """
        if not self._compiler:
            return

        sources = getattr(self._compiler, "_sources", {})
        if not sources:
            return

        import re

        for cls in classes:
            try:
                str(_safe_attr(cls, "name", ""))
                continue
            except UnicodeDecodeError:
                pass

            syntax = getattr(cls, "syntax", None)
            if not syntax:
                continue
            sr = getattr(syntax, "sourceRange", None)
            if not sr:
                continue
            start = getattr(sr, "start", None)
            if not start:
                continue
            offset = getattr(start, "offset", 0)

            for _fname, src in sources.items():
                if offset < len(src):
                    snippet = src[offset : offset + 100]
                    match = re.match(r"class\s+(\w+)", snippet)
                    if match:
                        self._fixed_names[id(cls)] = match.group(1)
                        break

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
        except Exception:
            pass

        return info

    def get_generate_instances(self) -> list:
        """获取 generate 实例 (Semantic AST 暂不支持 generate 语法)

        Args:
            trees: 兼容 SyntaxTree 接口,此参数被忽略

        Returns:
            空列表 (Semantic AST 不单独处理 generate)
        """
        return []

    def get_instance_connection(self, instance) -> list:
        """获取实例的端口连接

        Semantic AST: 从 InstanceSymbol.portConnections 获取
        Returns:
            [(port_name, signal_name), ...]
        """
        connections = []

        # 如果是包装器,从 _symbol 获取
        if hasattr(instance, "_symbol"):
            inst_sym = instance._symbol
        else:
            inst_sym = instance

        # Semantic AST: InstanceSymbol 有 portConnections 属性
        if hasattr(inst_sym, "portConnections"):
            for conn in inst_sym.portConnections:
                # port 属性有 name
                port_name = "?"
                if hasattr(conn, "port"):
                    try:
                        port_name = str(conn.port.name)
                    except (UnicodeDecodeError, TypeError, Exception):
                        port_name = "<id:non-utf8>"

                # expression 是 NamedValue,其 symbol 是信号
                # 也可能是 Assignment 表达式 (用于 output 端口连接，如 .q(signal))
                signal_name = "?"
                if hasattr(conn, "expression") and hasattr(conn.expression, "symbol"):
                    # NamedValue expression
                    try:
                        signal_name = str(conn.expression.symbol.name)
                    except (UnicodeDecodeError, TypeError, Exception):
                        signal_name = "<id:non-utf8>"
                elif hasattr(conn, "expression"):
                    expr = conn.expression
                    # Check if it's an Assignment expression (output port connection)
                    expr_kind = str(getattr(expr, "kind", ""))
                    if "Assignment" in expr_kind:
                        # For Assignment expression (.q(signal)), signal is in left side
                        left = getattr(expr, "left", None)
                        if left and hasattr(left, "symbol"):
                            try:
                                signal_name = str(left.symbol.name)
                            except (UnicodeDecodeError, TypeError, Exception):
                                signal_name = "<id:non-utf8>"

                if port_name != "?" and signal_name != "?":
                    connections.append((port_name, signal_name))

        return connections

    # =========================================================================
    # 端口相关
    # =========================================================================

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
            return str(name)
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
                name = str(port_decl.name)
        except (UnicodeDecodeError, Exception):
            name = None

        # 检查端口方向
        if hasattr(port_decl, "direction"):
            dir_val = port_decl.direction
            if hasattr(dir_val, "name"):
                dir_str = str(dir_val.name).lower()
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
                    except (ValueError, TypeError):
                        pass

        # 默认 1 位
        return (1, 0, 0)

    # =========================================================================
    # 赋值语句
    # =========================================================================

    def get_assignments(self, module) -> list:
        """获取模块的连续赋值语句

        Semantic AST: 遍历 always_ff/always_comb/连续赋值
        """
        assignments = []

        def find_assignments(node):
            if node is None:
                return
            kind = str(getattr(node, "kind", ""))

            # ContinuousAssign 语法
            if "ContinuousAssign" in kind:
                assignments.append(node)
                return  # 不递归到子节点
            # AssignmentExpression (procedural)
            elif "AssignmentExpression" in kind:
                assignments.append(node)
                return  # 不递归到子节点

            # [FIX Ghost-Signal] 递归只能进入"作用域"节点。
            # 之前的实现递归了 PortSymbol/NetSymbol 这些顶层成员, PortSymbol 的
            # __iter__ 会产生该 port 在子模块内部的相关节点 (包括其内部的
            # ContinuousAssign)。这会错误地将子模块的 assigns 加入到父模块。
            # 修正: 只递归 user code scope 节点 (always/generate), 不递归 Port/Net 等符号。
            #
            # 合法 scope 节点:
            #   - ProceduralBlock  (always_ff / always_comb / always 等)
            #   - GenerateBlock    (generate for / generate if 内的代码块)
            #   - GenerateBlockArray (generate for 展开的数组入口)
            if ("ProceduralBlock" in kind
                or "GenerateBlock" in kind):
                for child in self._iter_children(node):
                    find_assignments(child)

        if hasattr(module, "body") and module.body:
            for member in module.body:
                find_assignments(member)

        return assignments

    # =========================================================================
    # Always 块
    # =========================================================================

    def get_always_blocks(self, module) -> list:
        """获取模块的 always_ff/always_comb/always_latch 块

        Semantic AST: ProceduralBlockSymbol
        """
        always_blocks = []

        if hasattr(module, "body") and module.body:
            for member in module.body:
                kind = str(getattr(member, "kind", ""))
                if "ProceduralBlock" in kind:
                    always_blocks.append(member)

        return always_blocks

    # =========================================================================
    # Task 和 Function
    # =========================================================================

    def get_task_declarations(self, module) -> list:
        """获取模块的 task 声明"""
        tasks = []

        if hasattr(module, "body") and module.body:
            for member in module.body:
                kind = str(getattr(member, "kind", ""))
                # Semantic AST: SubroutineSymbol has kind=SymbolKind.Subroutine
                # Use subroutineKind to determine if it's a Task or Function
                if "Subroutine" in kind:
                    sk = getattr(member, "subroutineKind", None)
                    if sk and "Task" in str(sk):
                        tasks.append(member)
                elif "Task" in kind:
                    tasks.append(member)

        # Also check CU-level tasks (top-level tasks outside any module)
        if hasattr(module, "body"):
            cu_funcs = self.get_top_level_subroutines()
            for f in cu_funcs:
                sk = getattr(f, "subroutineKind", None)
                if sk and "Task" in str(sk):
                    tasks.append(f)

        return tasks

    def get_top_level_subroutines(self) -> list:
        """Get all function/task declarations at compilation unit level"""
        subroutines = []
        for cu in getattr(self._root, "compilationUnits", []):
            if hasattr(cu, "__iter__"):
                for item in cu:
                    kind = getattr(item, "kind", None)
                    kind_str = str(kind) if kind else ""
                    if "Subroutine" in kind_str:
                        subroutines.append(item)
        return subroutines

    def get_function_declarations(self, module) -> list:
        """获取模块的 function 声明"""
        funcs = []

        if hasattr(module, "body") and module.body:
            for member in module.body:
                kind = str(getattr(member, "kind", ""))
                # Semantic AST: SubroutineSymbol with subroutineKind=Function
                if "Subroutine" in kind:
                    sk = getattr(member, "subroutineKind", None)
                    if sk and "Function" in str(sk):
                        funcs.append(member)
                elif "Function" in kind:
                    funcs.append(member)

        # Also check CU-level functions (top-level functions outside any module)
        if hasattr(module, "body"):
            cu_funcs = self.get_top_level_subroutines()
            for f in cu_funcs:
                sk = getattr(f, "subroutineKind", None)
                if sk and "Function" in str(sk):
                    funcs.append(f)

        return funcs

    def get_task_name(self, task) -> str:
        """获取 task 名称"""
        return str(getattr(task, "name", "unknown"))

    def get_function_name(self, func) -> str:
        """获取 function 名称"""
        return str(getattr(func, "name", "unknown"))

    # =========================================================================
    # 参数相关
    # =========================================================================

    def get_module_parameters(self, module) -> list:
        """获取模块的参数声明"""
        params = []

        if hasattr(module, "body") and module.body:
            for member in module.body:
                kind = str(getattr(member, "kind", ""))
                if "Parameter" in kind:
                    # 返回 dict 格式以兼容现有代码
                    param_name = _safe_attr(member, "name", None)
                    param_value = _safe_attr(member, "value", None)
                    if param_name:
                        params.append({"name": str(param_name), "value": str(param_value) if param_value else ""})

        return params

    # =========================================================================
    # 信号和驱动相关
    # =========================================================================

    def get_drivers(self, signal_name: str) -> list:
        """获取信号的驱动源 (Semantic AST 暂不支持)"""
        return []

    def get_loads(self, signal_name: str) -> list:
        """获取信号的负载 (Semantic AST 暂不支持)"""
        return []

    def get_net_declarations(self, module) -> list:
        """获取模块的 net/wire 声明"""
        nets = []

        if hasattr(module, "body") and module.body:
            for member in module.body:
                kind = str(getattr(member, "kind", ""))
                if "Net" in kind:
                    nets.append(member)

        return nets

    def get_net_aliases(self, module) -> list:
        """获取模块的 NetAlias (alias 语句)"""
        aliases = []

        if hasattr(module, "body") and module.body:
            for member in module.body:
                kind = str(getattr(member, "kind", ""))
                if "NetAlias" in kind:
                    aliases.append(member)

        return aliases

    def get_variable_declarations(self, module) -> list:
        """获取模块的变量声明

        返回 DataDeclaration 语法节点（用于位宽提取），而不是 VariableSymbol 对象。
        遍历 module.body.definition.syntax.members 获取 DataDeclaration 节点。
        """
        decls = []

        if hasattr(module, "body") and module.body:
            definition = getattr(module.body, "definition", None)
            if definition and hasattr(definition, "syntax"):
                syntax = definition.syntax
                if hasattr(syntax, "members"):
                    for member in syntax.members:
                        kind = str(getattr(member, "kind", ""))
                        if "DataDeclaration" in kind:
                            decls.append(member)

        return decls

    def get_data_declarations(self, module) -> list:
        """获取模块的数据声明 (wire, reg, logic 等)"""
        decls = []

        if hasattr(module, "body") and module.body:
            for member in module.body:
                kind = str(getattr(member, "kind", ""))
                if "DataDeclaration" in kind or "Net" in kind or "Variable" in kind:
                    decls.append(member)

        return decls

    def get_signal_name(self, signal) -> str:
        """获取信号名称

        DataDeclaration: signal.declarators[0].name.value
        VariableSymbol: signal.name
        """
        # Handle DataDeclaration (syntax tree)
        if hasattr(signal, "declarators"):
            decls = signal.declarators
            if hasattr(decls, "__iter__") and not isinstance(decls, str):
                decl_list = list(decls)
                if decl_list:
                    first_decl = decl_list[0]
                    name = _safe_attr(first_decl, "name", None)
                    if name:
                        try:
                            return str(name)
                        except (UnicodeDecodeError, TypeError):
                            # 非 utf-8 identifier (e.g. escape 序列), 退回 location
                            loc = getattr(name, "location", None)
                            if loc is not None:
                                return f"<id@{getattr(loc, 'line', '?')}:{getattr(loc, 'column', '?')}>"
                            return "<id:non-utf8>"
            elif hasattr(decls, "name"):
                try:
                    return str(decls.name)
                except (UnicodeDecodeError, TypeError):
                    return "<id:non-utf8>"

        # Handle VariableSymbol (semantic AST)
        if hasattr(signal, "name"):
            try:
                return str(signal.name)
            except (UnicodeDecodeError, TypeError):
                return "<id:non-utf8>"
        return "unknown"

    def get_task_params(self, task) -> list:
        """获取 task 的参数列表

        Semantic AST: SubroutineSymbol.arguments is a list of FormalArgument symbols
        Each FormalArgument has name, direction, and declaredType
        """
        params = []

        if hasattr(task, "arguments"):
            for arg in task.arguments:
                param_info = {
                    "name": getattr(arg, "name", "unknown"),
                    "direction": str(getattr(arg, "direction", "None")),
                    "width": (0, 0),  # TODO: extract from declaredType
                }
                params.append(param_info)

        return params
    def _extract_signals_from_expr(self, expr) -> list[str]:
        """从表达式中提取所有信号名称"""
        signals = []
        if expr is None:
            return signals

        kind_str = str(getattr(expr, "kind", ""))

        # NamedValue: direct signal reference
        if "NamedValue" in kind_str:
            sym = getattr(expr, "symbol", None)
            if sym:
                sig_name = _safe_attr(sym, "name", None)
                if sig_name:
                    signals.append(sig_name)

        # Binary/Unary expressions: recurse into left/right operands
        elif "Binary" in kind_str:
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)
            if left:
                signals.extend(self._extract_signals_from_expr(left))
            if right:
                signals.extend(self._extract_signals_from_expr(right))

        elif "Unary" in kind_str:
            operand = getattr(expr, "operand", None)
            if operand:
                signals.extend(self._extract_signals_from_expr(operand))

        elif "Conversion" in kind_str:
            operand = getattr(expr, "operand", None)
            if operand:
                signals.extend(self._extract_signals_from_expr(operand))

        return signals

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
                iface_def_name = header.name.value if hasattr(header.name, "value") else str(header.name)

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
                        actual_name = item_name.value if hasattr(item_name, "value") else str(item_name)
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
                                                sig_name = (
                                                    sig_name_attr.value
                                                    if hasattr(sig_name_attr, "value")
                                                    else str(sig_name_attr)
                                                )
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
        except Exception:
            pass

        return members

    def get_function_params(self, func) -> list:
        """获取 function 的参数列表

        Semantic AST: FormalArgument symbols with direction and name
        Returns: List[Tuple[str, str]] - [(direction, name), ...]
        """
        params = []
        for arg in getattr(func, "arguments", []):
            direction = str(getattr(arg, "direction", "Input")).split(".")[-1].lower()
            name = getattr(arg, "name", "unknown")
            if name:
                params.append((direction, str(name)))
        return params

    def analyze_task_internal_drivers(self, task_or_func) -> dict:
        """分析 task/function 内部的驱动关系

        Handles:
        1. Functions: assignment to function name (implicit return)
        2. Tasks with output parameters: assignment to parameter name
        3. For loops, while loops, if-else inside tasks

        Returns:
            Dict: {var_name: [rhs_signal_names]}
        """
        drivers = {}
        func_name = _safe_attr(task_or_func, "name", None)
        if not func_name:
            return drivers
        func_name = str(func_name)

        body = getattr(task_or_func, "body", None)
        if not body:
            return drivers

        # Recursively collect assignment statements from the body
        self._collect_drivers_from_stmt(body, func_name, drivers)

        return drivers

    def _collect_drivers_from_stmt(self, stmt, func_name, drivers):
        """Recursively collect driver information from statements"""
        if stmt is None:
            return

        stmt_kind = str(getattr(stmt, "kind", ""))

        # ExpressionStatement: assignment like out = in + 1
        if "ExpressionStatement" in stmt_kind:
            expr = getattr(stmt, "expr", None)
            if expr and "Assignment" in str(getattr(expr, "kind", "")):
                self._extract_assignment_drivers(expr, func_name, drivers)
            return

        # BlockStatement: begin...end block containing multiple statements
        if "Block" in stmt_kind and "Statement" in stmt_kind:
            body = getattr(stmt, "body", None)
            if body:
                # Handle StatementList
                stmt_list = getattr(body, "list", None) or list(body) if hasattr(body, "__iter__") else [body]
                for s in stmt_list:
                    self._collect_drivers_from_stmt(s, func_name, drivers)
            return

        # ForLoopStatement: for (...) statement
        if "ForLoop" in stmt_kind:
            for_body = getattr(stmt, "body", None)
            if for_body:
                self._collect_drivers_from_stmt(for_body, func_name, drivers)
            return

        # WhileLoopStatement: while (...) statement
        if "WhileLoop" in stmt_kind:
            while_body = getattr(stmt, "body", None)
            if while_body:
                self._collect_drivers_from_stmt(while_body, func_name, drivers)
            return

        # ConditionalStatement: if (...) statement or if (...) ... else ...
        if "Conditional" in stmt_kind and "Statement" in stmt_kind:
            # Handle ifTrue (then branch)
            if_true = getattr(stmt, "ifTrue", None) or getattr(stmt, "statement", None)
            if if_true:
                self._collect_drivers_from_stmt(if_true, func_name, drivers)
            # Handle ifFalse (else branch)
            if_false = getattr(stmt, "ifFalse", None)
            if if_false:
                self._collect_drivers_from_stmt(if_false, func_name, drivers)
            return

        # SequentialBlock: begin...end in procedural context
        if "SequentialBlock" in stmt_kind:
            items = getattr(stmt, "items", None)
            if items:
                for s in items:
                    self._collect_drivers_from_stmt(s, func_name, drivers)
            return

        # ForkStatement: fork...join for parallel statements
        if "Fork" in stmt_kind:
            items = getattr(stmt, "items", None)
            if items:
                for s in items:
                    self._collect_drivers_from_stmt(s, func_name, drivers)
            return

        # StatementList: list of statements inside a block (from pyslang)
        if "List" in stmt_kind and "Statement" in stmt_kind:
            stmt_list = getattr(stmt, "list", None)
            if stmt_list:
                for s in stmt_list:
                    self._collect_drivers_from_stmt(s, func_name, drivers)
            return

        # ReturnStatement: return expr; (explicit return in function)
        if "Return" in stmt_kind:
            ret_expr = getattr(stmt, "expr", None)
            if ret_expr:
                rhs_signals = self._extract_signals_from_expr(ret_expr)
                if rhs_signals:
                    drivers[func_name] = rhs_signals
            return

    def _extract_assignment_drivers(self, expr, func_name, drivers):
        """Extract driver info from an AssignmentExpression"""
        lhs = getattr(expr, "left", None)
        rhs = getattr(expr, "right", None)

        if not lhs or not rhs:
            return

        # Get the left-hand side symbol and name
        # Handle both direct NamedValue and ElementSelect (signal[bit])
        lhs_symbol = getattr(lhs, "symbol", None)
        lhs_name = None

        if lhs_symbol:
            lhs_name = _safe_attr(lhs_symbol, "name", None)
        else:
            # Maybe it's an ElementSelect - check .value.symbol
            lhs_value = _safe_attr(lhs, "value", None)
            if lhs_value:
                lhs_symbol = getattr(lhs_value, "symbol", None)
                if lhs_symbol:
                    lhs_name = _safe_attr(lhs_symbol, "name", None)

        if not lhs_name:
            return

        # Extract RHS signal names
        rhs_signals = self._extract_signals_from_expr(rhs)

        # Only update if we have actual signal sources (not just literals)
        # This prevents overwriting real drivers with empty results from literals
        if rhs_signals:
            drivers[lhs_name] = rhs_signals

    def _extract_signals_from_expr(self, expr) -> list[str]:
        """从表达式中提取所有信号名

        Handles:
        - NamedValue: signal reference
        - ElementSelect: signal[bit] -> extract signal name
        - RangeSelect: signal[msb:lsb] -> extract signal name
        - Concatenation: {a, b, c}
        - BinaryExpression: a ^ b, a + b, etc.
        - UnaryExpression
        - IntegerLiteral: index value (not a signal)
        """
        signals = []
        if expr is None:
            return signals

        kind = getattr(expr, "kind", None)
        if not kind:
            return signals

        kind_str = str(kind)

        # NamedValue: signal reference
        if "NamedValue" in kind_str:
            sym = getattr(expr, "symbol", None)
            if sym:
                name = _safe_attr(sym, "name", None)
                if name:
                    signals.append(str(name))
            return signals

        # Concatenation: {a, b, c}
        if "Concatenation" in kind_str:
            for op in getattr(expr, "operands", []):
                signals.extend(self._extract_signals_from_expr(op))
            return signals

        # BinaryExpression: a ^ b, a + b, etc.
        if "Binary" in kind_str:
            signals.extend(self._extract_signals_from_expr(getattr(expr, "left", None)))
            signals.extend(self._extract_signals_from_expr(getattr(expr, "right", None)))
            return signals

        # UnaryExpression
        if "Unary" in kind_str:
            signals.extend(self._extract_signals_from_expr(getattr(expr, "operand", None)))
            return signals

        # ConversionExpression (type casting) - recurse into operand
        if "Conversion" in kind_str:
            signals.extend(self._extract_signals_from_expr(getattr(expr, "operand", None)))
            return signals

        # ElementSelect: signal[bit] - extract full name signal[bit]
        if "ElementSelect" in kind_str:
            # Get the base signal
            base_signals = self._extract_signals_from_expr(_safe_attr(expr, "value", None))
            # Get the selector (bit index)
            selector = getattr(expr, "selector", None)
            if selector and base_signals:
                # selector is an expression (IntegerLiteral or ParameterExpression)
                sel_kind = getattr(selector, "kind", None)
                if sel_kind:
                    sel_kind_str = str(sel_kind)
                    if "IntegerLiteral" in sel_kind_str:
                        # Get the integer value
                        sel_val = _safe_attr(selector, "value", None)
                        if sel_val is not None:
                            for base in base_signals:
                                signals.append(f"{base}[{sel_val}]")
                            return signals
                    elif "Parameter" in sel_kind_str:
                        # Parameter expression - try to get value
                        try:
                            sel_val = str(selector)  # Fallback to string representation
                        except Exception:
                            sel_val = _safe_attr(selector, "name", None) or str(selector)
                        for base in base_signals:
                            signals.append(f"{base}[{sel_val}]")
                        return signals
            # Fallback: just return base signal
            return base_signals

        # RangeSelect: signal[msb:lsb] - extract full name signal[msb:lsb]
        if "RangeSelect" in kind_str:
            # Get the base signal
            base_signals = self._extract_signals_from_expr(_safe_attr(expr, "value", None))
            # Get the range (left/right or selector with left/right)
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)
            if not left or not right:
                # Maybe stored as selector with left/right
                selector = getattr(expr, "selector", None)
                if selector:
                    left = getattr(selector, "left", None)
                    right = getattr(selector, "right", None)
            if left and right:
                left_val = _safe_attr(left, "value", None)
                right_val = _safe_attr(right, "value", None)
                for base in base_signals:
                    if left_val is not None and right_val is not None:
                        signals.append(f"{base}[{left_val}:{right_val}]")
                    else:
                        signals.append(f"{base}[?:?]")
                return signals
            # Fallback: just return base signal
            return base_signals

        # IntegerLiteral: not a signal
        if "IntegerLiteral" in kind_str:
            return signals

        return signals

    def extract_data_width(self, data_decl) -> tuple:
        """提取数据声明的位宽 (wire, reg, logic 等)

        支持两种方式:
        1. Semantic AST: 尝试从 declaredType 获取位宽
        2. Syntax Tree: 从 data_decl.type.dimensions[0].specifier.selector 获取位宽
        """
        # Semantic AST: 尝试从 declaredType 获取位宽
        declared_type = getattr(data_decl, "declaredType", None)
        if declared_type:
            if hasattr(declared_type, "width"):
                w = declared_type.width
                if hasattr(w, "value"):
                    return (int(w.value), 0)

        # Syntax Tree: 从 type.dimensions 获取位宽
        # 数据声明结构: data_decl.type.dimensions[0].specifier.selector.left/right
        if hasattr(data_decl, "type") and data_decl.type:
            dt = data_decl.type
            if hasattr(dt, "dimensions") and dt.dimensions:
                dims = dt.dimensions
                # Handle both iterable and single dimension
                if hasattr(dims, "__iter__") and not isinstance(dims, str):
                    dims_list = list(dims)
                else:
                    dims_list = [dims]

                for dim in dims_list:
                    if hasattr(dim, "kind") and str(dim.kind) == "SyntaxKind.VariableDimension":
                        if hasattr(dim, "specifier") and dim.specifier:
                            spec = dim.specifier
                            if hasattr(spec, "selector"):
                                sel = spec.selector
                                left = getattr(sel, "left", None)
                                right = getattr(sel, "right", None)

                                # 从 LiteralExpressionSyntax.literal.valueText 获取整数值
                                def get_int(node):
                                    if node is None:
                                        return 0
                                    if hasattr(node, "literal") and node.literal:
                                        try:
                                            return int(node.literal.valueText)
                                        except Exception:
                                            pass
                                    try:
                                        return int(str(node))
                                    except Exception:
                                        return 0

                                msb = get_int(left)
                                lsb = get_int(right)
                                return (msb, lsb)

        # 默认 1 位
        return (1, 0)

    # =========================================================================
    # 遍历
    # =========================================================================

    def visit(self, callback: Callable):
        """遍历 Semantic AST 所有节点"""
        self._root.visit(callback)

    def visit_module(self, module, callback: Callable):
        """遍历模块的所有节点"""
        if hasattr(module, "body") and module.body:
            module.body.visit(callback)

    def _iter_children(self, node) -> list:
        """安全遍历子节点"""
        if node is None:
            return []

        children = []

        # 处理可迭代对象
        if hasattr(node, "__iter__") and not isinstance(node, (str, bytes)):
            try:
                for child in node:
                    children.append(child)
            except Exception:
                pass

        # 处理常见属性
        for attr in [
            "members",
            "body",
            "statement",
            "statements",
            "left",
            "right",
            "expr",
            "condition",
            "consequent",
            "alternate",
        ]:
            child = getattr(node, attr, None)
            if child:
                if isinstance(child, list):
                    children.extend(child)
                elif hasattr(child, "kind"):
                    children.append(child)

        return children

    # =========================================================================
    # 工具方法
    # =========================================================================

    def clean_name(self, name) -> str:
        """清理信号名称 (移除多余空白等)

        容忍非 utf-8 字节的 identifier (e.g. escape 序列)。
        如果转换失败,返回 hex 形式以保证唯一性。
        """
        if not name:
            return ""
        try:
            s = str(name)
        except (UnicodeDecodeError, TypeError):
            # Token 内部 buffer 是非 utf-8 字节, 用 hex 表达
            try:
                raw = bytes(name) if hasattr(name, '__bytes__') else b''
                return f"<id:0x{raw.hex()[:16]}>"
            except Exception:
                return "<id:non-utf8>"
        return " ".join(s.split()).strip()

    @staticmethod
    def _safe_str(obj) -> str:
        """安全的 str() 调用,容忍非 utf-8 字节 (e.g. escape 序列)"""
        if obj is None:
            return ""
        try:
            return str(obj)
        except (UnicodeDecodeError, TypeError):
            try:
                if hasattr(obj, 'rawText'):
                    raw = bytes(obj.rawText) if hasattr(obj.rawText, '__bytes__') else b''
                elif hasattr(obj, '__bytes__'):
                    raw = bytes(obj)
                else:
                    raw = b''
                return f"<id:0x{raw.hex()[:16]}>"
            except Exception:
                return "<id:non-utf8>"

    def iter_modules(self) -> Iterator:
        """迭代模块 (InstanceSymbol)"""
        for item in self._root:
            if hasattr(item, "kind"):
                kind_str = str(item.kind)
                if "Instance" in kind_str:
                    yield item

    def get_definition(self, name: str):
        """获取模块/类定义"""
        for item in self._root:
            if hasattr(item, "name") and item.name == name:
                return item
        return None


# =============================================================================
# Semantic AST 实例包装器 - 兼容 GraphBuilder 的实例期望
# =============================================================================


class SemanticInstanceWrapper:
    """
    Semantic AST 实例包装器

    将 Semantic AST InstanceSymbol 适配为 GraphBuilder 期望的接口格式。
    这样可以在不修改 GraphBuilder 的情况下使用 Semantic AST。
    """

    def __init__(self, instance_symbol, parent_module=None):
        self._symbol = instance_symbol
        # [FIX] 对于数组实例元素 (如 u_duts[0]), name='' 但有 arrayName
        # 使用 arrayName + arrayPath 构建完整实例名
        try:
            inst_name = instance_symbol.name
        except (UnicodeDecodeError, TypeError, Exception):
            inst_name = None
        if not inst_name:
            try:
                array_name = instance_symbol.arrayName
            except (UnicodeDecodeError, TypeError, Exception):
                array_name = None
            if array_name:
                try:
                    arr_path = instance_symbol.arrayPath
                except (UnicodeDecodeError, TypeError, Exception):
                    arr_path = None
                if arr_path and hasattr(arr_path, "__iter__") and not isinstance(arr_path, str):
                    inst_name = f"{array_name}[{arr_path[0]}]"
                else:
                    inst_name = array_name
        self.name = inst_name
        self.type = type("TypeToken", (), {"value": self._get_module_type()})()
        self.parent_module = parent_module  # 父模块名

        # 构造 .instances[0].decl.name 结构供 GraphBuilder 使用
        self.instances = [SemanticInstanceDeclWrapper(instance_symbol)]

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return f"SemanticInstanceWrapper({self.name})"

    def _get_module_type(self) -> str:
        """获取模块类型名"""
        if hasattr(self._symbol, "definition"):
            defn = self._symbol.definition
            try:
                name_str = str(defn.name)
            except (UnicodeDecodeError, TypeError, Exception):
                name_str = None
            if name_str:
                return name_str
        try:
            return str(self.name)
        except (UnicodeDecodeError, TypeError):
            return "<id:non-utf8>"

    def get_parent_module(self) -> str:
        """获取父模块名,供 GraphBuilder._get_parent_module_name 使用"""
        return self.parent_module or "top"

    def _get_parent_module_safe(self) -> str:
        """安全获取父模块名,用于 GraphBuilder 的 _get_parent_module_name 兼容

        这个方法模拟 GraphBuilder._get_parent_module_name 的行为,
        但在 parent 为 None 时返回 type.value(模块类型名)而非 'unknown'。
        """
        if self.parent_module:
            return self.parent_module
        # 对于顶级模块,parent 为 None,此时返回 type.value(即模块类型名)
        # 这样 inst_module_name 就能正确设为 'top'
        return self.type.value if self.type.value else str(self.name)

    @property
    def parent(self):
        """兼容属性:返回类似 SyntaxTree 的 parent 节点结构

        对于顶级模块(parent_module is None),返回 None
        这样 _get_parent_module_name 会使用 fallback 逻辑。
        """
        if self.parent_module:

            class ParentModule:
                def __init__(self, name):
                    self.name = name
                    self.header = type("Header", (), {"name": type("Name", (), {"rawText": name})()})()

            return ParentModule(self.parent_module)
        return None


class SemanticInstanceDeclWrapper:
    """包装 InstanceSymbol 的 declaration 部分"""

    def __init__(self, instance_symbol):
        self._symbol = instance_symbol

    @property
    def name(self):
        """返回实例名称作为 TokenValue"""

        class TokenValue:
            def __init__(self, val):
                self.value = val

        return TokenValue(self._symbol.name)
