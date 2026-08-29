"""
native_adapter.py — pyslang native API for instance extraction.

[Phase 1 2026-06-25] 方案 C Phase 1: pyslang native API implementation.

替代 semantic_adapter.get_module_instances() 的 recursive walk, 用 pyslang 11.0.0
的 native API (root.topInstances + InstanceSymbol.body + hierarchicalPath).

性能: CVA6 73 instances 4.4x speedup (265ms → 60ms)

兼容: 输出格式跟 SemanticInstanceWrapper 一样 (id, name, def_name, parent_module),
       14 个用户 files 不用改.
"""


import pyslang

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _safe_str(value) -> str | None:
    """[Bug-resistant] 跟 sv_query 一样 handle UnicodeDecodeError / binary garbage."""
    if value is None:
        return None
    try:
        s = str(value)
        if not s or s == "<id:binary>":
            return None
        return s
    except (UnicodeDecodeError, TypeError):
        return None


def _safe_hierarchical_path(symbol) -> str | None:
    """Get hierarchicalPath, safely."""
    try:
        hp = symbol.hierarchicalPath
        return _safe_str(hp)
    except (UnicodeDecodeError, TypeError):
        return None


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def get_module_instances_native(
    root: pyslang.RootSymbol,
    target_module: str | None = None,
) -> list:
    """[Phase 1 2026-06-25] pyslang native API for instance extraction.

    跟 semantic_adapter.get_module_instances() 输出兼容:
    - 返 list of wrapper-like objects
    - 每个有: _symbol (pyslang InstanceSymbol), type (TypeToken-like), parent_module
    - 支持 hierarchicalPath / name / definition lookup

    Args:
        root: pyslang RootSymbol (from compilation.getRoot())
        target_module: 如果指定, 只返以该 module 为 hierarchy 根的 instances.
                       如果 None, 返所有 instances (跟旧实现行为一致).

    Returns:
        list of SemanticInstanceWrapper-compatible objects.

    Strategy:
    1. 找 user target 在 topInstances 里 (or first top if not specified)
    2. 递归 walk InstanceSymbol.body
    3. 处理 GenerateBlockArray + GenerateBlock + InstanceArray
    4. 跳过 ProceduralBlock / Variable / Parameter (跟旧实现一致)

    [GAP-5 fix 2026-08-29] 移除 _is_user_module 过滤 (target=None 时):
    旧实现 (递归) 不过滤任何 top instance; 过滤会把 "只有 generate 块、无直接
    InstanceSymbol" 的合法 user top (如顶层 generate-for 实例化) 误判为 utility
    cell 而整棵跳过 → MIG 空。生产 (UnifiedTracer) 默认 target=None, 必须与
    递归行为一致。utility cell 过滤的诉求 (CVA6) 由 target 参数路径覆盖
    (指定 target 时只 walk 该子树), 无需启发式。
    """
    wrappers = []
    if root is None:
        return wrappers

    # 找 start point — user target or first top
    top_to_walk = _find_target_top(root, target_module)
    if top_to_walk is None:
        # Fall back: walk all top instances (与递归一致, 不过滤)
        for top in root.topInstances:
            _walk_instance(top, target_module or top.name, wrappers, root, target_module, is_top=True)
    else:
        _walk_instance(top_to_walk, target_module, wrappers, root, target_module, is_top=True)

    return wrappers


def _find_target_top(root: pyslang.RootSymbol, target_module: str | None):
    """[Helper] 找 user-specified target 在 topInstances 里."""
    if target_module is None:
        # 没指定 — 返第一个 top instance (与递归一致, 不过滤)
        for top in root.topInstances:
            return top
        return None
    # 指定了 — 找同名 top
    for top in root.topInstances:
        try:
            if top.name == target_module:
                return top
        except (UnicodeDecodeError, TypeError):
            continue
    return None


