"""[iter_344 / PLAN P44.3] scope 聚合：一个 scope 里有什么。

Scope 是入口/上下文层，不追因果：
- 实例类型/父/子
- 端口方向/宽度/canonical id/internal
- 生效参数
"""
from __future__ import annotations

from pathlib import Path

import typer

from cli._common import _build_tracer, handle_compilation_error
from cli.core.semantic._common import node_dict
from cli._output import emit_json
from trace.core.compiler import CompilationError


def _params_for(tracer, path: str) -> list[dict]:
    try:
        adapter = tracer._get_adapter()
        for w in adapter.get_module_instances():
            sym = getattr(w, "_symbol", None)
            if getattr(sym, "hierarchicalPath", None) != path:
                continue
            body = getattr(sym, "body", None)
            rows = []
            for p in getattr(body, "parameters", []) or []:
                val = getattr(p, "value", None)
                try:
                    text = val.toString() if hasattr(val, "toString") else str(val)
                except Exception:
                    text = None
                rows.append({"name": str(getattr(p, "name", "")),
                             "value": text,
                             "is_overridden": bool(getattr(p, "isOverridden", False)),
                             "is_local_param": bool(getattr(p, "isLocalParam", False))})
            return rows
    except Exception:
        return []
    return []


def _signals_under(tracer, path: str) -> list[dict]:
    """[iter_345 / PLAN P44.5] scope 的直接子信号/端口（不展开因果）。"""
    graph = tracer.get_graph()
    prefix = path + "."
    out = []
    for nid in graph.nodes():
        if not nid.startswith(prefix):
            continue
        rest = nid[len(prefix):]
        if not rest or "." in rest:
            continue
        node = graph.get_node(nid)
        if node is None:
            continue
        kind = getattr(getattr(node, "kind", None), "name", "")
        if kind in ("INSTANTIATED_MODULE", "GENERATE_BLOCK"):
            continue
        direction = ""
        if kind == "PORT_IN":
            direction = "input"
        elif kind == "PORT_OUT":
            direction = "output"
        elif kind == "PORT_INOUT":
            direction = "inout"
        out.append({"name": rest, "canonical_id": nid, "kind": kind,
                    "width": list(node.width) if node.width else None,
                    "is_port": bool(getattr(node, "is_port", False))
                    or kind.startswith("PORT_"),
                    "direction": direction})
    out.sort(key=lambda x: x["name"])
    return out


def scope_cmd(
    path: str = typer.Argument(..., help="实例路径 (如 top.u_dut)"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """一个 scope 的聚合清单：类型/父/子/端口/参数（不做因果追踪）。"""
    try:
        tracer = _build_tracer(file=file, filelist=filelist, log_level=log_level)
        tracer.build_graph()
        mig = tracer.get_module_graph()
        node = mig.get_instance(path) if mig is not None else None
        top_sym = None
        if node is None:
            try:
                for t in getattr(tracer._get_adapter()._root, 'topInstances', []):
                    if getattr(t, "hierarchicalPath", None) == path:
                        top_sym = t
                        break
            except Exception:
                top_sym = None
        if node is None and top_sym is None:
            graph = tracer.get_graph()
            prefix = path + "."
            under = [n for n in graph.nodes() if n.startswith(prefix)]
            is_class = path in set(tracer.list_classes())
            if not under and not is_class:
                data = {"ok": False, "command": "scope",
                        "params": {"path": path, "file": str(file) if file else None,
                                   "filelist": filelist},
                        "error": "scope not found", "result": None,
                        "errors": [{"error": "scope not found", "path": path,
                                    "hint": ("RTL scope 只支持 module/instance；"
                                             "class instance (如 top.e) 请用 `svq class <type>` "
                                             "或 `svq trace covergroup <cg> --instance top.e`")}]}
                if json_output:
                    emit_json(data, pretty)
                else:
                    print(f"Error: scope not found: {path}")
                raise typer.Exit(code=1)
            # class type-level scope 优先于 generate（packet.addr 是成员不是 generate）
            if is_class:
                members = [node_dict(n) for n in tracer.trace_class_members(path)]
                instances = [node_dict(n) for n in tracer.trace_class_instances(path)]
                data = {"ok": True, "command": "scope",
                        "params": {"path": path, "file": str(file) if file else None,
                                   "filelist": filelist},
                        "result": {"scope": path, "canonical_id": path,
                                   "kind": "class", "module_type": path, "parent": None,
                                   "children": [], "ports": [], "parameters": [],
                                   "signals": [], "members": members,
                                   "instances": instances},
                        "errors": []}
                if json_output:
                    emit_json(data, pretty)
                else:
                    print(f"class scope: {path}, members={len(members)}")
                return
            # generate scope 路径：有 <path>. 子节点，但不是 MIG instance
            data = {"ok": True, "command": "scope",
                    "params": {"path": path, "file": str(file) if file else None,
                               "filelist": filelist},
                    "result": {"scope": path, "canonical_id": path,
                               "kind": "generate", "module_type": "generate",
                               "parent": path.rsplit(".", 1)[0] if "." in path else None,
                               "children": [], "ports": [],
                               "parameters": [], "signals": _signals_under(tracer, path),
                               "members": [], "instances": []},
                    "errors": []}
            if json_output:
                emit_json(data, pretty)
            else:
                print(f"generate scope: {path}")
            return
        children = []
        for inst in tracer.get_instances():
            if getattr(inst, "parent", None) == path:
                children.append({"full_path": inst.full_path,
                                 "name": inst.name,
                                 "module_type": inst.module_type,
                                 "canonical_id": inst.full_path})
        ports = []
        if node is not None:
            for pn, p in sorted(getattr(node, "ports", {}).items()):
                ports.append({
                    "name": pn,
                    "direction": getattr(p, "direction", ""),
                    "width": list(p.width) if getattr(p, "width", None) else None,
                    "canonical_id": f"{path}.{pn}",
                    "internal_signal": getattr(p, "internal_signal", None),
                })
        else:
            _adapter = tracer._get_adapter()
            for pd in _adapter.get_port_declarations(top_sym):
                pn = _adapter.get_port_name(pd)
                direction = _adapter.get_port_name_and_direction(pd)[1]
                t = getattr(pd, "type", None)
                bw = getattr(t, "bitWidth", None)
                ports.append({
                    "name": pn,
                    "direction": direction,
                    "width": [int(bw) - 1, 0] if bw else None,
                    "canonical_id": f"{path}.{pn}",
                    "internal_signal": f"{path}.{pn}",
                })
        ports.sort(key=lambda x: x["name"])
        data = {
            "ok": True,
            "command": "scope",
            "params": {"path": path, "file": str(file) if file else None,
                       "filelist": filelist},
            "result": {
                "scope": path,
                "canonical_id": path,
                "module_type": (node.module_type if node is not None
                                else getattr(top_sym, "name", path)),
                "parent": (node.parent if node is not None else None),
                "kind": "instance",
                "children": children,
                "ports": ports,
                "parameters": _params_for(tracer, path),
                "signals": _signals_under(tracer, path),
                "members": [],
                "instances": [],
            },
            "errors": [],
        }
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"scope: {path} ({node.module_type})")
            print(f"children: {len(children)} ports: {len(ports)}")
    except typer.Exit:
        raise
    except CompilationError as e:
        handle_compilation_error(e)
    except Exception as e:
        data = {"ok": False, "command": "scope", "error": str(e),
                "params": {"path": path}, "result": None, "errors": [str(e)]}
        if json_output:
            emit_json(data, pretty)
        else:
            print(f"Error: {e}")
        raise typer.Exit(code=1) from None
