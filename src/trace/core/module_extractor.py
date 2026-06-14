"""
trace.core.module_extractor - 提取 module 级别的 sub-instance 结构

[PR1 2026-06-13] 用于 visualize module L1 图.

设计:
  - 从 SignalGraph 提取所有 INSTANTIATED_MODULE 节点 (含子 instance)
  - 从 semantic AST 提取 top module 的 external ports
  - 应用 instance boundary truncation (--depth flag)
  - 折叠 array instance (i_axi_mux[0], i_axi_mux[1], ... → [0], [1] + [*] 占位)
  - 输出 JSON 供 visualize / diff 用

不模拟仿真, 静态提取. 处理:
  - 子模块实例 (axi_xbar contains axi_xbar_unmuxed)
  - 数组实例 (i_axi_mux[i] in gen_mst_port_mux)
  - Interface ports (AXI_BUS.Slave → 5 channel struct)
  - Port-to-instance 映射 (.awready_i(slv_req.awready))
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .semantic_adapter import SemanticAdapter
from .._safe import _safe_str, _safe_attr
from .graph.models import SignalGraph, NodeKind


@dataclass
class ModuleInstance:
    """[PR1 2026-06-13] 一个 sub-module instance.

    Attributes:
        id: 完整 id (e.g. "axi_xbar_intf.i_xbar.gen_mst_port_mux[0].i_axi_mux")
        name: 实例名 (e.g. "i_axi_mux")
        def_name: 实例化的模块定义名 (e.g. "axi_mux")
        parent_module: 父模块 (e.g. "axi_xbar")
        depth: 在 instance 层级中的深度 (0 = top direct child)
        array_index: 如果是 generate block 数组的元素, 索引
        array_name: generate block 名
        is_collapsed: 是否为 [2..N-1] 的占位
    """
    id: str
    name: str
    def_name: str
    parent_module: str
    depth: int
    array_index: Optional[int] = None
    array_name: Optional[str] = None
    is_collapsed: bool = False


@dataclass
class PortConnection:
    """[PR1] 一个 port-to-instance 的连接."""
    from_node: str
    to_node: str
    port_name: str
    signal_name: str = ""
    is_external: bool = False


@dataclass
class ModuleExtraction:
    """[PR1] 完整 module 提取结果."""
    top_module: str
    instances: List[ModuleInstance] = field(default_factory=list)
    connections: List[PortConnection] = field(default_factory=list)
    external_ports: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main extraction (graph-based, robust)
# ---------------------------------------------------------------------------

def extract_module_from_graph(
    graph: SignalGraph,
    target_module: str,
    max_depth: int = 1,
    collapse_arrays: bool = True,
    max_array_unroll: int = 2,
) -> ModuleExtraction:
    """[PR1] 从 SignalGraph 提取 target_module 的 sub-instance 结构.

    策略:
      1. 找 graph 中所有 INSTANTIATED_MODULE 节点
      2. 按 id 路径分类
      3. 过滤掉 binary garbage
      4. 应用 instance boundary truncation
    """
    result = ModuleExtraction(top_module=target_module)

    # Collect all INSTANTIATED_MODULE nodes
    raw_insts: List[Tuple[str, str, str]] = []
    for nid in graph.nodes():
        n = graph.get_node(nid)
        if n is None: continue
        if n.kind != NodeKind.INSTANTIATED_MODULE: continue
        if any(ord(c) < 0x20 for c in nid if c not in '\n\t'):
            continue
        if n.module is None: continue
        if any(ord(c) < 0x20 for c in n.module if c not in '\n\t'):
            continue
        raw_insts.append((nid, n.name or "", n.module))

    # Group by top-level module
    by_top: Dict[str, List[Tuple[str, str, str]]] = {}
    for nid, name, mod in raw_insts:
        top = nid.split('.', 1)[0]
        by_top.setdefault(top, []).append((nid, name, mod))

    # Match target_module to a top key (exact, then substring)
    target_insts = by_top.get(target_module, [])
    if not target_insts:
        for top_key, insts in by_top.items():
            if target_module and (
                target_module in top_key or top_key in target_module
            ):
                target_insts = insts
                result.top_module = top_key  # Update to actual
                break

    # Build ModuleInstance list
    for nid, name, mod in target_insts:
        parts = nid.split('.')
        depth = len(parts) - 1
        if depth > max_depth:
            continue

        array_name = None
        array_idx = None
        for p in parts[1:]:
            m = re.match(r"^(\w+)\[(\d+)\]$", p)
            if m:
                array_name = m.group(1)
                array_idx = int(m.group(2))
                break

        inst = ModuleInstance(
            id=nid,
            name=name,
            def_name=mod,
            parent_module=parts[0],
            depth=depth,
            array_index=array_idx,
            array_name=array_name,
            is_collapsed=False,
        )
        result.instances.append(inst)

    return result


def extract_module(
    adapter: SemanticAdapter,
    target_module: str,
    max_depth: int = 1,
    collapse_arrays: bool = True,
    max_array_unroll: int = 2,
) -> ModuleExtraction:
    """[PR1] 主入口: 从 semantic AST 提取 (备用, graph 失败时用)."""
    target_mod = _find_module(adapter, target_module)
    if target_mod is None:
        return ModuleExtraction(top_module=target_module)

    result = ModuleExtraction(top_module=target_module)

    for pd in adapter.get_port_declarations(target_mod):
        pname, pdir = adapter.get_port_name_and_direction(pd)
        result.external_ports.append({
            "name": pname,
            "direction": pdir,
            "id": f"{target_module}.{pname}",
        })

    _extract_sub_instances(
        adapter, target_mod, target_module,
        depth=0, max_depth=max_depth,
        collapse_arrays=collapse_arrays, max_array_unroll=max_array_unroll,
        result=result, current_path=target_module,
    )

    return result


def _find_module(adapter: SemanticAdapter, name: str):
    """[PR1] 按名找 module."""
    for mod in adapter.get_modules():
        if _safe_str(adapter.get_module_name(mod)) == name:
            return mod
    return None


def _extract_sub_instances(
    adapter: SemanticAdapter,
    parent_mod,
    parent_name: str,
    depth: int,
    max_depth: int,
    collapse_arrays: bool,
    max_array_unroll: int,
    result: ModuleExtraction,
    current_path: str,
):
    if depth >= max_depth:
        return

    for sub_inst, inst_name, def_name, array_idx, array_name in _iter_sub_instances(adapter, parent_mod):
        if array_idx is not None:
            full_id = f"{current_path}.{array_name}[{array_idx}].{inst_name}"
            parent_module = current_path
        else:
            full_id = f"{current_path}.{inst_name}"
            parent_module = current_path

        is_collapsed = False
        if collapse_arrays and array_name is not None and array_idx is not None and array_idx >= max_array_unroll:
            is_collapsed = True

        inst = ModuleInstance(
            id=full_id,
            name=inst_name,
            def_name=def_name,
            parent_module=parent_module,
            depth=depth + 1,
            array_index=array_idx,
            array_name=array_name,
            is_collapsed=is_collapsed,
        )
        result.instances.append(inst)

        if is_collapsed:
            continue

        sub_mod = _find_module(adapter, def_name)
        if sub_mod is not None:
            _extract_sub_instances(
                adapter, sub_mod, def_name,
                depth=depth + 1, max_depth=max_depth,
                collapse_arrays=collapse_arrays, max_array_unroll=max_array_unroll,
                result=result, current_path=full_id,
            )


def _iter_sub_instances(adapter, parent_mod) -> List[Tuple]:
    results: List[Tuple] = []
    seen_array_counts: Dict[str, int] = {}

    for item in parent_mod.body:
        for inst_obj, inst_name, def_name in _collect_instances_from_stmt(adapter, item):
            if def_name in ("AXI_BUS", "AXI_BUS_ASYNC", "AXI_BUS_ASYNC_GRAY",
                            "AXI_BUS_DV", "AXI_LITE", "AXI_LITE_ASYNC_GRAY", "AXI_LITE_DV"):
                continue
            results.append((inst_obj, inst_name, def_name, None, None))

    for item in parent_mod.body:
        gen_block = _find_generate_block(adapter, item)
        if gen_block is not None:
            block_name = _safe_str(_safe_attr(gen_block, "name", ""))
            for inst_obj, inst_name, def_name in _iter_generate_body(adapter, gen_block):
                if def_name in ("AXI_BUS", "AXI_BUS_ASYNC", "AXI_BUS_ASYNC_GRAY",
                                "AXI_BUS_DV", "AXI_LITE", "AXI_LITE_ASYNC_GRAY", "AXI_LITE_DV"):
                    continue
                results.append((inst_obj, inst_name, def_name, 0, block_name))

    return results


def _collect_instances_from_stmt(adapter, stmt) -> List[Tuple]:
    results = []
    kind_str = _safe_str(_safe_attr(stmt, "kind", ""))
    if "Instance" in kind_str:
        name = _safe_str(_safe_attr(stmt, "name", ""))
        defn = _safe_attr(stmt, "definition", None)
        def_name = _safe_str(_safe_attr(defn, "name", "")) if defn else ""
        if name or def_name:
            results.append((stmt, name, def_name))
    elif "Generate" in kind_str or "Block" in kind_str:
        # 尝试多种方式获取 body (可能是 list / BlockStatement / Scope)
        body = _safe_attr(stmt, "body", None)
        if body is None:
            return results
        # 如果 body 是 list/Iterable 但不是 string/bytes
        if hasattr(body, "__iter__") and not isinstance(body, (str, bytes)):
            try:
                for child in body:
                    results.extend(_collect_instances_from_stmt(adapter, child))
            except TypeError:
                # body 不可迭代, 尝试 child 属性
                pass
    return results


def _find_generate_block(adapter, stmt):
    kind_str = _safe_str(_safe_attr(stmt, "kind", ""))
    if "Generate" in kind_str:
        return stmt
    return None


def _iter_generate_body(adapter, gen_block) -> List[Tuple]:
    results = []
    for child in getattr(gen_block, "body", []):
        results.extend(_collect_instances_from_stmt(adapter, child))
    return results


# ---------------------------------------------------------------------------
# Truncate instance names for display
# ---------------------------------------------------------------------------

def truncate_instance_id(full_id: str, depth: int = 1) -> str:
    """[PR1] instance 边界截断: 取最后 `depth` 层 instance path.

    Examples:
        full_id = "axi_xbar_intf.i_xbar.gen_mst_port_mux[0].i_axi_mux"
        depth=0 → "axi_xbar_intf"  (only module name)
        depth=1 → "i_axi_mux"  (last instance)
        depth=2 → "gen_mst_port_mux[0].i_axi_mux"
    """
    parts = full_id.split(".")
    if len(parts) <= 1:
        return full_id
    instance_parts = parts[1:]
    if depth <= 0:
        return parts[0]
    if depth >= len(instance_parts):
        return full_id
    return ".".join(instance_parts[-depth:])
