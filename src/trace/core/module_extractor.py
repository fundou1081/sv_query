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

import logging
import re
from dataclasses import dataclass, field

from .._safe import _safe_attr, _safe_str
from .graph.models import EdgeKind, NodeKind, SignalGraph
from .semantic_adapter import SemanticAdapter

logger = logging.getLogger(__name__)


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
    array_index: int | None = None
    array_name: str | None = None
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
    instances: list[ModuleInstance] = field(default_factory=list)
    connections: list[PortConnection] = field(default_factory=list)
    external_ports: list[dict] = field(default_factory=list)


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
    raw_insts: list[tuple[str, str, str]] = []
    for nid in graph.nodes():
        n = graph.get_node(nid)
        if n is None:
            continue
        if n.kind != NodeKind.INSTANTIATED_MODULE:
            continue
        if any(ord(c) < 0x20 for c in nid if c not in '\n\t'):
            continue
        if n.module is None:
            continue
        if any(ord(c) < 0x20 for c in n.module if c not in '\n\t'):
            continue
        raw_insts.append((nid, n.name or "", n.module))

    # Group by top-level module
    by_top: dict[str, list[tuple[str, str, str]]] = {}
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
        # [iter_185] 不静默: 目标模块不在语义树中 = 调用方拿不到任何实例, 必须
        # 可见。此前静默返回空 → benchmark 只报 instance_count=0, 掩盖了
        # SourceManager 生命周期 bug 造成的乱码名/"找不到模块" (iter_185)。
        logger.warning(
            "extract_module: 目标模块 '%s' 不在语义树中 (语义树模块数 %d) — 返回空提取",
            target_module, len(adapter.get_modules()),
        )
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

    for _sub_inst, inst_name, def_name, array_idx, array_name in _iter_sub_instances(adapter, parent_mod):
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


def _iter_sub_instances(adapter, parent_mod) -> list[tuple]:
    results: list[tuple] = []

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


def _collect_instances_from_stmt(adapter, stmt) -> list[tuple]:
    results = []
    kind_str = _safe_str(_safe_attr(stmt, "kind", ""))
    if "Instance" in kind_str:
        # 跳过 InstanceBody (是 module 自己的 body, 不是 child instance)
        if "InstanceBody" in kind_str:
            return results
        name = _safe_str(_safe_attr(stmt, "name", ""))
        defn = _safe_attr(stmt, "definition", None)
        def_name = _safe_str(_safe_attr(defn, "name", "")) if defn else ""
        # [PR1 2026-06-14] 如果没 def (InstanceArray), 尝试从 elements[0].definition 获取
        if not def_name:
            elements = _safe_attr(stmt, "elements", None)
            if elements and len(elements) > 0:
                first = elements[0]
                if first is not None:
                    defn2 = _safe_attr(first, "definition", None)
                    if defn2 is not None:
                        def_name = _safe_str(_safe_attr(defn2, "name", ""))
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
            except TypeError as e:
                # body 不可迭代, 尝试 child 属性
                logger.debug("%s: 忽略 TypeError: %s", __name__, e)
    return results


def _find_generate_block(adapter, stmt):
    kind_str = _safe_str(_safe_attr(stmt, "kind", ""))
    if "Generate" in kind_str:
        return stmt
    return None


def _iter_generate_body(adapter, gen_block) -> list[tuple]:
    results = []
    for child in getattr(gen_block, "body", []):
        results.extend(_collect_instances_from_stmt(adapter, child))
    return results


# ---------------------------------------------------------------------------
# Truncate instance names for display
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# [PR4 2026-06-15] L2 cross-instance port connections from MIG
# ---------------------------------------------------------------------------

# 跟 L1/L3 一样, 过滤 binary garbage
_PORT_BIN_PATTERNS = ('', '<id:binary>', '_anon_', '_bad_', '_bin_')


def _is_clean_id(s: str | None) -> bool:
    """[PR4] 检查 id 是否不含 binary garbage."""
    if not s:
        return False
    n = str(s).strip()
    if not n:
        return False
    if n in _PORT_BIN_PATTERNS:
        return False
    # 带 \x00 或控制字符的也是 garbage
    if any(ord(c) < 0x20 and c not in '\n\t' for c in n):
        return False
    return True


