"""[iter_365 / PLAN P63.3] covergroup 语义查询。

covergroup 是覆盖率观察域：定义/采样引用独立于数据流；
本模块只暴露已有 CovergroupTracer / CovergroupExtractor 查询。
"""
from __future__ import annotations

from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli._output import emit_json
from trace.core.compiler import CompilationError


def _cg_summary(cg) -> dict:
    return {
        "name": cg.name,
        "in_class": cg.in_class,
        "host_module": cg.host_module,
        "clock": cg.clock,
        "instance_rule": cg.instance_rule,
        "coverpoints": [
            {"name": cp.name, "signal": cp.signal, "iff": cp.iff,
             "bins": len(cp.bins), "sampled": len(cp.sampled)}
            for cp in cg.coverpoints
        ],
        "crosses": [
            {"name": cross.name, "items": list(cross.items), "iff": cross.iff}
            for cross in cg.crosses
        ],
        "file": cg.source_file,
        "line": cg.source_line,
        "errors": list(cg.errors),
    }


def _sampling_dict(item) -> dict:
    return {
        "coverpoint": item.cp_name,
        "signal_raw": item.signal_raw,
        "sampled": list(item.sampled),
        "drivers": list(item.drivers),
        "missing": list(item.missing),
    }


def _coverpoint_ref(item) -> dict:
    return {
        "covergroup": item.cg_name,
        "coverpoint": item.cp_name,
        "in_class": item.in_class,
        "host_module": item.host_module,
        "ref_name": item.ref_name,
        "select": item.select,
        "instance": item.instance,
    }


def _rand_dict(item) -> dict:
    return {
        "covergroup": item.cg_name,
        "coverpoint": item.cp_name,
        "property": item.prop_id,
        "constraints": [
            {"block": c.block_id, "vars": list(c.vars),
             "conditions": list(c.conditions), "expr_count": c.expr_count}
            for c in item.constraints
        ],
    }


def _fail(message: str, json_output: bool, pretty: bool) -> None:
    data = {"ok": False, "command": "trace_covergroup", "error": message,
            "errors": [message]}
    if json_output:
        emit_json(data, pretty)
    else:
        typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def covergroups_cmd(
    class_name: str = typer.Option(None, "--class", help="filter by defining class"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """列出 covergroup 定义（可按定义 class 过滤）。"""
    try:
        tracer = _build_tracer(file=file, filelist=filelist)
        tracer.build_graph()
        items = [_cg_summary(cg) for cg in tracer.list_covergroups()]
        if class_name:
            items = [x for x in items if x["in_class"] == class_name]
        data = {"ok": True, "command": "trace_covergroups",
                "params": {"file": str(file) if file else None, "filelist": filelist,
                           "class": class_name},
                "result": {"count": len(items), "covergroups": items},
                "errors": []}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Covergroups ({len(items)}):")
            for cg in items:
                print(f"  {cg['name']} class={cg['in_class']} "
                      f"coverpoints={len(cg['coverpoints'])} crosses={len(cg['crosses'])}")
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        _fail(str(e), json_output, pretty)


def coverpoints_cmd(
    signal: str = typer.Argument(..., help="top.din / top.e.p.addr / packet.addr"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """反向查询：信号被哪些 covergroup/coverpoint 采样。"""
    try:
        tracer = _build_tracer(file=file, filelist=filelist)
        tracer.build_graph()
        items = [_coverpoint_ref(x) for x in tracer.trace_coverpoints(signal)]
        data = {"ok": True, "command": "trace_coverpoints",
                "params": {"file": str(file) if file else None, "filelist": filelist,
                           "signal": signal},
                "result": {"signal": signal, "count": len(items), "matches": items},
                "errors": []}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Coverpoints sampling {signal} ({len(items)}):")
            for m in items:
                print(f"  {m['covergroup']}.{m['coverpoint']} "
                      f"instance={m['instance'] or '-'}")
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        _fail(str(e), json_output, pretty)


def covergroup_cmd(
    covergroup: str = typer.Argument(..., help="covergroup definition name"),
    coverpoint: str = typer.Option(None, "--coverpoint", help="filter by coverpoint"),
    instance: str = typer.Option(None, "--instance", help="class cg instance (top.e)"),
    rand: bool = typer.Option(False, "--rand", help="show rand property -> constraints"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """查询 covergroup 的采样链，或 --rand 的属性→约束链。"""
    try:
        tracer = _build_tracer(file=file, filelist=filelist)
        tracer.build_graph()
        cgs = [x for x in tracer.list_covergroups() if x.name == covergroup]
        if not cgs:
            _fail(f"covergroup not found: {covergroup!r}", json_output, pretty)
        if rand:
            items = [_rand_dict(x) for x in tracer.trace_covergroup_rand_linkage(
                covergroup, coverpoint, instance)]
            result = {"mode": "rand", "covergroup": _cg_summary(cgs[0]),
                      "count": len(items), "links": items}
        else:
            items = [_sampling_dict(x) for x in tracer.trace_covergroup_sampling(
                covergroup, coverpoint, instance)]
            result = {"mode": "sampling", "covergroup": _cg_summary(cgs[0]),
                      "count": len(items), "samples": items}
        data = {"ok": True, "command": "trace_covergroup",
                "params": {"file": str(file) if file else None, "filelist": filelist,
                           "covergroup": covergroup, "coverpoint": coverpoint,
                           "instance": instance, "rand": rand},
                "result": result, "errors": []}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"{covergroup} ({result['mode']}): {result['count']}")
            for item in items:
                print(f"  {item}")
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        _fail(str(e), json_output, pretty)
