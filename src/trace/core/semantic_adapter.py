# ruff: noqa: E402
# ==============================================================================
# semantic_adapter.py - Semantic AST 适配器
#
# 将 Semantic AST (RootSymbol) 适配为 GraphBuilder 期望的接口
# 遵循铁律1: 必须使用 Semantic AST (Compilation + getRoot())
# ==============================================================================

import logging
import sys
from typing import Callable, Iterator

logger = logging.getLogger(__name__)

from .._safe import _safe_attr, _safe_str, safe_attr, safe_str
from .._safe import clean_name as _clean_name_fn

# 确保 pyslang bindings 在 path 中
PYSLLANG_BINDINGS_PATH = "/Users/fundou/my_dv_proj/slang/build/bindings"
if PYSLLANG_BINDINGS_PATH not in sys.path:
    sys.path.insert(0, PYSLLANG_BINDINGS_PATH)

import pyslang

from trace.core.ast_utils import is_syntax_list, iter_syntax_list


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

    def __init__(self, root, compiler=None, target_module=None):
        """
        Args:
            root: Semantic AST root (RootSymbol from comp.getRoot())
            compiler: Optional SVCompiler for accessing getDefinitions()
            target_module: [NEW 2026-07-11 Phase 2] 如果指定, get_module_instances()
                           只返该 user-specified module 的 hierarchy 子树.
                           None (默认) = 返所有 (兼容旧行为).
        """
        self._root = root
        self._compiler = compiler
        self._target_module = target_module  # [NEW 2026-07-11]
        self._fixed_names = {}  # id(cls) -> name (pyslang Unicode bug workaround)
        # [Plan F1 2026-08-12] genvar context: assign id → {genvar_name: int}
        # pyslang symbol 不允许 setattr, 不能直接挂 .genvar_ctx
        self._genvar_context = {}  # id(assign) → dict
        # [iter_112] id(primitive) → genvar ctx (generate-for 内的门, 同 assign 模式)
        self._primitive_genvar_context = {}

    @property
    def root(self) -> object:
        """返回 Semantic AST root"""
        return self._root

    @property
    def parser(self) -> object:
        """兼容属性: 返回 self 用于模拟 parser.trees"""
        return self

    @property
    def trees(self) -> dict:
        """兼容属性: 返回空字典 (Semantic AST 不需要 trees)"""
        return {}

    def items(self) -> object:
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
        """[iter_101] 获取节点 sourceRange 对应的源码片段 (非整份文件)

        Args:
            node: semantic AST node (或 syntax node, 有 .sourceRange 即可)

        Returns:
            str: 节点源码片段 (start.offset → end.offset 切片), 失败返回空字符串

        [缺陷 A 修复 2026-09-02] 原实现 `sm.getSourceText(buf)` 返回整个 buffer
        的完整源码 (含末尾 \x00), 导致所有 assign/always 边的 expression 字段
        变成整份文件+空字节 (下游 handshake/dataflow/viz 消费受影响)。
        修复: 按 sr.start.offset / sr.end.offset 切片取节点源码片段。
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
            text = sm.getSourceText(buf)
            start = sr.start.offset
            end = sr.end.offset
            # [iter_101] pyslang offset 是 UTF-8 **字节**偏移 (非字符) —
            # 源含非 ASCII (如注释里的 —) 时字符切片会错位, 必须按字节切片再解码.
            raw = text.encode("utf-8")
            return raw[start:end].decode("utf-8", errors="replace")
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
        # [PR1 2026-06-14] 用 id(node) 替代 name_str 做 dedup key.
        # name_str 依赖 pybind11 decode, 随机成功/失败 → 不稳定.
        seen_ids = set()

        def collect_instances(node: object) -> None:
            if node is None:
                return

            try:
                kind = getattr(node, "kind", None)
                kind_str = str(kind) if kind else "None"
            except (UnicodeDecodeError, TypeError):
                kind_str = "None"

            # 仍然需要 name 用于显示/列表 (有 name 更好, 没 name 用 placeholder)
            try:
                name = _safe_attr(node, "name", None)
            except (UnicodeDecodeError, TypeError):
                name = None
            if isinstance(name, bytes):
                try:
                    name = name.decode("utf-8", errors="replace")
                except Exception:
                    name = "_bin_"
            try:
                name_str = self._safe_str(name) if name else "_anon_"
            except (UnicodeDecodeError, TypeError):
                name_str = "_bad_"

            # [PR1 2026-06-14] 混合去重: 干净 name 用 name_str 去重 (避免重复),
            # binary name 用 id(node) 去重 (避免 name decode 随机性).
            _bin_patterns = ('', '<id:binary>', '_anon_', '_bad_', '_bin_')
            if name_str in _bin_patterns:
                key = (kind_str, 'BIN', id(node))
            else:
                key = (kind_str, name_str)
            if key in seen_ids:
                return
            seen_ids.add(key)

            if kind_str == "SymbolKind.Instance":
                # [PR1 2026-06-14] Filter binary garbage modules
                # elaboration 失败的 module 有 kind=Instance 但无实质内容.
                # 检测: name 是 binary, 且无 definition → 跳过
                _name_is_binary = name_str in ('', '<id:binary>', '_anon_', '_bad_', '_bin_')
                if _name_is_binary:
                    # 有 def 的可能是真实 module (如 AXI_BUS stubs)
                    _defn = _safe_attr(node, "definition", None)
                    if _defn is None:
                        return  # 纯 binary garbage
                modules.append(node)
                # 递归收集嵌套实例
                body = getattr(node, "body", None)
                if isinstance(body, pyslang.InstanceBodySymbol):
                    for child in body:
                        collect_instances(child)
                return

            # [iter_109 #45] 非 Instance 节点也要下钻: generate 块 (GenerateBlockArray
            # / GenerateBlock) 内含子模块实例 — 之前不递归 → generate-only 实例化的
            # 模块定义收集不到 (rot 端口定义缺失 → 连接边全灭, verilog_cordic_core 暴露).
            # 遍历方式镜像 native_adapter._walk_generate_block_array/_walk_generate_block:
            # GenerateBlockArray 经 __iter__ 拿 GenerateBlock; GenerateBlock 经 __iter__
            # 拿 Instance/嵌套 Generate.
            if kind_str == "SymbolKind.GenerateBlockArray":
                try:
                    entries = getattr(node, "entries", None)
                    if entries is None:
                        entries = list(node)
                except (UnicodeDecodeError, TypeError):
                    return
                for _gb in list(entries):
                    collect_instances(_gb)
                return
            if kind_str == "SymbolKind.GenerateBlock":
                try:
                    children = list(node)
                except (UnicodeDecodeError, TypeError):
                    children = self._iter_children(node)
                for _child in children:
                    collect_instances(_child)
                return

        # 遍历 root.topInstances 获取顶级模块实例
        for inst in self._root.topInstances:
            collect_instances(inst)

        # [FIX] 如果 topInstances 为空(例如只有参数化模块定义但没有实例化),
        # 从 compilationUnits 获取模块定义
        if not modules and self._compiler:
            comp = self._compiler.get_compilation() if hasattr(self._compiler, 'get_compilation') else self._compiler
            root = self._compiler.get_root() if hasattr(self._compiler, 'get_root') else self._root

            # 尝试从 DefinitionSymbol 获取模块定义
            for unit in self._root.compilationUnits:

                    def collect_from_compilation(comp_node: object) -> None:
                        nonlocal modules
                        if comp_node is None:
                            return

                        kind = getattr(comp_node, "kind", None)
                        kind_str = str(kind) if kind else "None"

                        # 工作绕过: pyslang 某些情况下 name 会返回二进制乱码
                        name = _safe_attr(comp_node, "name", None)
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

        [G3 阶段 2 2026-08-29] 实例枚举切 native:
        内部调用 native_adapter.get_module_instances_native (topInstances/body 原生
        遍历, 含 GenerateBlockArray/GenerateBlock/InstanceArray), 再用
        SemanticInstanceWrapper 包装 — **返回类型零变化**, 5 个生产调用方
        (MIG / unified_tracer / graph_builder / connection_extractor) 无需改动。

        旧递归实现保留为 get_module_instances_recursive(), 供 verify_native_parity.py
        做 A/B 等价性验证参照 (GAP-1~5 已修/已接受, iter_053~056)。

        Returns:
            SemanticInstanceWrapper 列表,包装 InstanceSymbol
        """
        from .native_adapter import get_module_instances_native

        native = get_module_instances_native(self._root, self._target_module)
        return [
            SemanticInstanceWrapper(w._symbol, parent_module=w.parent_module)
            for w in native
        ]

    def get_module_instances_recursive(self) -> list:
        """[G3 阶段 2 2026-08-29] 旧递归实例枚举 (验证参照, 非生产路径).

        生产 get_module_instances() 已切 native; 本方法保留原递归 walk,
        供 tools/verify_native_parity.py 与 unit 测试做 A/B 等价性对比
        (native 必须与递归一致, 除已接受的 GAP-3/4 差异)。

        Returns:
            SemanticInstanceWrapper 列表,包装 InstanceSymbol
        """
        wrappers = []
        visited_names = set()

        def find_instances(node: object, parent_path: str = "") -> None:
            if node is None:
                return

            kind = getattr(node, "kind", None)
            kind_str = str(kind) if kind else "None"
            try:
                name = node.name
            except (UnicodeDecodeError, TypeError):
                name = None
            name_str = self._safe_str(name) if name else "_anon_"

            path_str = parent_path

            try:
                hp = node.hierarchicalPath
            except (UnicodeDecodeError, TypeError):
                hp = None
            hp_str = self._safe_str(hp) if hp else ""
            key = (kind_str, name_str, hp_str)
            if key in visited_names:
                return
            visited_names.add(key)

            # 直接的 InstanceSymbol
            if kind_str == "SymbolKind.Instance":
                hierarchical_path = _safe_attr(node, "hierarchicalPath", None)
                path_str = _safe_str(hierarchical_path) if hierarchical_path else ""

                if not parent_path and "." not in path_str and path_str:
                    body = getattr(node, "body", None)
                    if isinstance(body, pyslang.InstanceBodySymbol):
                        for child in body:
                            find_instances(child, path_str)
                    return

                parent_name = parent_path if parent_path else None
                wrappers.append(SemanticInstanceWrapper(node, parent_module=parent_name))
                body = getattr(node, "body", None)
                if isinstance(body, pyslang.InstanceBodySymbol):
                    for child in body:
                        # [PR1 2026-06-14] parent_path 可能含 binary garbage, 用 safe
                        _p = _safe_str(parent_path) if parent_path else ""
                        find_instances(child, f"{_p}.{name_str}" if _p else name_str)

            # GenerateBlockArray: 遍历 entries 找到其中的实例
            elif kind_str == "SymbolKind.GenerateBlockArray":
                entries = getattr(node, "entries", None)
                gen_name = _safe_str(name_str)
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
                                    _pp = _safe_str(parent_path) if parent_path else ""
                                    _gn = _safe_str(gen_name) if gen_name else ""
                                    _cn = _safe_str(_safe_attr(child, 'name', '_anon'))
                                    child_path = f"{_pp}.{_gn}.{_cn}"
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
                            arr_name = _safe_str(_safe_attr(elem, "arrayName", None)) or name_str
                            arr_path = _safe_attr(elem, "arrayPath", None)
                            if arr_path and hasattr(arr_path, "__iter__") and not isinstance(arr_path, str):
                                idx_str = f"[{arr_path[0]}]"
                            else:
                                idx_str = f"[{idx}]"
                            full_name = f"{arr_name}{idx_str}"
                            child_path = f"{parent_path}.{full_name}" if parent_path else full_name
                            find_instances(elem, child_path)

        # 遍历 root 下的所有项
        # [Phase 2 2026-07-11] 如果指定 target_module, 只 walk 那个 target 的子树
        # 这样 pyslang 的 hierarchicalPath 会自动以 user target 为前缀
        if self._target_module:
            target_top = self._find_target_top(self._target_module)
            if target_top is not None:
                find_instances(target_top)
            else:
                # Fall back to walking all (target not found in topInstances)
                for item in self._root:
                    find_instances(item)
        else:
            # 兼容旧行为: walk 所有 top instances
            for item in self._root:
                find_instances(item)

        return wrappers

    def _find_target_top(self, target_module: str):
        """[NEW Phase 2 2026-07-11] 在 topInstances 中找 user-specified target.

        Returns:
            pyslang InstanceSymbol if found, else None.

        Used by get_module_instances() to filter hierarchy before walking,
        so pyslang auto-prefixes hierarchicalPath with user target.
        """
        if not self._root or not hasattr(self._root, 'topInstances'):
            return None
        for top in self._root.topInstances:
            try:
                if str(top.name) == target_module:
                    return top
            except (UnicodeDecodeError, TypeError):
                continue
        return None

    def get_module_name(self, module) -> str:
        """获取模块名称

        Semantic AST: 对于 InstanceSymbol,返回 definition.name;
                      对于 DefinitionSymbol,返回 name

        [Bug-fix 2026-06-13] 防御 binary garbage: 用 safe_str() 代替 str()
        """
        try:
            kind_str = str(getattr(module, "kind", ""))
        except (UnicodeDecodeError, TypeError):
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
                        return _safe_str(name)
            except (UnicodeDecodeError, TypeError):
                return "_inst_"

        try:
            name = _safe_attr(module, "name", None)
            if name is not None:
                return _safe_str(name)
        except (UnicodeDecodeError, TypeError):
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
                        except (TypeError, UnicodeDecodeError) as _e:
                            logger.debug("提取失败 ((TypeError, UnicodeDecodeError)): %s", _e)
                            pass
            except (TypeError, UnicodeDecodeError) as _e:
                logger.debug("提取失败 ((TypeError, UnicodeDecodeError)): %s", _e)
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
            except UnicodeDecodeError as _e:
                logger.debug("提取失败 (UnicodeDecodeError): %s", _e)
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
        except Exception as e:
            logger.warning("提取失败: %s", e)

        return info

    def get_generate_instances(self) -> list:
        """获取 generate 块内的所有 symbol (Instance + Net) — 纯 semantic API 路径.

        [E1 2026-08-27] 之前 D2 决策下 stub 返 [] 是不对的. 实际 v11 GenerateBlockArraySymbol
        通过 .entries (semantic API) 直接迭代, 每个 entry 是 GenerateBlockSymbol (semantic scope),
        在其上调用 lookupName() / __iter__ (纯 semantic) 能拿到所有 per-iter 的 InstanceSymbol +
        NetSymbol. 不需要 .syntax.members (raw AST) fallback.

        Plan F1 (2026-08-12) get_assignments 已用相同模式. 本方法复用 _iter_children (semantic),
        配合 .entries / .loopVariable / .arrayIndex / .hierarchicalPath (semantic API).

        Returns:
            SemanticInstanceWrapper 列表 — 每个 wrapper.name 是 hierarchicalPath, 如
            'generate_loop.gen_accum[1].prod' 或 'generate_loop.gen_accum[1].u_dut'
        """
        wrappers = []
        visited_paths = set()

        def _safe_iter_body(entry) -> list:
            """pure semantic: 从 GenerateBlockSymbol 拿 children. 不用 .syntax.members."""
            return self._iter_children(entry)

        def collect_in_module(module) -> None:
            if not hasattr(module, "body") or not module.body:
                return
            for member in module.body:
                kind = str(getattr(member, "kind", ""))
                # GenerateBlockArray (generate for 展开入口) — 纯 semantic
                if "GenerateBlockArray" in kind:
                    # [iter_037] 尝试纯 semantic iter (node 直接 __iter__),
                    # fallback 到 .entries (也 semantic, 但更显式)
                    try:
                        entries = list(member)  # GenerateBlockArraySymbol 直接可 iter
                    except TypeError:
                        entries = getattr(member, "entries", None) or []
                    for entry in entries:
                        # Skip uninstantiated (generate if false branch / 未实例化的 loop iter)
                        if getattr(entry, "isUninstantiated", False):
                            continue
                        # 在 entry scope 上 iter children (pure semantic, 不下钻 .syntax)
                        for child in _safe_iter_body(entry):
                            child_kind = str(getattr(child, "kind", ""))
                            # [E1.1 2026-08-27] 只收 InstanceSymbol — NetSymbol/Variable 由 driver_extractor 从
                            # assign expression 提取 (Plan F1 已 work). 这里若收 NetSymbol 会被 connection_extractor 当
                            # instance 调 portConnections 触发 AttributeError (NetSymbol 没 portConnections).
                            # [iter_112] PrimitiveInstance (门级原语) 也含 'Instance' 子串 — 显式排除:
                            # 不是模块实例, connection_extractor 展开它会导致 get_path 自环 (iter_112 根因)。
                            if "Instance" in child_kind and "PrimitiveInstance" not in child_kind:
                                # 用 hierarchicalPath (semantic API) 拿完整路径
                                hp = _safe_attr(child, "hierarchicalPath", None)
                                hp_str = _safe_str(hp) if hp else None
                                if not hp_str:
                                    # 无 hp — 拼装 (从 generate block 拿 arrayIndex + entry name)
                                    arr_idx = getattr(entry, "arrayIndex", None)
                                    idx_str = f"[{arr_idx}]" if arr_idx is not None else "[?]"
                                    en = _safe_str(_safe_attr(entry, "name", "gen"))
                                    cn = _safe_str(_safe_attr(child, "name", "_anon"))
                                    hp_str = f"{_safe_str(_safe_attr(module, 'name', 'top'))}.{en}{idx_str}.{cn}"
                                if hp_str in visited_paths:
                                    continue
                                visited_paths.add(hp_str)
                                parent_module = _safe_str(_safe_attr(module, "name", None))
                                wrappers.append(SemanticInstanceWrapper(child, parent_module=parent_module))
                    # 也递归到 entry 里可能嵌套的 GenerateBlock (generate-if 在 generate-for 内)
                    for entry in entries:
                        for child in _safe_iter_body(entry):
                            if "GenerateBlock" in str(getattr(child, "kind", "")):
                                # 嵌套 generate, 走 collect_in_generate_entry 模式
                                # (简化: 暂不下钻嵌套, 当前 case27 无此需求)
                                pass
                # GenerateBlock (无 gen-var, generate if / case 单 block): 也下钻
                # [E1.2 2026-08-27] 跟 GenerateBlockArray 一样只收 InstanceSymbol — Variable/Net
                # 会让 connection_extractor 当 instance 调 portConnections → AttributeError
                elif "GenerateBlock" in kind and "GenerateBlockArray" not in kind:
                    if getattr(member, "isUninstantiated", False):
                        continue
                    for child in _safe_iter_body(member):
                        child_kind = str(getattr(child, "kind", ""))
                        if "Instance" in child_kind and "PrimitiveInstance" not in child_kind:
                            hp = _safe_attr(child, "hierarchicalPath", None)
                            hp_str = _safe_str(hp) if hp else None
                            if hp_str and hp_str not in visited_paths:
                                visited_paths.add(hp_str)
                                wrappers.append(SemanticInstanceWrapper(
                                    child, parent_module=_safe_str(_safe_attr(module, "name", None))
                                ))

        # Walk 所有 top-level module
        for module in self.get_modules():
            collect_in_module(module)

        return wrappers

    def _genvar_index_from_hp(self, instance) -> int | None:
        """[iter_109] 从实例 hierarchicalPath 取 generate entry 索引.

        generate-for 实例每个 entry 是独立 InstanceSymbol, hp 形如 'top.g[2].U'
        (带 entry 索引); 其端口连接表达式里的 genvar (如 arr[i]) 在符号层仍是
        NamedValue('i'), 需用 entry 索引替换 → arr[2]. 取最后一个 [N] (最内层
        generate entry). 非 generate 实例或无索引返回 None.
        """
        try:
            sym = getattr(instance, "_symbol", None) or instance
            hp = getattr(sym, "hierarchicalPath", None)
            if hp is None:
                return None
            hps = str(hp)
            import re as _re_gi
            _m = _re_gi.findall(r"\[(\d+)\]", hps)
            return int(_m[-1]) if _m else None
        except Exception:
            return None

    def _eval_select_index(self, sel, gidx: int | None) -> int | None:
        """[iter_109] 位选/元素选索引求值 (generate-for 连接表达式).

        支持: Literal (常量) / Conversion (解包) / NamedValue (generate entry 内
        视为 loop var → gidx) / BinaryOp (+/- 折叠). 求不出返回 None (调用方
        落 '?' 占位, 不静默丢连接).
        """
        if sel is None:
            return None
        k = str(getattr(sel, "kind", ""))
        try:
            if "Literal" in k:
                # pyslang IntegerLiteral: str() 是类名, 数值在 .value (SVInt)
                _v = getattr(sel, "value", None)
                if _v is not None:
                    try:
                        return int(str(_v))
                    except (ValueError, TypeError):
                        return None
                try:
                    return int(str(sel))
                except (ValueError, TypeError):
                    return None
            if "Conversion" in k:
                for _a in ("operand", "value", "inner", "expr"):
                    _v = getattr(sel, _a, None)
                    if _v is not None:
                        return self._eval_select_index(_v, gidx)
                return None
            if "NamedValue" in k:
                # generate entry 内 NamedValue selector 视为 loop var → gidx
                return gidx
            if "BinaryOp" in k:
                l = self._eval_select_index(getattr(sel, "left", None), gidx)
                r = self._eval_select_index(getattr(sel, "right", None), gidx)
                if l is None or r is None:
                    return None
                op = str(getattr(sel, "op", ""))
                if "Add" in op or "+" in op:
                    return l + r
                if "Sub" in op or "-" in op:
                    return l - r
                if "Mul" in op or "*" in op:
                    return l * r
            return None
        except Exception:
            return None

    def _conn_expr_to_signal(self, expr, instance) -> str | None:
        """[iter_109] 解开实例端口连接表达式 → 信号名 (含数组元素/位选).

        处理: NamedValue (直接信号名) / ElementSelect·RangeSelect (base[sel]).
        ElementSelect 的 selector 若是 genvar NamedValue ('i'), 用实例 hp 的
        generate entry 索引替换 (arr[i] → arr[2]); 非 genvar/无法解析 → '?' 占位
        (保持图节点存在, 不静默丢连接).
        """
        if expr is None:
            return None
        k = str(getattr(expr, "kind", ""))
        try:
            if "RangeSelect" in k:
                # [iter_119] semantic RangeSelectExpression: left/right 在 expr 上
                # (无 .selector), selectionKind 区分 +: (IndexedUp) / -: (IndexedDown)
                # / 普通 [msb:lsb] (Simple). iter_118 S2 四级嵌套 .a(a[i*4+:4]) /
                # .y(y[j*2+:2]) 因此恒 '?' 占位 — 逐界 _eval_select_index 求值,
                # +:/ -: 换算成 [hi:lo] (msb:lsb) 命名。
                val = getattr(expr, "value", None)
                base = None
                if val is not None and hasattr(val, "symbol") and val.symbol is not None:
                    try:
                        base = str(val.symbol.name)
                    except (UnicodeDecodeError, TypeError):
                        base = None
                if base is None:
                    base = self._conn_expr_to_signal(val, instance)
                if base is None:
                    return None
                _gi = self._genvar_index_from_hp(instance)
                a = self._eval_select_index(getattr(expr, "left", None), _gi)
                b = self._eval_select_index(getattr(expr, "right", None), _gi)
                if a is None or b is None:
                    return f"{base}[?]"
                selkind = str(getattr(expr, "selectionKind", ""))
                if "IndexedUp" in selkind:
                    # [base+:width] → 位 [base+width-1 : base]
                    hi, lo = a + b - 1, a
                elif "IndexedDown" in selkind:
                    # [base-:width] → 位 [base : base-width+1]
                    hi, lo = a, a - b + 1
                else:
                    hi, lo = max(a, b), min(a, b)
                return f"{base}[{hi}:{lo}]"
            if "ElementSelect" in k:
                val = getattr(expr, "value", None)
                sel = getattr(expr, "selector", None)
                # base: value 的 symbol 名 (也可能是嵌套 select → 递归)
                base = None
                if val is not None and hasattr(val, "symbol") and val.symbol is not None:
                    try:
                        base = str(val.symbol.name)
                    except (UnicodeDecodeError, TypeError):
                        base = None
                if base is None:
                    base = self._conn_expr_to_signal(val, instance)
                if base is None:
                    return None
                # selector → 索引文本 (支持 genvar i / i±k / 常量; 解析失败 → '?')
                idx = "?"
                if sel is not None:
                    _gi = self._genvar_index_from_hp(instance)
                    _val = self._eval_select_index(sel, _gi)
                    if _val is not None:
                        idx = str(_val)
                return f"{base}[{idx}]"
            # NamedValue / Identifier: 直接信号名
            if "NamedValue" in k or "Identifier" in k:
                if hasattr(expr, "symbol") and expr.symbol is not None:
                    try:
                        return str(expr.symbol.name)
                    except (UnicodeDecodeError, TypeError):
                        return None
            return None
        except Exception:
            return None

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

        # [D5] v11 InstanceSymbol always has portConnections
        for conn in inst_sym.portConnections:
            # port 属性有 name
            port_name = "?"
            if hasattr(conn, "port"):
                try:
                    port_name = str(conn.port.name)
                except (UnicodeDecodeError, TypeError):
                    port_name = "<id:non-utf8>"

            # expression 是 NamedValue,其 symbol 是信号
            # 也可能是 Assignment 表达式 (用于 output 端口连接，如 .q(signal))
            signal_name = "?"
            if hasattr(conn, "expression") and hasattr(conn.expression, "symbol"):
                # NamedValue expression
                try:
                    signal_name = str(conn.expression.symbol.name)
                except (UnicodeDecodeError, TypeError):
                    signal_name = "<id:non-utf8>"
            elif hasattr(conn, "expression"):
                expr = conn.expression
                # Check if it's an Assignment expression (output port connection)
                expr_kind = str(getattr(expr, "kind", ""))
                if "Assignment" in expr_kind:
                    # For Assignment expression (.q(signal)), signal is in left side
                    left = getattr(expr, "left", None)
                    if left:
                        # [iter_109] left 可能是 ElementSelect (如 .xo(arr[i+1])) —
                        # 原有 left.symbol 直接取 base 名会丢索引且 ElementSelect 无 symbol.
                        sig = self._conn_expr_to_signal(left, instance)
                        if sig:
                            signal_name = sig
                        elif hasattr(left, "symbol"):
                            try:
                                signal_name = str(left.symbol.name)
                            except (UnicodeDecodeError, TypeError):
                                signal_name = "<id:non-utf8>"
                # [iter_109] 顶层 ElementSelect/RangeSelect (如 .x(arr[i])):
                # 之前未处理 → signal_name 停留 "?" → 整条 conn 被丢 (generate-for
                # 数组元素实例连接全灭, verilog_cordic_core 暴露).
                elif "ElementSelect" in expr_kind or "RangeSelect" in expr_kind:
                    sig = self._conn_expr_to_signal(expr, instance)
                    if sig:
                        signal_name = sig
                # [iter_136] Conversion 壳 (端口位宽 ≠ 连接位宽 / 类型转换时,
                # pyslang 给 input 表达式包 Conversion, operand 才是真表达式):
                # 不剥壳 → signal_name 停留 "?" → 整条 conn 静默丢 (无 warning,
                # 违反 AGENTS.md §2) — iter_119 观察真身: leafm `input a` 1 位接
                # a[j*2+:2] 2 位切片, 嵌套 fixture 4/4 input 连接全缺, fanin 断
                # 在 u_leaf.a。output 侧是 Assignment(left=RangeSelect) 不受影响。
                elif "Conversion" in expr_kind:
                    operand = getattr(expr, "operand", None)
                    # 链式剥壳 (防 Conversion(Conversion(...)))
                    while (operand is not None
                           and "Conversion" in str(getattr(operand, "kind", ""))):
                        operand = getattr(operand, "operand", None)
                    if operand is not None:
                        sig = self._conn_expr_to_signal(operand, instance)
                        if sig:
                            signal_name = sig
                # [V15.2 2026-08-13] 方向 A: pyslang semantic AST 处理 ConcatenationExpression
                # 当 .port(expr) 的 expr 是 {a, b, c} 时, 原逻辑 (NamedValue/Assignment)
                # 不命中 → 整条 conn 被丢弃. 现在走 semantic AST 的 ConcatenationExpression.operands,
                # 每个 operand emit 一条 (port_name, signal_name) conn.
                # 例: .din({3'b0, offsetted}) → ('din', 'offsetted') (跳过 IntegerLiteral const)
                #     让 connection_extractor 生成 offsetted → u_clamp_u.din 跨实例连线
                elif "Concatenation" in expr_kind and hasattr(expr, "operands"):
                    for operand in expr.operands:
                        op_kind_str = str(getattr(operand, "kind", ""))
                        # 跳过 const literals (IntegerLiteral, RealLiteral, etc.)
                        if "Literal" in op_kind_str:
                            continue
                        # NamedValueExpression: operand.symbol.name
                        if hasattr(operand, "symbol") and operand.symbol is not None:
                            try:
                                connections.append((port_name, str(operand.symbol.name)))
                                continue
                            except (UnicodeDecodeError, TypeError) as e:
                                logger.warning("提取失败: %s", e)
                        # ElementSelect / RangeSelect (e.g. din[7:0]):
                        # operand.expr 是 inner NamedValue
                        inner = getattr(operand, "expr", None)
                        if inner is not None and hasattr(inner, "symbol") and inner.symbol is not None:
                            try:
                                connections.append((port_name, str(inner.symbol.name)))
                            except (UnicodeDecodeError, TypeError) as e:
                                logger.warning("提取失败: %s", e)

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

    def get_assignments(self, module) -> list:
        """获取模块的连续赋值语句

        Semantic AST: 遍历 always_ff/always_comb/连续赋值

        [FIX 2026-08-12 Plan F1] 给每个返回的 assign 加 `.genvar_ctx` 属性:
        - 顶层 assigns: genvar_ctx = {}
        - generate for 内的 assigns: genvar_ctx = {genvar_name: entry.arrayIndex}
          (e.g. gen_accum[1] 内的 assign → genvar_ctx = {'i': 1})
        - generate if / generate case 内的 assigns: genvar_ctx = {} (无 genvar,
          但 pyslang 已根据 condition filter 了 entries)

        下游 (driver_extractor) 读取 .genvar_ctx 后, 在提取 signal name 时
        把 expression 里的 genvar 引用 substitute 成具体值, 这样
        `acc[i+1]` 在 gen_accum[1] 内变成 `acc[2]`, 而不是合并成单个
        `acc[i+1]` 节点.
        """
        assignments = []

        def find_assignments(node: object, genvar_ctx: dict | None = None) -> None:
            import os as _os
            import sys as _sys
            _dbg = _os.environ.get('G1_DEBUG')
            if node is None:
                return
            kind = str(getattr(node, "kind", ""))
            ctx = genvar_ctx if genvar_ctx is not None else {}
            if _dbg:
                print(f'[FIND] kind={kind!r:50s} ctx={ctx}', file=_sys.stderr)

            # ContinuousAssign 语法
            if "ContinuousAssign" in kind:
                # [Plan F1] 存到 adapter._genvar_context (pyslang symbol 不可 setattr)
                self._genvar_context[id(node)] = dict(ctx)
                assignments.append(node)
                return  # 不递归到子节点
            # AssignmentExpression (procedural)
            # [#8 2026-08-28] kind 可能是 'ExpressionKind.Assignment' (pyslang v11)
            # 或 'AssignmentExpression' (旧), 统一用 "Assignment" 匹配。
            # **只存 _genvar_context, 不 append 到返回列表**: procedural 赋值由
            # always_extractor 处理 (assign_extractor 只处理 continuous),
            # append 会导致 assign 阶段误处理 procedural 产生重复/错误边。
            # (原始代码遍历不到 Timed 内的 procedural, 所以 get_assignments
            #  实际只返回 continuous; 本次修复扩展了遍历, 必须保持契约不变)
            elif "Assignment" in kind:
                self._genvar_context[id(node)] = dict(ctx)
                return  # 不递归到子节点, 也不 append (保持 get_assignments 只返回 continuous)

            # GenerateBlockArray (generate for 展开入口): 进入每个 entry,
            # 把 entry 的 arrayIndex 作为对应 genvar 的 substitute value
            if "GenerateBlockArray" in kind:
                entries = getattr(node, "entries", None) or []
                # Genvar name 从 generate block 拿
                genvar_name = None
                loop_var = getattr(node, "loopVariable", None)
                if loop_var is not None:
                    # [iter_141 CVA6] loopVariable.name 属性 getter 在非 utf8
                    # identifier 抛 UnicodeDecodeError (pybind) — safe_str 防护
                    try:
                        gn = getattr(loop_var, "name", None)
                        genvar_name = str(gn) if gn else None
                    except UnicodeDecodeError:
                        genvar_name = None
                for entry in entries:
                    # [Plan F1.2 2026-08-12] Skip uninstantiated entries
                    if getattr(entry, 'isUninstantiated', False):
                        continue
                    child_ctx = dict(ctx)
                    if genvar_name:
                        ai = getattr(entry, "arrayIndex", None)
                        if ai is not None:
                            try:
                                child_ctx[genvar_name] = int(str(ai))
                            except Exception as e:
                                logger.warning("提取失败: %s", e)
                    for child in self._iter_children(entry):
                        find_assignments(child, child_ctx)
                return

            # GenerateBlock (generate if 内的单个 block): 无 genvar, 保留 ctx
            if "GenerateBlock" in kind:
                # [Plan F1.2 2026-08-12] Skip uninstantiated branches
                # (generate if/case false branch: pyslang 仍 expose assign symbols,
                #  需手动 filter 避免 hallucinatory driver 边)
                if getattr(node, 'isUninstantiated', False):
                    return
                for child in self._iter_children(node):
                    find_assignments(child, ctx)
                return

            # ProceduralBlock (always_ff 等)
            if "ProceduralBlock" in kind:
                for child in self._iter_children(node):
                    find_assignments(child, ctx)
                return

            # TimedStatement (@(posedge clk) ...): 进入 .stmt 递归
            # [#8 2026-08-28] generate for 内的 always_ff 是
            # ProceduralBlock → Timed → Block → ExpressionStatement(Assignment),
            # 缺此分支导致 _genvar_context 永不填充, acc[i] 无法 substitute 成 acc[0],
            # generate 内所有 procedural 赋值丢失 DRIVER 边。
            if "Timed" in kind:
                for child in self._iter_children(node):
                    find_assignments(child, ctx)
                return

            # BlockStatement (begin ... end): 进入 .body 递归
            if "Block" in kind:
                for child in self._iter_children(node):
                    find_assignments(child, ctx)
                return

            # StatementList (多条语句): 进入 .list 递归
            # [#8 2026-08-28] 双赋值时 Block → List → ExpressionStatement 链
            if "List" in kind:
                for child in self._iter_children(node):
                    find_assignments(child, ctx)
                return

            # ExpressionStatement (acc[i] <= data_in;): 进入 .expr (AssignmentExpression)
            if "ExpressionStatement" in kind:
                expr = getattr(node, "expr", None)
                if expr is not None:
                    find_assignments(expr, ctx)
                return

        if hasattr(module, "body") and module.body:
            for member in module.body:
                find_assignments(member)

        return assignments

    def get_primitive_instances(self, module) -> list:
        """[iter_112] 获取模块体中的门级原语实例 (GatePrimitiveInstance).

        Verilog 门级原语 (and/or/xor/not/nand/nor/xnor/buf/...) 在 pyslang 里
        kind = SymbolKind.PrimitiveInstance — **不是** InstanceSymbol:
        无 definition / 无 body / 无端口声明, 各 extractor 此前把它们当
        "有 body 的模块实例"处理 → connection 无限递归 (`and0.and0...`),
        driver 侧输出永远无人驱动 (KoggeStone-BrentKung xor16.S[0..15] 全空).

        语义信息 (pyslang 11 探查确认):
        - .primitiveType = Symbol(SymbolKind.Primitive, "and"/"xor"/...)
        - .portConnections = [Assignment(left=输出端子), NamedValue(输入1), ...]
          → conn[0].left = 输出, conn[1..] = 输入 (Verilog 门原语首端子是输出)

        遍历与 get_assignments 同构: 下钻 GenerateBlockArray/GenerateBlock
        (skip uninstantiated), 收集 PrimitiveInstance; 不进入 procedural。
        generate-for 内的门同步记录 genvar ctx (id(prim) → {genvar: entry 索引},
        同 get_assignments 的 _genvar_context 模式 — pyslang symbol 不可 setattr)。
        """
        primitives = []

        def find_primitives(node: object, genvar_ctx: dict | None = None) -> None:
            if node is None:
                return
            kind = str(getattr(node, "kind", ""))
            ctx = genvar_ctx if genvar_ctx is not None else {}
            # 门级原语本身: 收集 + 记 ctx, 不再下钻 (无 body)
            if "PrimitiveInstance" in kind:
                self._primitive_genvar_context[id(node)] = dict(ctx)
                primitives.append(node)
                return
            # GenerateBlockArray (generate for): 逐 entry (skip uninstantiated),
            # entry 的 arrayIndex 作为 genvar substitute value
            if "GenerateBlockArray" in kind:
                entries = getattr(node, "entries", None) or []
                genvar_name = None
                loop_var = getattr(node, "loopVariable", None)
                if loop_var is not None:
                    gn = getattr(loop_var, "name", None)
                    if gn:
                        genvar_name = str(gn)
                for entry in entries:
                    if getattr(entry, "isUninstantiated", False):
                        continue
                    child_ctx = dict(ctx)
                    if genvar_name:
                        ai = getattr(entry, "arrayIndex", None)
                        if ai is not None:
                            try:
                                child_ctx[genvar_name] = int(str(ai))
                            except (ValueError, TypeError):
                                logger.warning("genvar 索引提取失败: %s", ai)
                    for child in self._iter_children(entry):
                        find_primitives(child, child_ctx)
                return
            # GenerateBlock (generate if/case): skip uninstantiated branch
            if "GenerateBlock" in kind:
                if getattr(node, "isUninstantiated", False):
                    return
                for child in self._iter_children(node):
                    find_primitives(child, ctx)
                return
            # 其余 (net/assign/always/...) 不含门原语 — 不下钻

        if hasattr(module, "body") and module.body:
            for member in module.body:
                find_primitives(member)

        return primitives

    def get_primitive_genvar_context(self, primitive) -> dict:
        """[iter_112] 拿门原语所在 generate entry 的 genvar 上下文.

        Returns:
            dict: {genvar_name: int_value} — 同 get_genvar_context 语义;
            顶层门返回 {}.
        """
        return self._primitive_genvar_context.get(id(primitive), {})

    def get_genvar_context(self, assign) -> dict:
        """[Plan F1 2026-08-12] 拿 assign 所在的 generate entry 的 genvar 上下文。

        Returns:
            dict: {genvar_name: int_value}
            - 顶层 assign: {}
            - generate for 内: {genvar_name: entry.arrayIndex}
              e.g. gen_accum[1] 里的 assign → {'i': 1}
            - generate if 内: {} (无 genvar)

        pyslang symbol 不可 setattr, 所以 context 存在 adapter._genvar_context (id-keyed dict).
        """
        return self._genvar_context.get(id(assign), {})

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
        # [iter_141 CVA6] getattr 属性 getter 非 utf8 解码炸 (pybind) → safe_attr
        return safe_attr(task, "name", "unknown")

    def get_function_name(self, func) -> str:
        """获取 function 名称"""
        return safe_attr(func, "name", "unknown")

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

    def _iter_generate_children(self, module, kind_marker: str):
        """[iter_108] 共享 generate 遍历 (net_declarations / always_blocks 去重).

        GenerateBlockArray (for/case 展开) entries + GenerateBlock (if/else/case
        item 单块), 跳过 isUninstantiated. 产出:
        (child, genvar_ctx, array_index, loop_var, container)
        - child: 匹配 kind_marker 的成员 (NetSymbol / ProceduralBlockSymbol)
        - container: entry (array) 或 member (单块) — hierarchicalPath 来源
          (net 用 child.hp, always 用 container.hp, 保持两函数原行为)
        """
        if not hasattr(module, "body") or not module.body:
            return
        for member in module.body:
            kind = str(getattr(member, "kind", ""))
            if "GenerateBlockArray" in kind:
                # genvar 名字 (从 loopVariable, pure semantic)
                genvar_name = None
                try:
                    lv = getattr(member, "loopVariable", None)
                    if lv is not None:
                        genvar_name = str(getattr(lv, "name", "") or "")
                except Exception:
                    genvar_name = None
                # entries (pure semantic: 直接 __iter__ 或 .entries fallback)
                try:
                    entries = list(member)
                except TypeError:
                    entries = getattr(member, "entries", None) or []
                for entry in entries:
                    if getattr(entry, "isUninstantiated", False):
                        continue
                    arr_idx = getattr(entry, "arrayIndex", None)
                    ctx = {}
                    if genvar_name and arr_idx is not None:
                        try:
                            ctx = {genvar_name: int(arr_idx)}
                        except (TypeError, ValueError):
                            ctx = {genvar_name: arr_idx}
                    try:
                        children = list(entry)
                    except TypeError:
                        children = self._iter_children(entry)
                    for child in children:
                        if kind_marker in str(getattr(child, "kind", "")):
                            yield child, dict(ctx), arr_idx, genvar_name or "", entry
            elif "GenerateBlock" in kind:
                # [iter_107] 单块 (if/else/case item): 跳过 isUninstantiated
                if getattr(member, "isUninstantiated", False):
                    continue
                try:
                    children = list(member)
                except TypeError:
                    children = self._iter_children(member)
                for child in children:
                    if kind_marker in str(getattr(child, "kind", "")):
                        yield child, {}, None, "", member


    def get_generate_net_declarations(self, module) -> list[dict]:
        """[Plan G3 2026-08-27 13:01] 纯 semantic 收集 generate-for/if/case 内
        展开后的带 init Net decl.

        [iter_108] 遍历逻辑收敛到 _iter_generate_children (与
        get_generate_always_blocks 去重); 本方法只做 Net 专属提取
        (name/initializer/hierarchical_path 用 child 的, 与 G3 原行为一致).

        Returns:
            list[dict], 每个 dict:
              name: str                 — 展开后信号名 (如 'prod')
              initializer: object       — pyslang semantic Expression
              genvar_ctx: dict          — {'i': 0} 之类 (0 = arrayIndex 数值)
              array_index: int|None
              hierarchical_path: str    — 独立 node id (区分多 entry 同短名)
              loop_var: str             — genvar 名字 (如 'i')
        """
        results: list[dict] = []
        for child, ctx, arr_idx, loop_var, _container in self._iter_generate_children(module, "Net"):
            try:
                nm = getattr(child, "name", "")
                nm = str(nm) if nm else ""
            except Exception:
                nm = ""
            if not nm:
                continue
            init = getattr(child, "initializer", None)
            # hierarchicalPath 用 NetSymbol 自身的 (G3 原行为)
            hp_str = ""
            try:
                hp = getattr(child, "hierarchicalPath", None)
                if hp is not None:
                    hp_str = str(hp) or ""
            except Exception:
                hp_str = ""
            results.append({
                "name": nm,
                "initializer": init,
                "genvar_ctx": dict(ctx),
                "array_index": arr_idx,
                "hierarchical_path": hp_str,
                "loop_var": loop_var,
                # [iter_101] 缺陷 B: 带声明位宽, net_decl_extractor 建节点用
                "width": self.extract_data_width(child),
            })
        return results


    def get_generate_always_blocks(self, module) -> list[dict]:
        """[#8 2026-08-28] 纯 semantic 收集 generate-for/if/case 内展开后的 always 块.

        [iter_108] 遍历逻辑收敛到 _iter_generate_children (与
        get_generate_net_declarations 去重); 本方法只做 ProceduralBlock 专属提取
        (hierarchical_path 用 container 的, 与 #8 原行为一致).

        Returns:
            list[dict], 每个 dict:
              always: object             — ProceduralBlockSymbol
              genvar_ctx: dict           — {'i': 0} 之类 (0 = arrayIndex 数值)
              array_index: int|None
              hierarchical_path: str     — generate block 路径 (供 node id)
              loop_var: str              — genvar 名字 (如 'i')
        """
        results: list[dict] = []
        for child, ctx, arr_idx, loop_var, container in self._iter_generate_children(module, "ProceduralBlock"):
            hp_str = ""
            try:
                hp = getattr(container, "hierarchicalPath", None)
                if hp is not None:
                    hp_str = str(hp) or ""
            except Exception:
                hp_str = ""
            results.append({
                "always": child,
                "genvar_ctx": dict(ctx),
                "array_index": arr_idx,
                "hierarchical_path": hp_str,
                "loop_var": loop_var,
            })
        return results


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
                        # [Bug-fix 2026-06-13] safe_str() 防 binary garbage
                        return _safe_str(name)
                    # [Bug-fix 2026-06-25] name is None (declarator name 解析失败),
                    # 返 f-string 避免 'cannot access local variable' UnboundLocalError.
                    # Vortex.sv 触发 (partial AST).
                    loc = getattr(first_decl, "location", None)
                    if loc is not None:
                        return f"<id@{getattr(loc, 'line', '?')}:{getattr(loc, 'column', '?')}>"
                    return "<id:unknown>"
                # decl_list 为空 (e.g. empty struct)
                return "<id:empty-decl>"
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

    def get_function_width(self, func) -> tuple[int, int] | None:
        """[REFACTOR 2026-08-07 A计划] 从 function symbol 的 returnType 提取 (msb, lsb)

        function [7:0] saturate(...) → returnType=PackedArrayType
        getBitVectorRange() → "[7:0]" → 解析 (7, 0)
        标量函数 (无打包范围) → None (用 EffectiveWidth)

        替代旧 regex 从源码文本扫 function 声明的方式，数据源改为 semantic AST。
        """
        import re
        rt = getattr(func, 'returnType', None)
        if rt is None:
            return None
        try:
            rng = rt.getBitVectorRange()  # "[7:0]" (str) 或 None
        except Exception:
            rng = None
        if rng:
            m = re.fullmatch(r'\[(\d+)(?::(\d+))?\]', str(rng).strip())
            if m:
                msb = int(m.group(1))
                lsb = int(m.group(2)) if m.group(2) else msb
                return (msb, lsb)
        return None

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
            # [V6.9 fix] pyslang semantic AST: BlockStatement.body 可以是 StatementList (有 .list)
            #       或单语句 (直接是 statement, 无 .list)
            #       BlockStatement 本身也可能有 .list 属性
            inner = getattr(stmt, "body", None)
            if inner:
                slist = getattr(inner, "list", None)
                if slist:
                    for s in slist:
                        self._collect_drivers_from_stmt(s, func_name, drivers)
                else:
                    # 如果 inner 是单语句而不是 StatementList，直接递归处理
                    ik = str(getattr(inner, "kind", ""))
                    if "List" in ik and "Statement" in ik:
                        # StatementList 但 .list 为空 - 尝试用 list() 迭代
                        try:
                            for s in list(inner):
                                self._collect_drivers_from_stmt(s, func_name, drivers)
                        except (TypeError, ValueError) as _e:
                            logger.debug("提取失败 ((TypeError, ValueError)): %s", _e)
                            pass
                    else:
                        self._collect_drivers_from_stmt(inner, func_name, drivers)
            else:
                # BlockStatement 本身有 .list
                slist = getattr(stmt, "list", None)
                if slist:
                    for s in slist:
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

    def _extract_signals_from_expr(self, expr, genvar_ctx: dict | None = None) -> list[str]:
        """从表达式中提取所有信号名

        Handles:
        - NamedValue: signal reference
        - ElementSelect: signal[bit] -> extract signal name
        - RangeSelect: signal[msb:lsb] -> extract signal name
        - Concatenation: {a, b, c}
        - BinaryExpression: a ^ b, a + b, etc.
        - UnaryExpression
        - IntegerLiteral: index value (not a signal)

        [G1 iter_038 2026-08-27] 新增 genvar_ctx 参数:
        - 顶层 expr 传 None 或 {}
        - generate for 内的 expr 传 {genvar_name: entry.arrayIndex}
          (e.g. gen_accum[1] 内的 RHS → ctx={'i': 1})
        - NamedValue.name 是 genvar → substitute 成 ctx[name] (int)
        - ElementSelect / RangeSelect / BinaryOp / ConditionalOp / Concatenation
          递归时传 ctx 到子节点

        Pure semantic API: NamedValue (.symbol.name), ElementSelect (.value/.selector),
        BinaryOp (.left/.right), ConditionalOp (.conditions/.left/.right) 全部 pyslang
        semantic AST, 不碰 .syntax.members / IdentifierNameSyntax / .identifier.value.
        """
        signals = []
        ctx = genvar_ctx or {}
        if expr is None:
            return signals

        kind = getattr(expr, "kind", None)
        if not kind:
            return signals

        kind_str = str(kind)

        # Syntax IdentifierName: syntax tree signal reference
        # [V6.9] pyslang syntax: .identifier.value has the name
        if "IdentifierName" in kind_str:
            ident = getattr(expr, "identifier", None)
            if ident:
                val = getattr(ident, "value", None) or str(ident).strip()
                if val:
                    signals.append(val.strip())
            return signals

        # ScopedName (syntax tree): req.addr → recurse into .left/.right
        # pyslang syntax AST: ScopedNameSyntax has .left (IdentifierName) and
        #   .right (IdentifierName or another ScopedName for deeper nesting)
        if "ScopedName" in kind_str:
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)
            left_parts = []
            if left:
                left_parts = self._extract_signals_from_expr(left)
            if right:
                right_parts = self._extract_signals_from_expr(right)
            # Build dotted path: left_part.right_part
            if left_parts and right_parts:
                for lp in left_parts:
                    for rp in right_parts:
                        signals.append(f"{lp}.{rp}")
            elif right_parts:
                signals.extend(right_parts)
            return signals

        # NamedValue: signal reference
        # [G1 iter_038] genvar substitute: name 在 ctx 里则替换 (e.g. 'i' in {'i': 1} -> '1')
        if "NamedValue" in kind_str:
            sym = getattr(expr, "symbol", None)
            if sym:
                name = _safe_attr(sym, "name", None)
                if name:
                    name_str = str(name)
                    if name_str in ctx:
                        signals.append(str(ctx[name_str]))
                    else:
                        signals.append(name_str)
            return signals

        # [V6.9] ConversionExpression (type casting): 只在 operand 是信号引用时递归
        if "Conversion" in kind_str:
            operand = getattr(expr, "operand", None)
            if operand:
                ok = str(getattr(operand, "kind", ""))
                # 跳过字面量 (IntegerLiteral, UnbasedUnsizedIntegerLiteral)
                if "IntegerLiteral" in ok or "UnbasedUnsized" in ok:
                    return signals
                signals.extend(self._extract_signals_from_expr(operand, ctx))
            return signals

        # [V6.9] InsideExpression: left inside { rangeList }
        # [G1 iter_038] recursion 传 ctx
        if "Inside" in kind_str:
            signals.extend(self._extract_signals_from_expr(getattr(expr, "left", None), ctx))
            rlist = getattr(expr, "rangeList", None)
            if rlist and hasattr(rlist, "__iter__"):
                for r in rlist:
                    l = getattr(r, "left", None)  # noqa: E741
                    if l:
                        signals.extend(self._extract_signals_from_expr(l, ctx))
                    rr = getattr(r, "right", None)
                    if rr:
                        signals.extend(self._extract_signals_from_expr(rr, ctx))
                    if not l and not rr:
                        signals.extend(self._extract_signals_from_expr(r, ctx))
            return signals

        # [V6.9] DistExpression: left dist { items }
        # [G1 iter_038] recursion 传 ctx
        if "Dist" in kind_str:
            left = getattr(expr, "left", None)
            if left:
                signals.extend(self._extract_signals_from_expr(left, ctx))
            items = getattr(expr, "items", None)
            if items and hasattr(items, "__iter__"):
                for item in items:
                    val = getattr(item, "value", None) or getattr(item, "left", None)
                    if val:
                        signals.extend(self._extract_signals_from_expr(val, ctx))
            return signals


        # MemberAccess: req.addr → extract full dotted path (semantic AST)
        if "MemberAccess" in kind_str:
            # pyslang semantic AST: MemberAccessExpression has:
            #   .value: the base expression (e.g. NamedValueExpression for 'req')
            #   .member: ClassPropertySymbol (e.g. 'addr')
            #   .left: may be None in semantic AST (use .value instead)
            #   .syntax: ScopedNameSyntax for the full dotted name
            left = getattr(expr, "left", None) or getattr(expr, "value", None)
            member = getattr(expr, "member", None)
            member_name = None
            if member:
                # ClassPropertySymbol: .name gives the property name
                # [iter_141 CVA6] str(member) 兜底在非 utf8 时 pybind 解码炸 → safe_str
                member_name = (_safe_attr(member, "name", None)
                               or _safe_attr(member, "value", None)
                               or safe_str(member).strip())
                # Strip pyslang Symbol(...) wrapper if present
                if member_name.startswith("Symbol("):
                    try:
                        member_name = member_name.split('"')[1]
                    except (IndexError, AttributeError) as _e:
                        logger.debug("提取失败 ((IndexError, AttributeError)): %s", _e)
                        pass
            if left and member_name:
                # Recurse into left to get the full dotted path parts
                # [G1 iter_038] recursion 传 ctx
                left_sigs = self._extract_signals_from_expr(left, ctx)
                if left_sigs:
                    for ls in left_sigs:
                        signals.append(f"{ls}.{member_name}")
                else:
                    # [V6.9] left might be a NamedValueExpression
                    # [iter_140 CVA6] _safe_attr(left,'symbol') 返回 symbol 对象
                    # 非 str — f-string 拼接时 pyslang name 解码可能 UnicodeDecodeError
                    # (大设计非 utf8 identifier) → safe_str 防护 (失败显式返回 '')
                    lname = _safe_attr(left, "symbol", None) or str(getattr(left, "name", "")).strip()
                    if lname:
                        lname_s = safe_str(lname)
                        member_s = safe_str(member_name)
                        if lname_s and member_s:
                            signals.append(f"{lname_s}.{member_s}")
            return signals

        # Concatenation: {a, b, c}
        # [G1 iter_038] recursion 传 ctx
        if "Concatenation" in kind_str:
            for op in getattr(expr, "operands", []):
                signals.extend(self._extract_signals_from_expr(op, ctx))
            return signals

        # ConditionalOp (ternary: g ? x0 : x1)
        # [V6.9] pyslang ConditionalOp 结构:
        #   .conditions: list of Condition objects (each has .expr)
        #   .left: true branch, .right: false branch
                # ConditionalOp (ternary: g ? x0 : x1)
        # [V6.9] 处理 semantic AST ConditionalOp 和 syntax ConditionalExpression
        # Syntax ConditionalExpression: .predicate/.left/.right 返回字符串
        # 需要遍历子节点来提取信号名
                # ConditionalOp (ternary: g ? x0 : x1)
        # [V6.9] 处理 semantic AST ConditionalOp 和 syntax ConditionalExpression
        if "ConditionalOp" in kind_str or "ConditionalExpression" in kind_str:
            # Semantic AST: .conditions 列表 (Condition objects), .left/.right 是 AST 节点
            conditions = getattr(expr, "conditions", None)
            if conditions:
                for cond in conditions:
                    ce = getattr(cond, "expr", None) or getattr(cond, "expression", None)
                    # [G1 iter_038] recursion 传 ctx
                    signals.extend(self._extract_signals_from_expr(ce, ctx))
            pred = getattr(expr, "predicate", None)
            if pred is not None and not isinstance(pred, str):
                # [G1 iter_038] recursion 传 ctx
                signals.extend(self._extract_signals_from_expr(pred, ctx))
            # Syntax AST: .left/.right 返回字符串, 需要遍历子节点
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)
            if left is not None and not isinstance(left, str):
                # [G1 iter_038] recursion 传 ctx
                signals.extend(self._extract_signals_from_expr(left, ctx))
            if right is not None and not isinstance(right, str):
                # [G1 iter_038] recursion 传 ctx
                signals.extend(self._extract_signals_from_expr(right, ctx))
            # [V6.9] Syntax: 如果 left/right 是字符串, 遍历子节点提取 IdentifierName
            if (left is None or isinstance(left, str)) or (right is None or isinstance(right, str)):
                try:
                    for child in expr:
                        ck = str(getattr(child, "kind", ""))
                        if "IdentifierName" in ck:
                            ident = getattr(child, "identifier", None)
                            if ident:
                                val = getattr(ident, "value", None) or str(ident).strip()
                                if val:
                                    signals.append(val.strip())
                        elif "ConditionalPredicate" in ck or "Predicate" in ck:
                            # 递归提取条件信号
                            try:
                                for pchild in child:
                                    pck = str(getattr(pchild, "kind", ""))
                                    if "IdentifierName" in pck:
                                        pident = getattr(pchild, "identifier", None)
                                        if pident:
                                            pval = getattr(pident, "value", None) or str(pident).strip()
                                            if pval:
                                                signals.append(pval.strip())
                            except (TypeError, AttributeError) as e:
                                logger.warning("提取失败: %s", e)
                except (TypeError, AttributeError) as e:
                    logger.warning("提取失败: %s", e)
            return signals

        # ConditionalOp (ternary: g ? x0 : x1)
        # [V6.9] pyslang ConditionalOp 结构:
        #   .conditions: list of Condition objects (each has .expr)
        #   .left: true branch, .right: false branch
                # ConditionalOp (ternary: g ? x0 : x1)
        # [V6.9] 处理 semantic AST ConditionalOp 和 syntax ConditionalExpression
        # Syntax ConditionalExpression: .predicate/.left/.right 返回字符串
        # 需要遍历子节点来提取信号名
                # ConditionalOp (ternary: g ? x0 : x1)
        # [V6.9] 处理 semantic AST ConditionalOp 和 syntax ConditionalExpression
        if "ConditionalOp" in kind_str or "ConditionalExpression" in kind_str:
            # Semantic AST: .conditions 列表 (Condition objects), .left/.right 是 AST 节点
            conditions = getattr(expr, "conditions", None)
            if conditions:
                for cond in conditions:
                    ce = getattr(cond, "expr", None) or getattr(cond, "expression", None)
                    # [G1 iter_038] recursion 传 ctx
                    signals.extend(self._extract_signals_from_expr(ce, ctx))
            pred = getattr(expr, "predicate", None)
            if pred is not None and not isinstance(pred, str):
                # [G1 iter_038] recursion 传 ctx
                signals.extend(self._extract_signals_from_expr(pred, ctx))
            # Syntax AST: .left/.right 返回字符串, 需要遍历子节点
            left = getattr(expr, "left", None)
            right = getattr(expr, "right", None)
            if left is not None and not isinstance(left, str):
                # [G1 iter_038] recursion 传 ctx
                signals.extend(self._extract_signals_from_expr(left, ctx))
            if right is not None and not isinstance(right, str):
                # [G1 iter_038] recursion 传 ctx
                signals.extend(self._extract_signals_from_expr(right, ctx))
            # [V6.9] Syntax: 如果 left/right 是字符串, 遍历子节点提取 IdentifierName
            if (left is None or isinstance(left, str)) or (right is None or isinstance(right, str)):
                try:
                    for child in expr:
                        ck = str(getattr(child, "kind", ""))
                        if "IdentifierName" in ck:
                            ident = getattr(child, "identifier", None)
                            if ident:
                                val = getattr(ident, "value", None) or str(ident).strip()
                                if val:
                                    signals.append(val.strip())
                        elif "ConditionalPredicate" in ck or "Predicate" in ck:
                            # 递归提取条件信号
                            try:
                                for pchild in child:
                                    pck = str(getattr(pchild, "kind", ""))
                                    if "IdentifierName" in pck:
                                        pident = getattr(pchild, "identifier", None)
                                        if pident:
                                            pval = getattr(pident, "value", None) or str(pident).strip()
                                            if pval:
                                                signals.append(pval.strip())
                            except (TypeError, AttributeError) as e:
                                logger.warning("提取失败: %s", e)
                except (TypeError, AttributeError) as e:
                    logger.warning("提取失败: %s", e)
            return signals

        # AssignmentExpression: out_addr = req.addr → recurse into left/right
        if "Assignment" in kind_str:
            # [G1 iter_038] 传 ctx 给 left/right recursion
            signals.extend(self._extract_signals_from_expr(getattr(expr, "left", None), ctx))
            signals.extend(self._extract_signals_from_expr(getattr(expr, "right", None), ctx))
            return signals

        # BinaryExpression: a ^ b, a + b, etc.
        if "Binary" in kind_str:
            # [G1 iter_038] 传 ctx 给 left/right recursion
            signals.extend(self._extract_signals_from_expr(getattr(expr, "left", None), ctx))
            signals.extend(self._extract_signals_from_expr(getattr(expr, "right", None), ctx))
            return signals

        # UnaryExpression
        if "Unary" in kind_str:
            # [G1 iter_038] 传 ctx 给 operand recursion
            signals.extend(self._extract_signals_from_expr(getattr(expr, "operand", None), ctx))
            return signals

        # CallExpression / Invocation: system function call e.g. $signed(a)
        # [V6.9] $signed(a) is parsed as Call($signed, args=[a]), not Conversion.
        # Recurse into arguments to extract signal names.
        if "Call" in kind_str or "Invocation" in kind_str:
            args = getattr(expr, "arguments", None) or getattr(expr, "args", None) or []
            if args and hasattr(args, "__iter__") and not isinstance(args, str):
                for arg in args:
                    signals.extend(self._extract_signals_from_expr(arg))
            return signals

        # ConversionExpression (type casting) - recurse into operand
        if "Conversion" in kind_str:
            signals.extend(self._extract_signals_from_expr(getattr(expr, "operand", None)))
            return signals

        # [iter_118] genvar-ctx 索引求值 (generate-for 内 assign 的 RHS 位选):
        # slang 对 entry 内 x[i] / x[i-1] 的 selector 保持 NamedValue('i') /
        # BinaryOp(i-1), 不 fold 成常量 — 旧逻辑 (非 Literal/Parameter) 直接
        # fallback 返回 base → RHS x[i-1] 错解析成整总线 x (S8 深链死端;
        # case27 acc[i]+prod 同病, iter_035 起未被图级断言捕获).
        # 此处用 generate entry 的 genvar ctx 求值: NamedValue→ctx[name],
        # BinaryOp → 递归折叠 (+ - * /), 求不出返回 None (调用方保持旧行为).
        def _fold_sel(sel: object):
            if sel is None:
                return None
            sk = str(getattr(sel, "kind", ""))
            if "Literal" in sk:
                v = _safe_attr(sel, "constant", None) or _safe_attr(sel, "value", None)
                if v is not None:
                    # [iter_118] ConstantValue.integer 是对象不是 int —
                    # 统一 int(str(...)) 解 (str(SVInt)='1')
                    try:
                        iv = v.integer if hasattr(v, "integer") else v
                        return int(str(iv))
                    except (ValueError, TypeError):
                        return None
                return None
            if "NamedValue" in sk:
                sym = _safe_attr(sel, "symbol", None)
                nm = _safe_attr(sym, "name", None) or getattr(sel, "name", None)
                if nm is None:
                    return None
                nm = str(nm)
                return ctx.get(nm) if nm in ctx else None
            if "BinaryOp" in sk:
                op = getattr(sel, "op", None)
                opn = str(getattr(op, "name", op)).lower()
                l = _fold_sel(getattr(sel, "left", None))
                r = _fold_sel(getattr(sel, "right", None))
                if l is None or r is None:
                    return None
                try:
                    if opn in ("add", "plus", "+"):
                        return l + r
                    if opn in ("subtract", "minus", "-"):
                        return l - r
                    if opn in ("multiply", "times", "*"):
                        return l * r
                    if opn in ("divide", "div", "/"):
                        return int(l / r) if r else None
                except (ValueError, TypeError, ZeroDivisionError):
                    return None
                return None
            if "Conversion" in sk:
                return _fold_sel(getattr(sel, "operand", None))
            return None

        # ElementSelect: signal[bit] - extract full name signal[bit]
        if "ElementSelect" in kind_str:
            # Get the base signal
            # [G1 iter_038] 传 ctx 给 base + selector recursion
            base_signals = self._extract_signals_from_expr(_safe_attr(expr, "value", None), ctx)
            # Get the selector (bit index)
            selector = getattr(expr, "selector", None)
            if selector and base_signals:
                # selector is an expression (IntegerLiteral or ParameterExpression)
                sel_kind = getattr(selector, "kind", None)
                if sel_kind:
                    sel_kind_str = str(sel_kind)
                    if "IntegerLiteral" in sel_kind_str:
                        # Get the integer value
                        # [G1 iter_038] pyslang 11.x folded selectors expose .constant (ConstantValue)
                        #   not .value. Try .constant first, fallback to .value.
                        sel_val = _safe_attr(selector, "constant", None)
                        if sel_val is None:
                            sel_val = _safe_attr(selector, "value", None)
                        if sel_val is not None and hasattr(sel_val, "integer"):
                            try:
                                sel_val = int(sel_val.integer)
                            except Exception:
                                sel_val = str(sel_val.integer)
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
                    else:
                        # [iter_118] genvar-ctx 求值 (NamedValue 'i' / BinaryOp 'i-1'):
                        # generate-for entry 内 RHS 位选 — 修 x[i-1] 错解析成整总线
                        fold_idx = _fold_sel(selector)
                        if fold_idx is not None:
                            for base in base_signals:
                                signals.append(f"{base}[{fold_idx}]")
                            return signals
            # Fallback: just return base signal
            return base_signals

        # RangeSelect: signal[msb:lsb] - extract full name signal[msb:lsb]
        if "RangeSelect" in kind_str:
            # Get the base signal
            # [G1 iter_038] 传 ctx 给 base recursion
            base_signals = self._extract_signals_from_expr(_safe_attr(expr, "value", None), ctx)
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
                # [G1 iter_038] .constant fallback for pyslang 11.x folded selectors
                left_val = _safe_attr(left, "constant", None) or _safe_attr(left, "value", None)
                right_val = _safe_attr(right, "constant", None) or _safe_attr(right, "value", None)
                # .constant may be ConstantValue → unwrap .integer
                if hasattr(left_val, "integer"):
                    try:
                        left_val = int(left_val.integer)
                    except Exception:
                        left_val = str(left_val.integer)
                if hasattr(right_val, "integer"):
                    try:
                        right_val = int(right_val.integer)
                    except Exception:
                        right_val = str(right_val.integer)
                # [iter_118] genvar-ctx 求值 (generate entry 内 x[i*4+:4] 等范围)
                if left_val is None:
                    left_val = _fold_sel(left)
                if right_val is None:
                    right_val = _fold_sel(right)
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

        [iter_101] 缺陷 B 修复: NetSymbol (wire/逻辑网) 的 .syntax 是
        DeclaratorSyntax (无 .type), 且 declaredType 无 .width — 原两条路径都
        拿不到 → 返回 (1,0) 默认值, `wire [15:0] x` 全被当成 1 位。
        新增路径: declaredType.type (pyslang Type, str 如 'logic[15:0]')
        → getBitVectorRange() 返回 '[msb:lsb]' 字符串解析。
        """
        # Semantic AST: 尝试从 declaredType 获取位宽
        declared_type = getattr(data_decl, "declaredType", None)
        if declared_type:
            # [iter_101] NetSymbol 主路径: declaredType.type.getBitVectorRange()
            # → '[15:0]' 字符串 (实测 pyslang 11, 含非零 lsb 也正确)
            try:
                dtt = getattr(declared_type, "type", None)
                if dtt is not None:
                    has_fixed = getattr(dtt, "hasFixedRange", False)
                    if has_fixed:
                        rng_str = str(dtt.getBitVectorRange())
                        import re as _re_bw
                        _m = _re_bw.match(r"\[\s*(-?\d+)\s*:\s*(-?\d+)\s*\]", rng_str)
                        if _m:
                            return (int(_m.group(1)), int(_m.group(2)))
            except Exception:
                pass
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
                                def get_int(node: object) -> int:
                                    if node is None:
                                        return 0
                                    if hasattr(node, "literal") and node.literal:
                                        try:
                                            return int(node.literal.valueText)
                                        except Exception as e:
                                            logger.warning("提取失败: %s", e)
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

    def visit(self, callback: Callable) -> None:
        """遍历 Semantic AST 所有节点"""
        self._root.visit(callback)

    def visit_module(self, module: object, callback: Callable) -> None:
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
            except TypeError as e:
                logger.debug("子节点迭代失败: %s", e)
                pass

        # 处理常见属性
        for attr in [
            "members",
            "body",
            "statement",
            "statements",
            "stmt",       # [#8 2026-08-28] TimedStatement (@(posedge clk) ...) 用 .stmt,
                          # 不是 .statement — 缺它导致 generate always 内赋值拿不到 genvar_ctx
            "list",       # [#8 2026-08-28] StatementKind.List 的语句列表 (.list),
                          # 双赋值时 Block → List → ExpressionStatement 链需要它
            "left",
            "right",
            "expr",
            "condition",
            "consequent",
            "alternate",
        ]:
            try:
                child = getattr(node, attr, None)
            except (RuntimeError, Exception) as e:
                # [FIX 2026-06-26] pyslang: 'mutex lock failed: Invalid argument'
                # elaboration 不完整时, InstanceSymbol attribute access 死锁
                # 注: 某些 native segfault 会绕过 RuntimeError 抛 BaseException
                try:
                    if 'mutex' not in str(e).lower():
                        raise
                except Exception as e2:
                    logger.debug("pyslang mutex 防御 (partial AST): %s", e2)
                child = None
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

        [P0-1 2026-06-13] 收口: 委托给 _safe.clean_name (单一规范实现),
        不再重复过滤逻辑。参见 _safe.py 文档。
        """
        return _clean_name_fn(name)

    @staticmethod
    def _safe_str(obj) -> str:
        """DEPRECATED: 委托给 _safe.safe_str (单一规范实现)。"""
        return safe_str(obj)

    def iter_modules(self) -> Iterator:
        """迭代模块 (InstanceSymbol)"""
        for item in self._root:
            if hasattr(item, "kind"):
                kind_str = str(item.kind)
                if "Instance" in kind_str:
                    yield item

    def get_definition(self, name: str) -> object:
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
        except (UnicodeDecodeError, TypeError):
            inst_name = None
        if not inst_name:
            try:
                array_name = instance_symbol.arrayName
            except (UnicodeDecodeError, TypeError):
                array_name = None
            if array_name:
                try:
                    arr_path = instance_symbol.arrayPath
                except (UnicodeDecodeError, TypeError):
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
            except (UnicodeDecodeError, TypeError):
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
    def parent(self) -> object:
        """兼容属性:返回类似 SyntaxTree 的 parent 节点结构

        对于顶级模块(parent_module is None),返回 None
        这样 _get_parent_module_name 会使用 fallback 逻辑。
        """
        if self.parent_module:

            class ParentModule:
                def __init__(self, name: str) -> None:
                    self.name = name
                    self.header = type("Header", (), {"name": type("Name", (), {"rawText": name})()})()

            return ParentModule(self.parent_module)
        return None


class SemanticInstanceDeclWrapper:
    """包装 InstanceSymbol 的 declaration 部分"""

    def __init__(self, instance_symbol):
        self._symbol = instance_symbol

    @property
    def name(self) -> object:
        """返回实例名称作为 TokenValue"""

        class TokenValue:
            def __init__(self, val: str) -> None:
                self.value = val

        return TokenValue(self._symbol.name)
