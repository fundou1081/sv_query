#!/usr/bin/env python3
"""[P186.1] Measure module-definition shadow nodes by fixture/module/query surface."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sv_query.trace.core.graph.models import NodeKind  # noqa: E402
from sv_query.trace.unified_tracer import UnifiedTracer  # noqa: E402

DEFAULT_FIXTURES = (
    "sim/tests/fixtures/minimal_3module/filelist.f",
    "sim/tests/fixtures/scheduler_minimal/filelist.f",
    "sim/tests/fixtures/golden_mini/filelist.f",
    "sim/tests/fixtures/generate_forms/filelist.f",
    "sim/tests/fixtures/wrapper_chain/filelist.f",
)


def instance_prefixes(tracer) -> list[str]:
    tops = [str(t) for t in tracer.list_top_modules()]
    children = [i.full_path for i in tracer.get_instances()]
    return sorted(set(tops + children), key=len, reverse=True)


def _under_instance(node_id: str, prefixes: list[str]) -> bool:
    return any(node_id == p or node_id.startswith(p + ".") for p in prefixes)


def classify_shadow(tracer, graph) -> tuple[list[str], list[str]]:
    prefixes = instance_prefixes(tracer)
    shadow, constants = [], []
    for node_id in graph.nodes():
        node = graph.get_node(node_id)
        if node is None:
            continue
        if node.kind == NodeKind.CONST or node_id in {"0", "1"}:
            constants.append(node_id)
        elif not _under_instance(node_id, prefixes):
            shadow.append(node_id)
    return sorted(shadow), constants


def measure_graph(tracer, graph) -> dict:
    prefixes = instance_prefixes(tracer)
    shadow, constants = classify_shadow(tracer, graph)
    shadow_set = set(shadow)
    edges = list(graph.edges())
    shadow_edges = sum(1 for u, v in edges if u in shadow_set and v in shadow_set)
    cross_edges = sum(1 for u, v in edges if (u in shadow_set) != (v in shadow_set))
    isolated = sum(1 for n in shadow if graph.degree(n) == 0)

    # Top-level input ports are the observable dataflow sources.
    sources = [
        n for n in graph.nodes()
        if graph.get_node(n) is not None
        and graph.get_node(n).kind == NodeKind.PORT_IN
        and any(n == p or n.startswith(p + ".") for p in prefixes)
        and graph.in_degree(n) == 0
    ]
    reached = set(sources)
    queue = deque(sources)
    while queue:
        cur = queue.popleft()
        for nxt in graph.successors(cur):
            if nxt not in reached:
                reached.add(nxt)
                queue.append(nxt)
    reached_shadow = sorted(shadow_set & reached)

    by_module = Counter((graph.get_node(n).module or "<none>") for n in shadow)
    return {
        "instance_prefixes": len(prefixes),
        "nodes": graph.number_of_nodes(),
        "edges": len(edges),
        "shadow_nodes": len(shadow),
        "shadow_ratio": round(len(shadow) / max(1, graph.number_of_nodes()), 4),
        "shadow_edges": shadow_edges,
        "cross_namespace_edges": cross_edges,
        "shadow_isolated": isolated,
        "shadow_reachable_from_top_inputs": len(reached_shadow),
        "shadow_examples": shadow[:10],
        "shadow_by_module": dict(sorted(by_module.items())),
        "constants": len(constants),
    }


def measure_fixture(filelist: str) -> dict:
    tracer = UnifiedTracer(filelist=filelist, log_level="ERROR")
    graph = tracer.build_graph()
    result = measure_graph(tracer, graph)
    result["filelist"] = filelist
    result["shadow_zero"] = result["shadow_nodes"] == 0
    return result


def collect(fixtures=DEFAULT_FIXTURES) -> dict:
    rows = []
    for filelist in fixtures:
        path = ROOT / filelist
        if not path.exists():
            rows.append({"filelist": filelist, "error": "fixture missing"})
            continue
        try:
            rows.append(measure_fixture(filelist))
        except Exception as exc:
            rows.append({"filelist": filelist, "error": f"{type(exc).__name__}: {exc}"})
    return {"fixtures": list(fixtures), "rows": rows}


def render(data: dict) -> None:
    print("P186.1 shadow-node measurement")
    print("fixture\tnodes\tshadow\tratio\tshadow_edges\tcross\treachable\texamples")
    for row in data["rows"]:
        if "error" in row:
            print(f"{row['filelist']}\tERROR\t{row['error']}")
            continue
        print(f"{row['filelist']}\t{row['nodes']}\t{row['shadow_nodes']}\t"
              f"{row['shadow_ratio']:.4f}\t{row['shadow_edges']}\t"
              f"{row['cross_namespace_edges']}\t"
              f"{row['shadow_reachable_from_top_inputs']}\t"
              f"{','.join(row['shadow_examples'][:3]) or '-'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fixture", action="append", default=[])
    args = parser.parse_args(argv)
    fixtures = tuple(args.fixture) if args.fixture else DEFAULT_FIXTURES
    data = collect(fixtures)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        render(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
