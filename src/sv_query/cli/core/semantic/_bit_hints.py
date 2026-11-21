"""[P191.1] Additive bit-select discoverability hints.

Truth layer unchanged: a bus query answers the bus node. These helpers only
produce optional road signs pointing at descendant bit-select nodes.
"""
from __future__ import annotations


def split_bit_range(node_id: str, bus_id: str) -> dict[str, str] | None:
    """Return {msb, lsb} for a direct ``bus_id[...]`` descendant."""
    prefix = bus_id + "["
    if not node_id.startswith(prefix) or not node_id.endswith("]"):
        return None
    inner = node_id[len(prefix):-1]
    if not inner:
        return None
    if ":" in inner:
        msb, lsb = inner.split(":", 1)
    else:
        msb = lsb = inner
    return {"msb": msb, "lsb": lsb}


def descendant_bit_nodes(graph, bus_id: str) -> list[dict]:
    """List direct bit-select nodes for a bus, with parent/range metadata."""
    if bus_id.endswith("]"):
        return []
    rows = []
    for node_id in graph.nodes():
        bit_range = split_bit_range(str(node_id), bus_id)
        if bit_range is None:
            continue
        rows.append({
            "id": str(node_id),
            "parent_bus": bus_id,
            "bit_range": bit_range,
        })
    return sorted(rows, key=lambda row: row["id"])


def bit_hint_payload(graph, bus_id: str, direction: str) -> dict:
    """Return additive hints for drivers/loads at the bus node."""
    nodes = descendant_bit_nodes(graph, bus_id)
    if direction == "drivers":
        has_bits = any(graph.in_degree(row["id"]) > 0 for row in nodes)
        key = "has_bit_select_drivers"
    elif direction == "loads":
        has_bits = any(graph.out_degree(row["id"]) > 0 for row in nodes)
        key = "has_bit_select_loads"
    else:
        raise ValueError(f"direction must be drivers or loads, got {direction!r}")
    payload: dict = {key: has_bits}
    if nodes:
        payload["bit_nodes"] = nodes
    return payload


def dataflow_bit_paths(dfg, graph, from_id: str, to_id: str,
                       *, max_expansions: int = 200_000) -> dict:
    """Return additive dataflow hints when a bus endpoint has bit paths."""
    rows = []
    for bit in descendant_bit_nodes(graph, from_id):
        if graph.out_degree(bit["id"]) == 0:
            continue
        try:
            result = dfg.analyze(
                bit["id"], to_id, max_paths=1,
                max_expansions=max_expansions,
            )
        except ValueError:
            continue
        if result.is_reachable is True and result.paths_count > 0:
            rows.append({"from": bit["id"], "path_count": result.paths_count})
    if not rows:
        return {}
    return {"bit_node_paths_exist": True, "bit_node_paths": rows}