def extract_module_edges_from_graph(
    graph,
    instances: list[ModuleInstance],
    max_edges: int = 500,
) -> list[dict]:
    """[iter_283 / PLAN P1.1] 从**实例级 SignalGraph** 推 instance-to-instance 边。

    取代 `extract_module_edges_from_mig`（按 MIG 的 `inst_port → module_type.port`
    分组——同模块类型同名端口就算相连，是双命名空间时代的启发式，多实例会误连）。

    新判据（纯实例级，全部来自图）：
      1. **直接边**：图中两端归属**不同实例**的 CONNECTION/DRIVER 边
      2. **经过父级网络**：两端分别连着同一个网络节点（owner 不在 in-scope 实例内，
         如 top 层 wire/port）的两个实例端点 → 该网络连接这两个实例

    Returns:
        [{src, dst, src_instance, dst_instance, internal, port, port_src,
          port_dst, width}]；`internal` = 网络/端口节点 id。
    """
    if graph is None or not instances:
        return []

    inst_ids = {inst.id for inst in instances}
    if not inst_ids:
        return []

    def owner(node_id: str) -> str | None:
        """节点 → 所属实例（最长前缀匹配；generate 路径也能命中）。"""
        parts = node_id.split(".")
        for i in range(len(parts) - 1, 0, -1):
            cand = ".".join(parts[:i])
            if cand in inst_ids:
                return cand
        return None

    def width_of(node_id: str) -> int | None:
        node = graph.get_node(node_id)
        w = getattr(node, "width", None)
        if isinstance(w, (tuple, list)) and len(w) >= 2:
            try:
                return abs(int(w[0]) - int(w[1])) + 1
            except (TypeError, ValueError):
                return None
        return None

    def port_of(node_id: str) -> str:
        return node_id.rsplit(".", 1)[-1]

    # 预计算 owner（节点数有限，一次遍历）
    owner_of: dict[str, str | None] = {}
    for node_id in graph.nodes():
        owner_of[node_id] = owner(node_id)

    edges: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(a_inst: str, b_inst: str, net: str, a_port: str, b_port: str, width_id: str) -> bool:
        if a_inst == b_inst:
            return False
        key = (a_inst, b_inst, a_port, b_port)
        if key in seen:
            return False
        seen.add(key)
        edges.append({
            "src": a_inst,
            "dst": b_inst,
            "src_instance": a_inst,
            "dst_instance": b_inst,
            "internal": net,
            "port": a_port,
            "port_src": a_port,
            "port_dst": b_port,
            "width": width_of(width_id),
        })
        return True

    # ---- 1. 直接跨实例边 ----
    for (u, v), trace_edges in graph._edge_data.items():
        if u == v:
            continue
        if not any(e.kind in (EdgeKind.CONNECTION, EdgeKind.DRIVER) for e in trace_edges):
            continue
        ou, ov = owner_of.get(u), owner_of.get(v)
        if ou and ov and ou != ov:
            add(ou, ov, u, port_of(u), port_of(v), v)
            if len(edges) >= max_edges:
                break

    # ---- 2. 经过父级网络（net 的端点都是实例端口）----
    # 每个网络最多贡献 4 对（与旧 MIG 启发式上限一致）：时钟/复位这类广播网络
    # 连着 N 个实例，全展开是 N² 条边，对架构视图是噪声。
    MAX_PAIRS_PER_NET = 4
    if len(edges) < max_edges:
        net_endpoints: dict[str, list[tuple[str, str]]] = {}
        for (u, v), trace_edges in graph._edge_data.items():
            if not any(e.kind in (EdgeKind.CONNECTION, EdgeKind.DRIVER) for e in trace_edges):
                continue
            def is_net(node_id: str) -> bool:
                """父级网络节点；字面量常量（0 / 1'b0）不是网络，不能当连线。"""
                n = graph.get_node(node_id)
                return n is not None and n.kind != NodeKind.CONST

            ou, ov = owner_of.get(u), owner_of.get(v)
            if ou and not ov and is_net(v):
                net_endpoints.setdefault(v, []).append((ou, u))
            elif ov and not ou and is_net(u):
                net_endpoints.setdefault(u, []).append((ov, v))

        for net, endpoints in net_endpoints.items():
            if len({inst for inst, _ in endpoints}) < 2:
                continue
            # 按实例去重（同一实例同一网络只取一个端口）
            uniq: dict[str, str] = {}
            for inst, port_node in endpoints:
                uniq.setdefault(inst, port_node)
            items = sorted(uniq.items())
            pairs_added = 0
            for i in range(len(items) - 1):
                for j in range(i + 1, len(items)):
                    a_inst, a_node = items[i]
                    b_inst, b_node = items[j]
                    if add(a_inst, b_inst, net, port_of(a_node), port_of(b_node), b_node):
                        pairs_added += 1
                    if pairs_added >= MAX_PAIRS_PER_NET or len(edges) >= max_edges:
                        break
                if pairs_added >= MAX_PAIRS_PER_NET or len(edges) >= max_edges:
                    break
            if len(edges) >= max_edges:
                break

    edges.sort(key=lambda e: (e["src"], e["dst"], e["port_src"], e["port_dst"]))
    return edges


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
