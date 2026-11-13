"""[iter_364 / PLAN P62.1] finding 局部 review artifact。

读取 verify structural --json 的 finding，按其 subgraph 参数调 core subgraph，
只画 finding 邻域为 SVG/HTML。不复制旧 VizData/ELK，不做全设计图。
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import typer

from cli._common import _build_tracer
from cli._output import emit_json
from sv_query.trace.core.query.subgraph import SubgraphOptions, build_subgraph

review_app = typer.Typer(help="Local review artifact for structural findings")


def _findings(data: dict) -> list[dict]:
    if isinstance(data.get("result"), dict) and isinstance(data["result"].get("findings"), list):
        return data["result"]["findings"]
    if isinstance(data.get("findings"), list):
        return data["findings"]
    if data.get("check") and data.get("id"):
        return [data]
    return []


def _pick(data: dict, finding_id: str | None) -> dict:
    items = _findings(data)
    if not items:
        raise ValueError("no findings in input")
    if not finding_id:
        return items[0]
    for item in items:
        if item.get("id") == finding_id:
            return item
    raise ValueError(f"finding id not found: {finding_id!r}")


def _source(data: dict, finding: dict, file, filelist):
    params = data.get("params", {}) if isinstance(data.get("params"), dict) else {}
    src_file = file or params.get("file")
    src_list = filelist or params.get("filelist")
    if not src_file and not src_list:
        raise ValueError("provide --file/--filelist or use findings with params.file/filelist")
    return src_file, src_list


def _subgraph_for(graph, finding: dict) -> dict:
    spec = finding.get("subgraph") or {}
    seeds = spec.get("seeds") or finding.get("seeds") or []
    if not seeds:
        raise ValueError("finding has no subgraph seeds")
    opts = SubgraphOptions(
        depth=int(spec.get("depth", 1)),
        direction=spec.get("direction", "both"),
        edge_kinds=tuple(spec.get("edge_kinds", ("connection", "driver"))),
        max_nodes=int(spec.get("max_nodes", 80)),
        max_edges=int(spec.get("max_edges", 160)),
        include_evidence=False,
    )
    return build_subgraph(graph, seeds, options=opts)


def _missing_nodes(finding: dict) -> list[dict]:
    actual = finding.get("actual") or {}
    expected = finding.get("expected") or {}
    port = expected.get("port")
    missing = actual.get("missing_instances") or []
    if not port:
        return []
    return [{
        "id": f"{inst}.{port}",
        "kind": "MISSING",
        "module": inst,
        "label": f"{port}? (missing)",
        "synthetic": True,
    } for inst in missing]


def _rank_groups(nodes: list[dict], edges: list[dict], seeds: list[str]):
    ids = [n["id"] for n in nodes]
    adj: dict[str, list[str]] = {n: [] for n in ids}
    indeg: dict[str, int] = {n: 0 for n in ids}
    for e in edges:
        if e["src"] in adj and e["dst"] in indeg:
            adj[e["src"]].append(e["dst"])
            indeg[e["dst"]] += 1
    for nid in adj:
        adj[nid] = sorted(set(adj[nid]))
    rank = {n: 0 for n in ids}
    queue = sorted(n for n in ids if indeg[n] == 0)
    while queue:
        cur = queue.pop(0)
        for nxt in adj[cur]:
            rank[nxt] = max(rank[nxt], rank[cur] + 1)
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
        queue.sort()
    groups: dict[int, list[str]] = {}
    for nid in ids:
        groups.setdefault(rank[nid], []).append(nid)
    return [sorted(groups[k]) for k in sorted(groups)]



def _svg_header(finding: dict) -> list[str]:
    return [
        f'<text x="20" y="28" font-family="monospace" font-size="15" fill="#111">'
        f'{html.escape(finding.get("id", "finding"))}</text>',
        f'<text x="20" y="50" font-family="monospace" font-size="12" fill="#444">'
        f'{html.escape(finding.get("message", ""))}</text>',
    ]


def _edge_svg(edge: dict, pos: dict) -> str | None:
    if edge["src"] not in pos or edge["dst"] not in pos:
        return None
    x1, y1 = pos[edge["src"]]
    x2, y2 = pos[edge["dst"]]
    return (f'<line x1="{x1 + 180}" y1="{y1 + 18}" x2="{x2}" y2="{y2 + 18}" '
            f'stroke="#777" stroke-width="1.2" marker-end="url(#arrow)">'
            f'<title>{html.escape(edge.get("condition") or edge.get("expression") or edge["kind"])}'
            f'</title></line>')


def _missing_edge_svg(instance: str, missing_id: str, pos: dict) -> str | None:
    if instance not in pos or missing_id not in pos:
        return None
    x1, y1 = pos[instance]
    x2, y2 = pos[missing_id]
    return (f'<line x1="{x1 + 180}" y1="{y1 + 18}" x2="{x2}" y2="{y2 + 18}" '
            f'stroke="#d33" stroke-width="1.4" stroke-dasharray="5,3" '
            f'marker-end="url(#arrow)"><title>missing port</title></line>')


def _node_svg(nid: str, node: dict, pos: dict, seeds: set[str]) -> list[str]:
    x, y = pos[nid]
    if node.get("synthetic"):
        fill, stroke, dash = "#fff0f0", "#d33", ' stroke-dasharray="5,3"'
    elif nid in seeds:
        fill, stroke, dash = "#eef5ff", "#2563eb", ""
    else:
        fill, stroke, dash = "#fafafa", "#333", ""
    label = node.get("label") or nid
    return [
        f'<rect x="{x}" y="{y}" width="180" height="38" rx="5" '
        f'fill="{fill}" stroke="{stroke}"{dash}/>',
        f'<text x="{x + 8}" y="{y + 24}" font-family="monospace" '
        f'font-size="10" fill="#111">{html.escape(str(label)[:34])}</text>',
        f'<title>{html.escape(nid)}</title>',
    ]


def _layout_data(finding: dict, result: dict, seed_list: list[str]):
    missing = _missing_nodes(finding)
    nodes = list(result["nodes"]) + missing
    edges = list(result["edges"])
    missing_insts = (finding.get("actual") or {}).get("missing_instances") or []
    for inst, miss in zip(missing_insts, missing):
        edges.append({"src": inst, "dst": miss["id"]})
    return nodes, edges, _rank_groups(nodes, edges, seed_list)


def _positions(groups) -> dict[str, tuple[int, int]]:
    pos: dict[str, tuple[int, int]] = {}
    for col, group in enumerate(groups):
        for row, nid in enumerate(group):
            pos[nid] = (40 + col * 250, 90 + row * 80)
    return pos


def _edges_svg(result: dict, missing: list[dict], missing_insts: list[str],
               pos: dict) -> list[str]:
    out = []
    for e in result["edges"]:
        line = _edge_svg(e, pos)
        if line:
            out.append(line)
    for inst, miss in zip(missing_insts, missing):
        line = _missing_edge_svg(inst, miss["id"], pos)
        if line:
            out.append(line)
    return out


def _svg(finding: dict, result: dict) -> str:
    seed_list = sorted(finding.get("seeds") or [])
    seeds = set(seed_list)
    nodes, layout_edges, groups = _layout_data(finding, result, seed_list)
    by_id = {n["id"]: n for n in nodes}
    missing = _missing_nodes(finding)
    missing_insts = (finding.get("actual") or {}).get("missing_instances") or []
    pos = _positions(groups)
    max_rows = max((len(g) for g in groups), default=1)
    width = 80 + max(1, len(groups)) * 250
    height = 120 + max_rows * 80
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" '
        'orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#555"/></marker></defs>',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    out.extend(_svg_header(finding))
    out.extend(_edges_svg(result, missing, missing_insts, pos))
    for nid in pos:
        out.extend(_node_svg(nid, by_id[nid], pos, seeds))
    out.append("</svg>")
    return "\n".join(out)



def _html(svg: str, finding: dict) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>sv_query review artifact</title></head><body>"
        f"<h2>{html.escape(finding.get('id', 'finding'))}</h2>"
        f"<p>{html.escape(finding.get('message', ''))}</p>"
        f"{svg}</body></html>"
    )


@review_app.command("render")
def render(
    findings: Path = typer.Argument(..., help="JSON from verify structural"),
    finding_id: str = typer.Option(None, "--finding-id", help="render this finding (default first)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    svg_output: str = typer.Option(None, "--svg", help="Write SVG artifact"),
    html_output: str = typer.Option(None, "--html", help="Write HTML artifact"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Print summary JSON"),
) -> None:
    """Render one structural finding's local subgraph (SVG/HTML)."""
    try:
        data = json.loads(Path(findings).read_text(encoding="utf-8"))
        finding = _pick(data, finding_id)
        src_file, src_list = _source(data, finding, file, filelist)
        tracer = _build_tracer(file=src_file, filelist=src_list)
        graph = tracer.build_graph()
        result = _subgraph_for(graph, finding)
        svg = _svg(finding, result)
        if svg_output:
            Path(svg_output).write_text(svg, encoding="utf-8")
        if html_output:
            Path(html_output).write_text(_html(svg, finding), encoding="utf-8")
        summary = {
            "ok": True,
            "command": "review_render",
            "finding_id": finding.get("id"),
            "nodes": len(result["nodes"]),
            "edges": len(result["edges"]),
            "missing": [n["id"] for n in _missing_nodes(finding)],
            "svg": svg_output,
            "html": html_output,
        }
        if json_output:
            emit_json(summary)
        elif not svg_output and not html_output:
            print(svg)
    except Exception as e:
        data = {"ok": False, "command": "review_render", "error": str(e)}
        if json_output:
            emit_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None
