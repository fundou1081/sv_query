"""Module/instance-level RTL architecture graph.

Built from real instance ports + CONNECTION edges (MIG), not from guessed
module boxes and not from the full signal graph.  Nodes are instances; edges
are parent nets connecting instance ports.  This is intentionally a
module-level view: it does not attempt to draw every internal signal.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ArchNode:
    id: str
    module: str
    parent: str | None
    depth: int
    ports: int = 0


@dataclass
class ArchEdge:
    src: str
    dst: str
    net: str
    src_port: str
    dst_port: str
    src_direction: str
    dst_direction: str


@dataclass
class Architecture:
    nodes: list[ArchNode] = field(default_factory=list)
    edges: list[ArchEdge] = field(default_factory=list)
    boundaries: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


def _depth(path: str, root: str | None) -> int:
    if root and path.startswith(root + "."):
        return path[len(root) + 1:].count(".") + 1
    return path.count(".")


def _owner(node_id: str, owners: list[str], port_sets: dict[str, set[str]]):
    for inst in owners:
        prefix = inst + "."
        if node_id.startswith(prefix):
            port = node_id[len(prefix):]
            if "." not in port and port in port_sets.get(inst, set()):
                return inst, port
    return None


def _select_instances(tracer, root: str | None, max_depth: int | None,
                      include_primitives: bool) -> list:
    selected = []
    for inst in tracer.get_instances():
        path = inst.full_path
        if root and not (path == root or path.startswith(root + ".")):
            continue
        if max_depth is not None and _depth(path, root) > max_depth:
            continue
        if not include_primitives and str(inst.module_type).startswith("prim_"):
            continue
        selected.append(inst)
    return selected


def _port_metadata(mig, selected: list) -> tuple[dict[str, set[str]],
                                                  dict[tuple[str, str], str]]:
    port_sets: dict[str, set[str]] = {}
    port_dirs: dict[tuple[str, str], str] = {}
    for inst in selected:
        node = mig.get_instance(inst.full_path) if mig is not None else None
        ports = list(getattr(node, "ports", {}).values()) if node is not None else []
        port_sets[inst.full_path] = {p.name for p in ports}
        for p in ports:
            port_dirs[(inst.full_path, p.name)] = p.direction
    return port_sets, port_dirs


def _classify_connection(s: str, d: str, owners: list[str],
                         port_sets: dict) -> list[tuple[str, tuple[str, str]]]:
    so = _owner(s, owners, port_sets)
    do = _owner(d, owners, port_sets)
    if so and not do:
        return [(d, so)]
    if do and not so:
        return [(s, do)]
    if so and do and so[0] != do[0]:
        net = f"{s}->{d}"
        return [(net, so), (net, do)]
    return []


def _collect_attachments(graph, owners: list[str], port_sets: dict,
                         port_dirs: dict) -> dict[str, list[tuple[str, str, str]]]:
    attachments: dict[str, list[tuple[str, str, str]]] = {}
    for s, d in graph.edges():
        for e in graph.get_edges(s, d):
            if e.kind.name != "CONNECTION":
                continue
            for net, owner in _classify_connection(s, d, owners, port_sets):
                attachments.setdefault(net, []).append(
                    (owner[0], owner[1], port_dirs.get(owner, "")))
    return attachments

def _edge_for_pair(net: str, ports: list[tuple[str, str, str]],
                   i: int, port_dirs: dict) -> ArchEdge | None:
    src, sp, sd = ports[i]
    for dst, dp, dd in ports[i + 1:]:
        if src == dst:
            continue
        if sd == "output" and dd == "input":
            a, b, ap, bp = src, dst, sp, dp
        elif sd == "input" and dd == "output":
            a, b, ap, bp = dst, src, dp, sp
        else:
            a, b, ap, bp = src, dst, sp, dp
        return ArchEdge(a, b, net, ap, bp,
                        port_dirs.get((a, ap), ""),
                        port_dirs.get((b, bp), ""))
    return None


def _edges_from_attachments(attachments: dict, port_dirs: dict):
    edges: list[ArchEdge] = []
    boundaries: list[dict] = []
    for net, ports in sorted(attachments.items()):
        if len(ports) == 1:
            inst, port, direction = ports[0]
            boundaries.append({"net": net, "instance": inst, "port": port,
                               "direction": direction})
            continue
        for i in range(len(ports)):
            edge = _edge_for_pair(net, ports, i, port_dirs)
            if edge is not None:
                edges.append(edge)
    return edges, boundaries


def build_architecture(tracer, root: str | None = None,
                       max_depth: int | None = None,
                       include_primitives: bool = True) -> Architecture:
    graph = tracer.build_graph()
    selected = _select_instances(tracer, root, max_depth, include_primitives)
    port_sets, port_dirs = _port_metadata(tracer.get_module_graph(), selected)
    owners = sorted({i.full_path for i in selected}, key=len, reverse=True)
    attachments = _collect_attachments(graph, owners, port_sets, port_dirs)
    edges, boundaries = _edges_from_attachments(attachments, port_dirs)
    nodes = [ArchNode(i.full_path, i.module_type, i.parent,
                      _depth(i.full_path, root), len(port_sets.get(i.full_path, ())))
             for i in selected]
    nodes.sort(key=lambda n: (n.depth, n.id))
    stats = {"instances": len(nodes), "connections": len(edges),
             "boundaries": len(boundaries)}
    return Architecture(nodes=nodes, edges=edges, boundaries=boundaries,
                        stats=stats)

def _esc(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace('"', '\\"')


def _is_clock_reset(net: str) -> bool:
    leaf = str(net).rsplit(".", 1)[-1].lower()
    return (leaf.startswith("clk") or leaf.startswith("rst")
            or leaf in {"reset", "resetn", "reset_n", "scan_en", "scanmode"})


def to_dot(arch: Architecture, rankdir: str = "LR",
           include_boundaries: bool = False,
           include_clock_reset: bool = False) -> str:
    """Render an Architecture as Graphviz DOT (module/instance level)."""
    lines = [f'digraph architecture {{', f'  rankdir={rankdir};',
             '  node [shape=box, style="rounded", fontname="monospace", fontsize=10];',
             '  edge [fontname="monospace", fontsize=8];']
    for node in arch.nodes:
        label = _esc(node.id) + "\\n" + _esc(node.module)
        lines.append(f'  "{_esc(node.id)}" [label="{label}"];')
    for edge in arch.edges:
        if not include_clock_reset and _is_clock_reset(edge.net):
            continue
        label = _esc(edge.net) + "\\n" + _esc(edge.src_port) + " -> " + _esc(edge.dst_port)
        arrow = "both" if edge.src_direction == edge.dst_direction == "inout" else "forward"
        lines.append(
            f'  "{_esc(edge.src)}" -> "{_esc(edge.dst)}" '
            f'[label="{label}", dir={arrow}];')
    if include_boundaries:
        for b in arch.boundaries:
            nid = f"__boundary__{b['net']}"
            lines.append(f'  "{_esc(nid)}" [label="{_esc(b["net"])}", shape=ellipse];')
            # external net attaches to the instance port; no dataflow direction
            lines.append(f'  "{_esc(nid)}" -> "{_esc(b["instance"])}" '
                         f'[label="{_esc(b["port"])}", dir=none];')
    lines.append("}")
    return "\n".join(lines) + "\n"
