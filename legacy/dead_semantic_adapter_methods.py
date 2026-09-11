# dead_semantic_adapter_methods.py — SemanticAdapter 的零调用方法 (iter_177 Step 10)
#
# 方豆原则: "用移出代替删除, 这样可以恢复"。
# 下列方法在 src/ + sim/tests/ 全仓**零调用** (含内部 self. 调用), iter_177 从
# `core/semantic/` 各 mixin 移出。经 AST 扫描 + grep 双向核实。
#
# 原位置: modules.py (get_generate_instances / iter_modules / visit_module);
#         classes.py (get_class_name); source_core.py (get_definition)
#
# 文档漂移顺带修正 (本次发现):
#   - docs/PYSLANG_SEMANTIC_USAGE.md 记 get_generate_instances 被
#     connection_extractor 使用 — 实测该调用早已不存在 (已同步改文档);
#   - 同文件已标注 get_class_name "⛔ UNUSED", 与实测一致。
#
# 未移出的近邻 (有意保留):
#   - `SemanticInstanceWrapper.get_parent_module / _get_parent_module_safe`
#     (在 semantic/_wrappers.py) 属**包装类** API, 与 native_adapter 的
#     wrapper 互为兼容实现, 不属于 SemanticAdapter 方法面 — 保留。
#
# 恢复: 粘回对应 mixin 类 (缩进 +4) 并更新
#   sim/tests/unit/test_semantic_adapter_api_surface.py 冻结表。
# 本文件不被任何模块 import (纯留存)。



# ── 原 src/trace/core/semantic/modules.py (git HEAD) ─────────────────────────────────────────
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


# ── 原 src/trace/core/semantic/modules.py ─────────────────────────────────────────
    def iter_modules(self) -> Iterator:
        """迭代模块 (InstanceSymbol)"""
        for item in self._root:
            if hasattr(item, "kind"):
                kind_str = str(item.kind)
                if "Instance" in kind_str:
                    yield item


# ── 原 src/trace/core/semantic/modules.py ─────────────────────────────────────────
    def visit_module(self, module: object, callback: Callable) -> None:
        """遍历模块的所有节点"""
        if hasattr(module, "body") and module.body:
            module.body.visit(callback)


# ── 原 src/trace/core/semantic/classes.py ─────────────────────────────────────────
    def get_class_name(self, cls) -> str:
        """获取 class 名称（处理 Unicode bug）"""
        fixed = self._fixed_names.get(id(cls))
        if fixed:
            return fixed
        try:
            return str(_safe_attr(cls, "name", "")).strip()
        except UnicodeDecodeError:
            return ""


# ── 原 src/trace/core/semantic/source_core.py ─────────────────────────────────────────
    def get_definition(self, name: str) -> object:
        """获取模块/类定义"""
        for item in self._root:
            if hasattr(item, "name") and item.name == name:
                return item
        return None
