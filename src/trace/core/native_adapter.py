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
from typing import List, Optional


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _safe_str(value) -> Optional[str]:
    """[Bug-resistant] 跟 sv_query 一样 handle UnicodeDecodeError / binary garbage."""
    if value is None:
        return None
    try:
        s = str(value)
        if not s or s == "<id:binary>":
            return None
        return s
    except (UnicodeDecodeError, TypeError, Exception):
        return None


def _safe_hierarchical_path(symbol) -> Optional[str]:
    """Get hierarchicalPath, safely."""
    try:
        hp = symbol.hierarchicalPath
        return _safe_str(hp)
    except (UnicodeDecodeError, TypeError, Exception):
        return None


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def get_module_instances_native(
    root: pyslang.RootSymbol,
    target_module: Optional[str] = None,
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
    2. 递归 walk InstanceSymbol.body, 跳过 utility cells
    3. 处理 GenerateBlockArray + GenerateBlock
    4. 跳过 ProceduralBlock / Variable / Parameter (跟旧实现一致)
    """
    wrappers = []
    if root is None:
        return wrappers

    # 找 start point — user target or first user top
    top_to_walk = _find_target_top(root, target_module)
    if top_to_walk is None:
        # Fall back: walk all top instances
        for top in root.topInstances:
            if _is_user_module(top):
                _walk_instance(top, target_module or top.name, wrappers, root, target_module, is_top=True)
    else:
        _walk_instance(top_to_walk, target_module, wrappers, root, target_module, is_top=True)

    return wrappers


def _find_target_top(root: pyslang.RootSymbol, target_module: Optional[str]):
    """[Helper] 找 user-specified target 在 topInstances 里."""
    if target_module is None:
        # 没指定 — 返第一个 user module top instance
        for top in root.topInstances:
            if _is_user_module(top):
                return top
        return None
    # 指定了 — 找同名 top
    for top in root.topInstances:
        try:
            if top.name == target_module:
                return top
        except (UnicodeDecodeError, TypeError, Exception):
            continue
    return None


def _is_user_module(top) -> bool:
    """[Helper] 判 top instance 是不是 user module (vs utility cell).

    Utility cell examples (CVA6): cluster_clock_*, fifo, lfsr_8bit, rrarbiter, etc.
    这些是 vendored libraries 暴露的, 跟 user DUT hierarchy 无关.

    Heuristic: 检查 top instance 的 definition — 如果 definition 在 user source 里,
    是 user module. 否则 utility cell. 但 sv_query 没 filelist 跟 definition 的 mapping.
    """
    # 简化: top instance body 里有 user-named module instance → user module
    # Utility cells 通常是 leaf (没 sub-instances) 或只有 std cells
    try:
        body = getattr(top, 'body', None)
        if body is None:
            return False
        for child in body:
            try:
                kind = str(child.kind)
                if 'Instance' in kind:
                    return True
            except (UnicodeDecodeError, TypeError, Exception):
                continue
    except Exception:
        return False
    return False


def _walk_instance(
    inst,
    parent_module: str,
    wrappers: list,
    root: pyslang.RootSymbol,
    target_module: Optional[str] = None,
    is_top: bool = False,
) -> None:
    """[Helper] 递归 walk InstanceSymbol, 处理 generate blocks.

    Mirrors semantic_adapter.get_module_instances() output:
    - 每个 instance wrapper: {_symbol, type, parent_module, ...}
    - type is TypeToken-like with .value
    - top-level target 本身不被 emit (跟旧实现一致 — 只 emit sub-instances)
    """
    try:
        inst_id = _safe_hierarchical_path(inst)
        if not inst_id:
            return
        try:
            inst_name = _safe_str(inst.name)
        except (UnicodeDecodeError, TypeError, Exception):
            inst_name = None

        # Get type name (module name) via definition
        defn = getattr(inst, 'definition', None)
        type_name = None
        if defn is not None:
            try:
                type_name = _safe_str(defn.name)
            except (UnicodeDecodeError, TypeError, Exception):
                type_name = None

        # 跟旧实现一致: top-level target 本身不被 emit
        # 旧实现: 如果 node.kind 是 Instance, parent_path 是空 (即顶层), 且
        # hierarchicalPath 是 target module 名字本身 (不含 '.'), 跳过 emit
        if is_top and inst_id == target_module:
            # 跳过 emit target 本身 — 跟旧实现行为一致
            # 但继续 recurse into body
            pass
        else:
            # Create wrapper
            wrapper = _NativeInstanceWrapper(
                _symbol=inst,
                type_name=type_name,
                parent_module=parent_module,
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
            except (UnicodeDecodeError, TypeError, Exception):
                continue

            if 'Instance' in kind:
                _walk_instance(child, child_parent, wrappers, root, target_module, is_top=False)
            elif 'GenerateBlockArray' in kind:
                _walk_generate_block_array(child, child_parent, wrappers, root, target_module)
            elif 'GenerateBlock' in kind:
                _walk_generate_block(child, child_parent, wrappers, root, target_module)
            # Skip ProceduralBlock, Variable, Parameter, etc.

    except (UnicodeDecodeError, TypeError, Exception):
        return


def _walk_generate_block_array(
    gba, parent_module: str, wrappers: list, root: pyslang.RootSymbol,
    target_module: Optional[str] = None,
) -> None:
    """[Helper] Walk GenerateBlockArray — each entry is a GenerateBlock."""
    try:
        entries = getattr(gba, 'entries', None)
        if entries is None:
            # Fall back: iterate gba directly
            entries = list(gba)
    except (UnicodeDecodeError, TypeError, Exception):
        return

    for entry in entries:
        try:
            kind = str(getattr(entry, 'kind', ''))
        except (UnicodeDecodeError, TypeError, Exception):
            continue
        if 'GenerateBlock' in kind:
            _walk_generate_block(entry, parent_module, wrappers, root, target_module)


def _walk_generate_block(
    gb, parent_module: str, wrappers: list, root: pyslang.RootSymbol,
    target_module: Optional[str] = None,
) -> None:
    """[Helper] Walk GenerateBlock — iterate for instance children."""
    try:
        for child in gb:
            try:
                kind = str(child.kind)
            except (UnicodeDecodeError, TypeError, Exception):
                continue
            if 'Instance' in kind:
                _walk_instance(child, parent_module, wrappers, root, target_module, is_top=False)
            elif 'GenerateBlockArray' in kind:
                _walk_generate_block_array(child, parent_module, wrappers, root, target_module)
            elif 'GenerateBlock' in kind:
                _walk_generate_block(child, parent_module, wrappers, root, target_module)
    except (UnicodeDecodeError, TypeError, Exception):
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

    def __init__(self, _symbol, type_name: Optional[str], parent_module: Optional[str]):
        self._symbol = _symbol
        self.parent_module = parent_module
        # TypeToken-like: must have .value attribute that's a string
        self.type = _TypeToken(type_name) if type_name else _TypeToken(None)

    @property
    def name(self) -> Optional[str]:
        try:
            return _safe_str(self._symbol.name)
        except Exception:
            return None


class _TypeToken:
    """[Compat] TypeToken-like object with .value = module name string."""
    def __init__(self, value: Optional[str]):
        self.value = value
    def __repr__(self):
        return f"_TypeToken({self.value!r})"