def _walk_instance(
    inst,
    parent_module: str,
    wrappers: list,
    root: pyslang.RootSymbol,
    target_module: str | None = None,
    is_top: bool = False,
    is_array_element: bool = False,
) -> None:
    """[Helper] 递归 walk InstanceSymbol, 处理 generate blocks.

    Mirrors semantic_adapter.get_module_instances() output:
    - 每个 instance wrapper: {_symbol, type, parent_module, ...}
    - type is TypeToken-like with .value
    - top-level target 本身不被 emit (跟旧实现一致 — 只 emit sub-instances)

    [GAP-1 fix 2026-08-29] parent_module 对齐递归语义:
    - 普通实例: parent = hierarchicalPath 去掉最后一段
      (递归: generate 内实例给 'top.gen_loop[0]', 普通实例给 'top')
    - 数组元素: parent = 自身 hierarchicalPath (递归 InstanceArray 分支的 child_path 语义)
    """
    try:
        inst_id = _safe_hierarchical_path(inst)
        if not inst_id:
            return
        try:
            _safe_str(inst.name)
        except (UnicodeDecodeError, TypeError):
            # [fix] 原 except 冗余包揽 Exception — 收窄到实际可能的解码/类型错误
            pass

        # Get type name (module name) via definition
        defn = getattr(inst, 'definition', None)
        type_name = None
        if defn is not None:
            try:
                type_name = _safe_str(defn.name)
            except (UnicodeDecodeError, TypeError):
                type_name = None

        # 跟旧实现一致: top-level target 本身不被 emit
        # 旧实现: 如果 node.kind 是 Instance, parent_path 是空 (即顶层), 且
        # hierarchicalPath 是 target module 名字本身 (不含 '.'), 跳过 emit
        # [GAP-5 fix 2026-08-29] target_module=None 时所有 walked top 都是
        # "顶层目标" — 一律不 emit (与递归一致: 递归对顶层实例只 recurse 不 emit)
        if is_top and (inst_id == target_module or target_module is None):
            # 跳过 emit target 本身 — 跟旧实现行为一致
            # 但继续 recurse into body
            pass
        else:
            # [GAP-1 fix 2026-08-29] parent = hp 去掉最后一段 (与递归一致),
            # 不再信任调用方传下来的外层 parent (generate 场景会丢 generate 段)
            if is_array_element:
                # 数组元素: 递归 InstanceArray 分支 parent = child_path = 元素自身 hp
                parent = inst_id
            else:
                parent = inst_id[:inst_id.rfind(".")] if "." in inst_id else parent_module
            # Create wrapper
            wrapper = _NativeInstanceWrapper(
                _symbol=inst,
                type_name=type_name,
                parent_module=parent,
            )
            wrappers.append(wrapper)

        # Recurse into body
        body = getattr(inst, 'body', None)
        if body is None:
            return

        # Derive child parent_module
        # hierarchicalPath of inst is e.g. "top.gen_loop[0].u_sub"
        # Children are "top.gen_loop[0].u_sub.X"
        # So child parent_module = inst_id
        child_parent = inst_id

        for child in body:
            try:
                kind = str(child.kind)
            except (UnicodeDecodeError, TypeError):
                continue

            # [GAP-2 fix 2026-08-29] InstanceArray 分支必须在 'Instance' 检查**之前**:
            # 'SymbolKind.InstanceArray' 也含 'Instance' 子串, 原实现误匹配成普通实例
            if 'GenerateBlockArray' in kind:
                _walk_generate_block_array(child, child_parent, wrappers, root, target_module)
            elif 'GenerateBlock' in kind:
                _walk_generate_block(child, child_parent, wrappers, root, target_module)
            elif 'InstanceArray' in kind:
                _walk_instance_array(child, child_parent, wrappers, root, target_module)
            elif 'Instance' in kind:
                _walk_instance(child, child_parent, wrappers, root, target_module, is_top=False)
            # Skip ProceduralBlock, Variable, Parameter, etc.

    except (UnicodeDecodeError, TypeError):
        return


