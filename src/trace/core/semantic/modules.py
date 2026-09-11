# modules.py — SemanticAdapter 的 modules 域 mixin (iter_176 分域搬迁)
#
# 方法名/签名与原 SemanticAdapter 完全一致 (API 面冻结测试锁定);
# `self` 即 SemanticAdapter 实例 (状态: _root/_compiler/_target_module/
# _fixed_names/_genvar_context/_spec_members 等), 无独立状态。
"""modules 域: module/instance/generate/primitive 导航"""
import logging
from typing import Callable, Iterator

import pyslang

from ..._safe import _safe_attr, _safe_str, clean_name, safe_attr, safe_str
from ..ast_utils import is_syntax_list, iter_syntax_list

from ._wrappers import SemanticInstanceDeclWrapper, SemanticInstanceWrapper  # noqa: E402

logger = logging.getLogger(__name__)


class ModulesMixin:
    """modules 域方法集 (mixin — 由 SemanticAdapter 组合)"""

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
        from ..native_adapter import get_module_instances_native

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




    def visit_module(self, module: object, callback: Callable) -> None:
        """遍历模块的所有节点"""
        if hasattr(module, "body") and module.body:
            module.body.visit(callback)



    def iter_modules(self) -> Iterator:
        """迭代模块 (InstanceSymbol)"""
        for item in self._root:
            if hasattr(item, "kind"):
                kind_str = str(item.kind)
                if "Instance" in kind_str:
                    yield item
