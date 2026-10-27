# exprs_drivers.py — SemanticAdapter 的 exprs_drivers 域 mixin (iter_176 分域搬迁)
#
# 方法名/签名与原 SemanticAdapter 完全一致 (API 面冻结测试锁定);
# `self` 即 SemanticAdapter 实例 (状态: _root/_compiler/_target_module/
# _fixed_names/_genvar_context/_spec_members 等), 无独立状态。
"""exprs_drivers 域: 赋值/数据声明/驱动/任务函数参数"""
import logging
from typing import Callable, Iterator

import pyslang

from ..._safe import _safe_attr, _safe_str, clean_name, safe_attr, safe_str
from ..ast_utils import is_syntax_list, iter_syntax_list

logger = logging.getLogger(__name__)

from ._expr_helpers import (  # noqa: E402
    _expr_assignment,
    _expr_binary,
    _expr_call,
    _expr_concatenation,
    _expr_conditional,
    _expr_conversion,
    _expr_dist,
    _expr_element_select,
    _expr_identifier_name,
    _expr_inside,
    _expr_integer_literal,
    _expr_member_access,
    _expr_named_value,
    _expr_range_select,
    _expr_scoped_name,
    _expr_unary,
)


class ExprsDriversMixin:
    """exprs_drivers 域方法集 (mixin — 由 SemanticAdapter 组合)"""

    def get_generate_locals_index(self) -> dict[str, set[str]]:
        """[iter_274] 所有 generate 块的 `{块路径: 块内声明的信号名}`。

        供 connection_extractor 用: 实例端口连到**块内局部信号**时, 父侧 id 必须带
        块路径 (`top.G[0].local_wire`), 否则跨轮同名 wire 会塌缩成 `top.local_wire`。

        路径相对层级起点 (含顶层实例名), 与实例的 hierarchicalPath 前缀一致。
        结果缓存在 adapter 上 (elaboration 不变 → 索引不变)。
        """
        cached = getattr(self, "_gen_locals_index", None)
        if cached is not None:
            return cached

        index: dict[str, set[str]] = {}

        def locals_of(block) -> set[str]:
            names = set()
            try:
                members = list(block)
            except TypeError:
                return names
            for sym in members:
                if str(getattr(sym, "kind", "")) in ("SymbolKind.Net", "SymbolKind.Variable"):
                    try:
                        nm = str(getattr(sym, "name", "") or "")
                    except (UnicodeDecodeError, TypeError):
                        nm = ""
                    if nm:
                        names.add(nm)
            return names

        def path_of(sym) -> str:
            try:
                return str(sym.hierarchicalPath)
            except (UnicodeDecodeError, TypeError, AttributeError):
                return ""

        def walk_scope(scope, depth: int = 0) -> None:
            if depth > 40:
                return
            try:
                members = list(scope)
            except TypeError:
                return
            for m in members:
                kind = str(getattr(m, "kind", ""))
                if "GenerateBlockArray" in kind:
                    for entry in (getattr(m, "entries", None) or list(m)):
                        p = path_of(entry)
                        if p:
                            index[p] = locals_of(entry)
                        walk_scope(entry, depth + 1)
                elif "GenerateBlock" in kind:
                    p = path_of(m)
                    if p:
                        index[p] = locals_of(m)
                    walk_scope(m, depth + 1)

        root = getattr(self, "_root", None)
        for top in getattr(root, "topInstances", []) or []:
            walk_scope(getattr(top, "body", None))

        self._gen_locals_index = index
        return index

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

        def _rel_scope(node, module) -> str:
            """[iter_274] generate 块的相对作用域路径 (如 "G[0]" / "GEN_IF")。"""
            try:
                hp = str(node.hierarchicalPath)
                mhp = str(module.hierarchicalPath)
            except (UnicodeDecodeError, TypeError, AttributeError):
                return ""
            if hp.startswith(mhp + "."):
                return hp[len(mhp) + 1:]
            return ""

        def _block_locals(block) -> set[str]:
            """[iter_274] 块内**声明**的信号名 (Net / Variable); genvar 参数不算。"""
            names = set()
            try:
                members = list(block)
            except TypeError:
                return names
            for sym in members:
                kind = str(getattr(sym, "kind", ""))
                if kind in ("SymbolKind.Net", "SymbolKind.Variable"):
                    try:
                        nm = str(getattr(sym, "name", "") or "")
                    except (UnicodeDecodeError, TypeError):
                        nm = ""
                    if nm:
                        names.add(nm)
            return names

        def _with_scope(ctx: dict, scope: str, locals_: set[str]) -> dict:
            """把作用域信息并入 ctx (保留 genvar 替换 + 父块路径)。"""
            if not scope:
                return ctx
            out = dict(ctx)
            parent = out.get("__scope_path__", "")
            out["__scope_path__"] = f"{parent}.{scope}" if parent else scope
            merged = set(out.get("__scope_locals__") or ())
            merged |= locals_
            out["__scope_locals__"] = merged
            return out

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
                    # [iter_274] generate 块作用域: 块内局部信号必须带块路径
                    # (top.G[0].local_wire), 否则 4 轮同名 wire 会塌缩成一个节点。
                    child_ctx = _with_scope(child_ctx, _rel_scope(entry, module), _block_locals(entry))
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
                # [iter_274] generate if/case 块的作用域 (如 GEN_IF)
                child_ctx = _with_scope(ctx, _rel_scope(node, module), _block_locals(node))
                for child in self._iter_children(node):
                    find_assignments(child, child_ctx)
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

        if hasattr(module, "body") and safe_attr(module, "body", []):
            for member in safe_attr(module, "body", []):
                find_assignments(member)

        return assignments



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

        if hasattr(module, "body") and safe_attr(module, "body", []):
            for member in safe_attr(module, "body", []):
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

        if hasattr(module, "body") and safe_attr(module, "body", []):
            for member in safe_attr(module, "body", []):
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



    def get_function_declarations(self, module) -> list:
        """获取模块的 function 声明"""
        funcs = []

        if hasattr(module, "body") and safe_attr(module, "body", []):
            for member in safe_attr(module, "body", []):
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



    def get_drivers(self, signal_name: str) -> list:
        """获取信号的驱动源 (Semantic AST 暂不支持)"""
        return []



    def get_loads(self, signal_name: str) -> list:
        """获取信号的负载 (Semantic AST 暂不支持)"""
        return []



    def get_net_declarations(self, module) -> list:
        """获取模块的 net/wire 声明"""
        nets = []

        if hasattr(module, "body") and safe_attr(module, "body", []):
            for member in safe_attr(module, "body", []):
                kind = str(getattr(member, "kind", ""))
                if "Net" in kind:
                    nets.append(member)

        return nets



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
                # [iter_297 / PLAN P9.1] signedness（加宽扩展方向）
                "signed": self.extract_data_signed(child),
            })
        return results




    def get_net_aliases(self, module) -> list:
        """获取模块的 NetAlias (alias 语句)"""
        aliases = []

        if hasattr(module, "body") and safe_attr(module, "body", []):
            for member in safe_attr(module, "body", []):
                kind = str(getattr(member, "kind", ""))
                if "NetAlias" in kind:
                    aliases.append(member)

        return aliases



    def get_variable_declarations(self, module) -> list:
        """获取模块的变量声明

        返回 DataDeclaration 语法节点（用于位宽提取），而不是 VariableSymbol 对象。
        遍历 safe_attr(module, "body", []).definition.syntax.members 获取 DataDeclaration 节点。
        """
        decls = []

        if hasattr(module, "body") and safe_attr(module, "body", []):
            definition = getattr(safe_attr(module, "body", []), "definition", None)
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

        if hasattr(module, "body") and safe_attr(module, "body", []):
            for member in safe_attr(module, "body", []):
                kind = str(getattr(member, "kind", ""))
                if "DataDeclaration" in kind or "Net" in kind or "Variable" in kind:
                    decls.append(member)

        return decls



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
            return _expr_identifier_name(self, expr, ctx)
        if "ScopedName" in kind_str:
            return _expr_scoped_name(self, expr, ctx)
        if "NamedValue" in kind_str:
            return _expr_named_value(self, expr, ctx)
        if "Conversion" in kind_str:
            return _expr_conversion(self, expr, ctx)
        if "Inside" in kind_str:
            return _expr_inside(self, expr, ctx)
        if "Dist" in kind_str:
            return _expr_dist(self, expr, ctx)
        if "MemberAccess" in kind_str:
            return _expr_member_access(self, expr, ctx)
        if "Concatenation" in kind_str:
            return _expr_concatenation(self, expr, ctx)
        if "ConditionalOp" in kind_str or "ConditionalExpression" in kind_str:
            return _expr_conditional(self, expr, ctx)
        if "Assignment" in kind_str:
            return _expr_assignment(self, expr, ctx)
        if "Binary" in kind_str:
            return _expr_binary(self, expr, ctx)
        if "Unary" in kind_str:
            return _expr_unary(self, expr, ctx)
        if "Call" in kind_str or "Invocation" in kind_str:
            return _expr_call(self, expr, ctx)
        if "ElementSelect" in kind_str:
            return _expr_element_select(self, expr, ctx)
        if "RangeSelect" in kind_str:
            return _expr_range_select(self, expr, ctx)
        if "IntegerLiteral" in kind_str:
            return _expr_integer_literal(self, expr, ctx)

        # 未覆盖的 kind → 无信号 (保持原行为: 走到底返回空列表)
        return signals



    def extract_data_width(self, data_decl) -> tuple:
        """提取数据声明的位宽 (wire, reg, logic 等)

        支持两种方式:
        1. Semantic AST: 尝试从 declaredType 获取位宽
        2. Syntax Tree: 从 safe_attr(data_decl, "type", None).dimensions[0].specifier.selector 获取位宽

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
                            _msb, _lsb = int(_m.group(1)), int(_m.group(2))
                            if _msb == _lsb == 0 and type(data_decl).__name__ == "VariableSymbol":
                                return (1, 0)  # 标量变量沿用历史 (1,0) 约定
                            return (_msb, _lsb)
            except Exception as e:
                logger.debug("%s: 忽略 Exception: %s", __name__, e)
            if hasattr(declared_type, "width"):
                w = declared_type.width
                if hasattr(w, "value"):
                    return (int(w.value), 0)
            # [iter_307 / PLAN P13.6] unpacked array：节点宽度 = 元素宽度
            dtt0 = getattr(declared_type, "type", None)
            if dtt0 is not None and bool(getattr(dtt0, "isUnpackedArray", False)):
                et = getattr(dtt0, "elementType", None)
                ebw = getattr(et, "bitWidth", None)
                if ebw:
                    try:
                        return (1, 0) if int(ebw) == 1 else (int(ebw) - 1, 0)
                    except (TypeError, ValueError) as _e:
                        logger.debug("unpacked array 元素宽度提取失败: %s", _e)
            # [iter_299 / PLAN P11.1] packed struct/union 的 typedef 类型：
            # TypeAliasType 没有 getBitVectorRange/width，但有 bitWidth
            dtt = getattr(declared_type, "type", None)
            if dtt is not None and type(dtt).__name__ in (
                    "TypeAliasType", "PackedStructType", "PackedUnionType"):
                bw = getattr(dtt, "bitWidth", None)
                if bw:
                    try:
                        if int(bw) == 1:
                            return (1, 0)   # 标量沿用历史 (1,0) 约定
                        if int(bw) > 0:
                            return (int(bw) - 1, 0)
                    except (TypeError, ValueError) as _e:
                        logger.debug("bitWidth 提取失败: %s", _e)

        # [iter_307 / PLAN P13.6] 语义符号本身是 unpacked array（无 declaredType 时）
        st = getattr(data_decl, "type", None)
        if st is not None and bool(getattr(st, "isUnpackedArray", False)):
            et = getattr(st, "elementType", None)
            ebw = getattr(et, "bitWidth", None)
            if ebw:
                try:
                    return (1, 0) if int(ebw) == 1 else (int(ebw) - 1, 0)
                except (TypeError, ValueError) as _e:
                    logger.debug("unpacked array 元素宽度提取失败: %s", _e)

        # Syntax Tree: 从 type.dimensions 获取位宽
        # 数据声明结构: safe_attr(data_decl, "type", None).dimensions[0].specifier.selector.left/right
        if hasattr(data_decl, "type") and safe_attr(data_decl, "type", None):
            dt = safe_attr(data_decl, "type", None)
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

        # [iter_298 / PLAN P10.1] 整数类型关键字（DataDeclarationSyntax.type）
        t = getattr(data_decl, "type", None)
        if t is not None:
            kw = " ".join(str(getattr(t, "keyword", "") or "").split()).lower()
            widths = {"byte": 8, "shortint": 16, "int": 32,
                      "integer": 32, "longint": 64, "time": 64}
            if kw in widths:
                return (widths[kw] - 1, 0)

        # 默认 1 位
        return (1, 0)

    def get_packed_member_layout(self, var_symbol) -> list[dict] | None:
        """[iter_299 / PLAN P11.2] packed struct/union 的成员布局。

        返回 [{name, width, offset, signed}]（offset = 成员 LSB 在聚合中的位置）；
        非 packed struct/union 或无法解析 → None。
        struct: 首成员在 MSB；union: 所有成员 offset=0。
        """
        t = getattr(var_symbol, "type", None)
        ct = getattr(t, "canonicalType", None) or t
        if ct is None:
            return None
        is_struct = bool(getattr(ct, "isStruct", False))
        is_union = bool(getattr(ct, "isPackedUnion", False))
        if not (is_struct or is_union):
            return None
        syn = getattr(ct, "syntax", None)
        out = []
        for mem in getattr(syn, "members", []) or []:
            for decl in getattr(mem, "declarators", []) or []:
                try:
                    name = str(getattr(decl, "name", "") or "").strip()
                except (UnicodeDecodeError, TypeError):
                    name = ""
                if not name:
                    continue
                try:
                    field = ct.lookupName(name)
                except Exception as e:
                    logger.debug("%s: lookupName(%s) 失败: %s", __name__, name, e)
                    continue
                ftype = getattr(field, "type", None)
                width = getattr(ftype, "bitWidth", None)
                offset = getattr(field, "bitOffset", None)
                if width is None or offset is None:
                    continue
                out.append({
                    "name": name,
                    "width": int(width),
                    "offset": int(offset),
                    "signed": bool(getattr(ftype, "isSigned", False)),
                })
        return out or None

    def _packed_members_of_type(self, ftype, depth: int) -> list[dict]:
        """packed struct/union 类型的成员（递归 children，深度上限 depth）。"""
        ct = getattr(ftype, "canonicalType", None) or ftype
        if ct is None or depth <= 0:
            return []
        if not (bool(getattr(ct, "isStruct", False))
                or bool(getattr(ct, "isPackedUnion", False))):
            return []
        syn = getattr(ct, "syntax", None)
        out = []
        for mem in getattr(syn, "members", []) or []:
            for decl in getattr(mem, "declarators", []) or []:
                try:
                    name = str(getattr(decl, "name", "") or "").strip()
                except (UnicodeDecodeError, TypeError):
                    name = ""
                if not name:
                    continue
                try:
                    field = ct.lookupName(name)
                except Exception as e:
                    logger.debug("%s: lookupName(%s) 失败: %s", __name__, name, e)
                    continue
                ftype2 = getattr(field, "type", None)
                width = getattr(ftype2, "bitWidth", None)
                offset = getattr(field, "bitOffset", None)
                if width is None or offset is None:
                    continue
                out.append({
                    "name": name,
                    "width": int(width),
                    "offset": int(offset),
                    "signed": bool(getattr(ftype2, "isSigned", False)),
                    "children": self._packed_members_of_type(ftype2, depth - 1),
                })
        return out

    def get_packed_member_tree(self, var_symbol, max_depth: int = 8) -> list[dict] | None:
        """[iter_305 / PLAN P13.4] packed struct/union 的**递归**成员树。

        每项 {name,width,offset,signed,children}（offset 相对直接父成员）。
        非 packed 类型/不可解析 → None。深度上限 max_depth（默认 8）。
        """
        t = getattr(var_symbol, "type", None)
        tree = self._packed_members_of_type(t, max_depth)
        return tree or None

    def get_variable_symbols(self, module) -> dict:
        """[iter_299 / PLAN P11.1] 变量名 → 语义 VariableSymbol。

        `get_variable_declarations` 返回 syntax DataDeclarationSyntax，typedef
        （packed struct/union）在 syntax 层没有宽度/signedness；语义符号的
        `.type.bitWidth` / `.type.isSigned` 才是权威值。
        """
        out = {}
        if hasattr(module, "body") and safe_attr(module, "body", []):
            for member in safe_attr(module, "body", []):
                if str(getattr(member, "kind", "")) != "SymbolKind.Variable":
                    continue
                try:
                    name = self.clean_name(str(getattr(member, "name", "") or ""))
                except (UnicodeDecodeError, TypeError):
                    continue
                if name:
                    out[name] = member
        return out

    def extract_data_signed(self, data_decl) -> bool | None:
        """[iter_297 / PLAN P9.1] 声明是否 signed（None = 无法判定）。

        依次尝试 semantic 的 `type.isSigned` / `declaredType.type.isSigned` /
        `declaredType.isSigned`；pyslang 对 PackedArrayType/ScalarType 支持 isSigned。
        """
        for path in (("type",), ("declaredType", "type"), ("declaredType",)):
            cur = data_decl
            ok = True
            for attr in path:
                cur = getattr(cur, attr, None)
                if cur is None:
                    ok = False
                    break
            if not ok:
                continue
            # [iter_307 / PLAN P13.6] unpacked array: signedness 取元素类型
            if bool(getattr(cur, "isUnpackedArray", False)):
                et = getattr(cur, "elementType", None)
                if et is not None:
                    ev = getattr(et, "isSigned", None)
                    if ev is not None:
                        return bool(ev)
                continue
            try:
                val = getattr(cur, "isSigned", None)
            except Exception as e:  # 某些类型属性访问会抛
                logger.debug("%s: isSigned 读取失败: %s", __name__, e)
                continue
            if val is not None:
                return bool(val)

        # Syntax 回退（get_variable_declarations 返回 DataDeclarationSyntax）：
        #   type.signing.kind = TokenKind.SignedKeyword / UnsignedKeyword / Unknown
        t = getattr(data_decl, "type", None)
        if t is not None:
            signing = getattr(t, "signing", None)
            kind = str(getattr(signing, "kind", "") or "")
            if "Signed" in kind:
                return True
            if "Unsigned" in kind:
                return False
            kw = " ".join(str(getattr(t, "keyword", "") or "").split()).lower()
            # [iter_298 / PLAN P10.1] 整数类型默认 signedness
            if kw in ("integer", "int", "byte", "shortint", "longint"):
                return True
            if kw == "time":
                return False
            return False      # logic/reg/bit 默认 unsigned
        return None

    # =========================================================================
    # 遍历
    # =========================================================================