def _walk_instance_array(
    iarr, parent_module: str, wrappers: list, root: pyslang.RootSymbol,
    target_module: str | None = None,
) -> None:
    """[GAP-2 fix 2026-08-29] Walk InstanceArraySymbol — 每个元素是完整 InstanceSymbol.

    递归实现 (semantic_adapter.find_instances 的 InstanceArray 分支):
    - id = 元素 hierarchicalPath (如 'top.u_arr[0]')
    - parent = child_path (顶层数组 = 元素自身 hp)
    - type = definition.name (如 'sub')
    元素还有独立 portConnections / body, 需继续递归.
    """
    try:
        elements = getattr(iarr, 'elements', None)
        if elements is None:
            elements = list(iarr)
    except (UnicodeDecodeError, TypeError):
        return

    for elem in elements:
        try:
            kind = str(getattr(elem, 'kind', ''))
        except (UnicodeDecodeError, TypeError):
            continue
        if 'Instance' in kind:
            _walk_instance(elem, parent_module, wrappers, root, target_module,
                           is_top=False, is_array_element=True)


def _walk_generate_block_array(
    gba, parent_module: str, wrappers: list, root: pyslang.RootSymbol,
    target_module: str | None = None,
) -> None:
    """[Helper] Walk GenerateBlockArray — each entry is a GenerateBlock."""
    try:
        entries = getattr(gba, 'entries', None)
        if entries is None:
            # Fall back: iterate gba directly
            entries = list(gba)
    except (UnicodeDecodeError, TypeError):
        return

    for entry in entries:
        try:
            kind = str(getattr(entry, 'kind', ''))
        except (UnicodeDecodeError, TypeError):
            continue
        if 'GenerateBlock' in kind:
            _walk_generate_block(entry, parent_module, wrappers, root, target_module)


def _walk_generate_block(
    gb, parent_module: str, wrappers: list, root: pyslang.RootSymbol,
    target_module: str | None = None,
) -> None:
    """[Helper] Walk GenerateBlock — iterate for instance children."""
    try:
        for child in gb:
            try:
                kind = str(child.kind)
            except (UnicodeDecodeError, TypeError):
                continue
            # [GAP-2 fix 2026-08-29] generate 内也可能直接是 InstanceArray
            # (如 for 循环里 `sub u_arr[2]()`), 分支顺序同 _walk_instance
            if 'GenerateBlockArray' in kind:
                _walk_generate_block_array(child, parent_module, wrappers, root, target_module)
            elif 'GenerateBlock' in kind:
                _walk_generate_block(child, parent_module, wrappers, root, target_module)
            elif 'InstanceArray' in kind:
                _walk_instance_array(child, parent_module, wrappers, root, target_module)
            elif 'Instance' in kind:
                _walk_instance(child, parent_module, wrappers, root, target_module, is_top=False)
    except (UnicodeDecodeError, TypeError):
        return


# ----------------------------------------------------------------------------
# Wrapper class (compatible with SemanticInstanceWrapper API)
# ----------------------------------------------------------------------------

class _NativeInstanceWrapper:
    """[Phase 1] pyslang-based instance wrapper, API-compatible with SemanticInstanceWrapper.

    Attributes:
        _symbol: pyslang InstanceSymbol
        type: TypeToken-like object with .value attribute (module name)
        parent_module: str — full hierarchical path of parent instance
    """

    def __init__(self, _symbol, type_name: str | None, parent_module: str | None):
        self._symbol = _symbol
        self.parent_module = parent_module
        # TypeToken-like: must have .value attribute that's a string
        self.type = _TypeToken(type_name) if type_name else _TypeToken(None)

    @property
    def name(self) -> str | None:
        try:
            return _safe_str(self._symbol.name)
        except Exception:
            return None


class _TypeToken:
    """[Compat] TypeToken-like object with .value = module name string."""
    def __init__(self, value: str | None):
        self.value = value
    def __repr__(self):
        return f"_TypeToken({self.value!r})"
