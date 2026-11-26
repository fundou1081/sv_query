"""
core/semantic/instances.py — [iter_236 1a] 实例/层级查询 (agent 理解架构的第一步)

背景 (方豆 2026-09-09 指出的能力缺口): 库侧 `get_instances()` / MIG (`ModuleInstanceGraph`)
早已就绪, 但 **CLI 零暴露** —— agent 只能靠 `arch show` / `visualize module` **看图**,
没法**问**"这设计里有哪些实例、它们怎么连"。本模块补上这四个只读、JSON-first 的语义命令:

    sv_query instances   [--module M] [--depth N]       实例列表 (可过滤/限深)
    sv_query instance    <实例路径>                       单实例详情 (类型/父/子/端口/位宽)
    sv_query connections <实例路径|模块名>                连接: 实例→端口↔内部信号 / 模块→四类边
    sv_query hierarchy   [--module M] [--depth N]       层级树

契约 (与 core 层一致): 只读 + 每个命令都有 `--json` + 稳定字段; 不写任何文件。
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from sv_query.cli._common import _build_tracer, handle_compilation_error
from sv_query.cli.core.semantic.trace_common import _load_tracer_from_snapshot
from sv_query.cli.errors import ErrorCode
from sv_query.trace.core.compiler import CompilationError

instance_app = typer.Typer(help="实例与层级查询 (只读, JSON-first)")


# ----------------------------------------------------------------------------
# 共享: 构建 tracer + 取实例/MIG
# ----------------------------------------------------------------------------
def _tracer(file, filelist, log_level: str = "WARNING", from_snapshot: str | None = None):
    if from_snapshot:
        return _load_tracer_from_snapshot(from_snapshot)
    return _build_tracer(file=file, filelist=filelist, log_level=log_level)


def _require_snapshot_mig(tracer, from_snapshot, command, json_output, pretty):
    """Old/new snapshot without MIG must fail explicitly, never as ok=true empty."""
    if from_snapshot and tracer.get_module_graph() is None:
        payload = {
            "ok": False,
            "command": command,
            "error": "snapshot has no module_graph; instance/MIG queries are unavailable",
            "error_code": ErrorCode.E_SNAPSHOT_NO_MIG.value,
            "errors": [{
                "error_code": ErrorCode.E_SNAPSHOT_NO_MIG.value,
                "error": "snapshot has no module_graph",
            }],
            "hint": "re-save the snapshot with a newer sv_query or use --filelist",
        }
        _emit(payload, json_output, pretty)
        raise typer.Exit(code=1)


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
    from sv_query.trace.core.query.architecture import instance_within_depth
    return instance_within_depth(path, root, depth)


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
    path: str = typer.Argument(None, help="[iter_250] 给实例路径 → 显示详情; 省略 → 列出所有实例"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    from_snapshot: str = typer.Option(None, "--from-snapshot", help="load graph/MIG from snapshot tag"),
    module: str = typer.Option(None, "--module", "-m", help="只看该模块(实例)下的直接实例"),
    depth: int = typer.Option(None, "--depth", "-d", help="相对 root 的最大层数"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """实例查询: 不给路径 → 列出实例; 给了路径 → 该实例的详情 (类型/父/子/端口)。

    [iter_250 T2] 合并原 `instance` 命令 (2 → 1): 两者只是"有没有给实例路径"的差别。

    例: sv_query instances --filelist project.f --json
        sv_query instances -f top.sv --module top --depth 1 --json
        sv_query instances top.u_dut --filelist project.f --json
    """
    try:
        tracer = _tracer(file, filelist, log_level, from_snapshot)
        tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e)
        return
    _require_snapshot_mig(tracer, from_snapshot, "instances", json_output, pretty)
    all_inst = _instances(tracer)
    if path is not None:
        _emit_instance_detail(tracer, all_inst, path, json_output, pretty)
        return
    rows = all_inst
    if module:
        rows = [i for i in all_inst if i["parent"] == module or i["full_path"] == module]
    rows = [i for i in rows if _depth_ok(i["full_path"], module, depth)]
    _emit({"ok": True, "count": len(rows), "module": module, "instances": rows},
          json_output, pretty)


# ----------------------------------------------------------------------------
# 2. 实例详情 (由 instances <path> 分派, iter_250 合并)
# ----------------------------------------------------------------------------
def _emit_instance_detail(tracer, all_inst: list[dict], path: str,
                          json_output: bool, pretty: bool) -> None:
    """输出单个实例的详情 (类型/父/子/端口); 找不到 → 结构化失败 rc=1。"""
    me = next((i for i in all_inst if i["full_path"] == path), None)
    if me is None:
        typer.echo(json.dumps({"ok": False, "error": "instance not found", "path": path,
                               "hint": "用 `sv_query instances --json` 看可用实例"},
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
# 3. connections <实例路径>
# ----------------------------------------------------------------------------
def connections_cmd(
    target: str = typer.Argument(..., help="实例路径 (top.u_dut); 只接受实例, 不接受模块名"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    from_snapshot: str = typer.Option(None, "--from-snapshot", help="load graph/MIG from snapshot tag"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """连接关系（只接受实例路径）。

    target 必须是**实例路径** → 端口 ↔ 内部信号映射 (来自 MIG)。
    模块名会被显式拒绝并提示同类型的实例；不再提供模块定义命名空间的四类边。
    输出里带 `resolved_as` 字段。
    """
    try:
        tracer = _tracer(file, filelist, log_level, from_snapshot)
        tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e)
        return
    _require_snapshot_mig(tracer, from_snapshot, "connections", json_output, pretty)

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

    # [iter_271] 实例级图只认实例路径 (方豆决策: "只认实例, 干净一些")。
    # 以前这里走 `trace_module(target)`, 输出模块定义命名空间的边; 切换到实例级后
    # 那些 id 不在图里 → networkx 抛 "node not in digraph" (不是友好错误)。
    # 现在显式失败, 并给出"该类型有哪些实例"的提示。
    same_type = [i for i in _instances(tracer) if i.get("module_type") == target]
    hint = "connections 只接受**实例路径**"
    if same_type:
        hint += "；该类型的实例: " + ", ".join(i["full_path"] for i in same_type[:5])
    _emit({"ok": False, "error": "target is not an instance path", "target": target,
           "resolved_as": "unknown", "hint": hint},
          json_output, pretty)
    raise typer.Exit(code=1)


# ----------------------------------------------------------------------------
# 4. hierarchy
# ----------------------------------------------------------------------------
def hierarchy_cmd(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    from_snapshot: str = typer.Option(None, "--from-snapshot", help="load graph/MIG from snapshot tag"),
    module: str = typer.Option(None, "--module", "-m", help="以该实例为根 (默认全部顶层)"),
    depth: int = typer.Option(None, "--depth", "-d", help="最大层数"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """实例层级树 (机器可读版 `arch show`)。"""
    try:
        tracer = _tracer(file, filelist, log_level, from_snapshot)
        tracer.build_graph()
    except CompilationError as e:
        handle_compilation_error(e)
        return
    _require_snapshot_mig(tracer, from_snapshot, "hierarchy", json_output, pretty)

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
