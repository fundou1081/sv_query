"""
core/semantic/instances.py — [iter_236 1a] 实例/层级查询 (agent 理解架构的第一步)

背景 (方豆 2026-09-09 指出的能力缺口): 库侧 `get_instances()` / MIG (`ModuleInstanceGraph`)
早已就绪, 但 **CLI 零暴露** —— agent 只能靠 `arch show` / `visualize module` **看图**,
没法**问**"这设计里有哪些实例、它们怎么连"。本模块补上这四个只读、JSON-first 的语义命令:

    svq instances   [--module M] [--depth N]       实例列表 (可过滤/限深)
    svq instance    <实例路径>                       单实例详情 (类型/父/子/端口/位宽)
    svq connections <实例路径|模块名>                连接: 实例→端口↔内部信号 / 模块→四类边
    svq hierarchy   [--module M] [--depth N]       层级树

契约 (与 core 层一致): 只读 + 每个命令都有 `--json` + 稳定字段; 不写任何文件。
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from trace.core.compiler import CompilationError

instance_app = typer.Typer(help="实例与层级查询 (只读, JSON-first)")


# ----------------------------------------------------------------------------
# 共享: 构建 tracer + 取实例/MIG
# ----------------------------------------------------------------------------
def _tracer(file, filelist, log_level: str = "WARNING"):
    return _build_tracer(file=file, filelist=filelist, log_level=log_level)


def _instances(tracer) -> list[dict]:
    """统一的实例表示 (InstanceInfo → dict)。"""
    return [
        {
            "full_path": i.full_path,
            "name": i.name,
            "module_type": i.module_type,
            "parent": i.parent,
        }
        for i in tracer.get_instances()
    ]


def _depth_ok(path: str, root: str | None, depth: int | None) -> bool:
    if depth is None:
        return True
    if root:
        rel = path[len(root):].lstrip(".") if path.startswith(root) else path
    else:
        rel = path
    return rel.count(".") < depth


def _emit(data: dict, json_output: bool, pretty: bool) -> None:
    if json_output:
        typer.echo(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))
        return
    # 人类可读简表
    for k, v in data.items():
        if isinstance(v, list):
            typer.echo(f"{k}: {len(v)}")
            for item in v[:20]:
                typer.echo(f"  - {item}")
        else:
            typer.echo(f"{k}: {v}")


# ----------------------------------------------------------------------------
# 1. instances
# ----------------------------------------------------------------------------
def instances_cmd(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    module: str = typer.Option(None, "--module", "-m", help="只看该模块(实例)下的直接实例"),
    depth: int = typer.Option(None, "--depth", "-d", help="相对 root 的最大层数"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """列出模块实例 (full_path / module_type / parent)。

    例: svq instances --filelist project.f --json
        svq instances -f top.sv --module top --depth 1 --json
    """
    try:
        tracer = _tracer(file, filelist, log_level)
        tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e)
        return
    all_inst = _instances(tracer)
    rows = all_inst
    if module:
        rows = [i for i in all_inst if i["parent"] == module or i["full_path"] == module]
    rows = [i for i in rows if _depth_ok(i["full_path"], module, depth)]
    _emit({"ok": True, "count": len(rows), "module": module, "instances": rows},
          json_output, pretty)


# ----------------------------------------------------------------------------
# 2. instance <path>
# ----------------------------------------------------------------------------
def instance_cmd(
    path: str = typer.Argument(..., help="实例路径 (如 top.u_dut)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """单个实例的详情 (类型/父/子/端口/位宽)。"""
    try:
        tracer = _tracer(file, filelist, log_level)
        tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e)
        return

    all_inst = _instances(tracer)
    me = next((i for i in all_inst if i["full_path"] == path), None)
    if me is None:
        typer.echo(json.dumps({"ok": False, "error": "instance not found", "path": path,
                               "hint": "用 `svq instances --json` 看可用实例"},
                              indent=2 if pretty else None, ensure_ascii=False))
        raise typer.Exit(code=1)

    children = [i for i in all_inst if i["parent"] == path]
    ports: list[dict] = []
    mig = tracer.get_module_graph()
    if mig is not None:
        node = mig.get_instance(path)
        if node is not None:
            for pname, p in sorted(node.ports.items()):
                ports.append({
                    "port": pname, "direction": p.direction,
                    "width": list(p.width) if p.width else None,
                    "internal_signal": p.internal_signal,
                })
    _emit({"ok": True, **me, "children": children, "ports": ports, "has_mig_data": bool(ports)},
          json_output, pretty)


# ----------------------------------------------------------------------------
# 3. connections <实例路径 | 模块名>
# ----------------------------------------------------------------------------
def connections_cmd(
    target: str = typer.Argument(..., help="实例路径 (top.u_dut) 或模块名 (dut)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """连接关系。

    - 若 target 是**实例路径** → 端口 ↔ 内部信号映射 (来自 MIG)
    - 若 target 是**模块名**  → 模块四类边 (inputs/outputs/internals/cross_module) + 置信度

    输出里带 `resolved_as` 字段, 不让你猜是哪一种。
    """
    try:
        tracer = _tracer(file, filelist, log_level)
        tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e)
        return

    mig = tracer.get_module_graph()
    node = mig.get_instance(target) if mig is not None else None
    if node is not None:
        ports = [
            {"port": n, "direction": p.direction,
             "width": list(p.width) if p.width else None,
             "internal_signal": p.internal_signal}
            for n, p in sorted(node.ports.items())
        ]
        _emit({"ok": True, "resolved_as": "instance", "instance": target,
               "module_type": node.module_type, "parent": node.parent,
               "port_count": len(ports), "ports": ports},
              json_output, pretty)
        return

    mc = tracer.trace_module(target)
    if not (mc.inputs or mc.outputs or mc.internals or mc.cross_module):
        typer.echo(json.dumps({"ok": False, "error": "target not found as instance or module",
                               "target": target,
                               "hint": "用 `svq instances --json` 或 `svq hierarchy --json` 查"},
                              indent=2 if pretty else None, ensure_ascii=False))
        raise typer.Exit(code=1)

    def _edges(edges):
        return [{"src": e.src, "dst": e.dst, "kind": e.kind.name if hasattr(e.kind, "name") else str(e.kind),
                 "condition": e.condition, "expression": e.expression} for e in edges]

    _emit({"ok": True, "resolved_as": "module", "module": target,
           "confidence": mc.confidence, "caveats": mc.caveats,
           "inputs": _edges(mc.inputs), "outputs": _edges(mc.outputs),
           "internals": _edges(mc.internals), "cross_module": _edges(mc.cross_module)},
          json_output, pretty)


# ----------------------------------------------------------------------------
# 4. hierarchy
# ----------------------------------------------------------------------------
def hierarchy_cmd(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    module: str = typer.Option(None, "--module", "-m", help="以该实例为根 (默认全部顶层)"),
    depth: int = typer.Option(None, "--depth", "-d", help="最大层数"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """实例层级树 (机器可读版 `arch show`)。"""
    try:
        tracer = _tracer(file, filelist, log_level)
        tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e)
        return

    all_inst = _instances(tracer)
    by_parent: dict[str | None, list[dict]] = {}
    for i in all_inst:
        by_parent.setdefault(i["parent"], []).append(i)
    for v in by_parent.values():
        v.sort(key=lambda x: x["full_path"])

    def build(node: dict, level: int) -> dict:
        kids = by_parent.get(node["full_path"], []) if (depth is None or level < depth) else []
        out = {
            "full_path": node["full_path"],
            "module_type": node["module_type"],
            "children": [build(k, level + 1) for k in kids],
        }
        if node.get("synthetic"):
            out["synthetic"] = True      # 顶层模块节点 (非实例), 供消费者区分
        return out

    if module:
        roots = [i for i in all_inst if i["full_path"] == module]
    else:
        # [iter_237 复核] 顶层模块本身**不是实例**, 所以它的子实例 parent 指向一个不在实例表里的
        # 路径。旧实现把这些子实例各自当成根 → 真实项目出现 "7 实例 / 7 根" (应为 1 根 + 7 子)。
        # 现在为这类 parent 造**合成根** (synthetic=True), 让树真正呈现设计层级。
        known = {i["full_path"] for i in all_inst}
        roots = [i for i in all_inst if not i["parent"]]
        synth_parents: list[str] = []
        for i in all_inst:
            p = i["parent"]
            if p and p not in known and p not in synth_parents:
                synth_parents.append(p)
        for p in synth_parents:
            roots.append({"full_path": p, "name": p.rsplit(".", 1)[-1],
                          "module_type": None, "parent": None, "synthetic": True})
    tree = [build(r, 1) for r in roots]

    def count(nodes, only_real: bool = True):
        """统计树内节点; only_real=True 时**不把合成根算作实例**。"""
        total = 0
        for n in nodes:
            real = not n.get("synthetic")
            if real or not only_real:
                total += 1
            total += count(n["children"], only_real)
        return total

    _emit({"ok": True, "root_count": len(tree),
           "instance_count": count(tree),          # 真实实例数 (不含合成根)
           "tree_node_count": count(tree, only_real=False),
           "root": module, "depth": depth, "tree": tree},
          json_output, pretty)
