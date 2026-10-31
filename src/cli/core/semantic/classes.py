"""
core/semantic/classes.py — [iter_237] class 查询 (`svq classes` / `svq class <name>`)

补上同类缺口: `list_classes()` / `trace_class_members()` / `trace_class_instances()` /
`trace_member_instances()` 四个库 API 此前**零 CLI 暴露** (与 instance 查询同批)。

契约与 iter_152 的架构决策一致 (D3):
  - **类型级**成员 = 结构参考 (CLASS_PROPERTY / CONSTRAINT_BLOCK 等)
  - **实例级**成员 = 数据端点 (top.p.data), "谁驱动它" 要用 fanin 走实例路径
因此 `class <name>` 分开返回 `members`(类型级) 与 `instances`(实例级), 不混为一谈。
"""
from __future__ import annotations

import re
from pathlib import Path

import typer

from cli.core.semantic._common import build_tracer, emit, fail, node_dict

_CALL_KW = {"if", "for", "while", "case", "return", "sizeof", "new", "function", "task"}


def _method_calls(body: str, method_name: str) -> list[dict]:
    """[iter_334 / PLAN P38] 从方法体文本提取调用（receiver.method / bare method）。"""
    calls = []
    seen = set()
    lines = body.splitlines()[1:]  # 去掉声明头
    for line in lines:
        for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\.\s*([A-Za-z_]\w*)\s*\(", line):
            recv, meth = m.group(1), m.group(2)
            key = (recv, meth)
            if key not in seen:
                seen.add(key)
                calls.append({"receiver": recv, "method": meth, "target_class": None})
        for m in re.finditer(r"(?<![.\w])([A-Za-z_]\w*)\s*\(", line):
            meth = m.group(1)
            if meth in _CALL_KW or meth == method_name:
                continue
            key = (None, meth)
            if key not in seen:
                seen.add(key)
                calls.append({"receiver": None, "method": meth, "target_class": None})
    return calls


def _class_methods(adapter, cls, class_name: str) -> list[dict]:
    """[iter_334 / PLAN P38] class 方法定义 + 方法体调用（不展开内部实现）。"""
    methods = []
    syntax = getattr(cls, "syntax", None)
    if syntax is None:
        return methods
    for item in getattr(syntax, "items", []):
        if "ClassMethod" not in str(getattr(item, "kind", "")):
            continue
        decl = getattr(item, "declaration", None)
        if decl is None:
            continue
        proto = str(getattr(decl, "prototype", ""))
        m = re.search(r"\b(function|task)\s+(?:[\w:]+\s+)*(\w+)\s*\(", proto)
        if not m:
            continue
        kind, name = m.group(1), m.group(2)
        try:
            file, line, _, _ = adapter.get_source_location(item)
        except Exception:
            file, line = "", 0
        body = str(decl)
        methods.append({"name": name, "kind": kind, "file": file, "line": line,
                        "calls": _method_calls(body, name)})
    return methods


def _class_relations(tracer, graph, name: str) -> dict:
    """[iter_334 / PLAN P38] class 关系：继承/成员/实例/约束/方法调用。"""
    hierarchy = tracer.get_class_hierarchy()
    members = tracer.trace_class_members(name)
    instances = tracer.trace_class_instances(name)
    member_instances = []
    for m in members:
        nodes = tracer.trace_member_instances(m.id)
        member_instances.append({"member": m.name, "count": len(nodes),
                                 "instances": [node_dict(n) for n in nodes]})
    constraints = []
    if name in graph.nodes():
        for dst in graph.successors(name):
            for e in graph.get_edges(name, dst):
                kind = getattr(getattr(e, "kind", None), "name", "")
                if kind == "CONSTRAINS" or kind.startswith("HAS_"):
                    constraints.append({"target": dst, "kind": kind})
    extends = hierarchy.get_parent(name) if hierarchy is not None else None
    adapter = tracer._get_adapter()
    cls = next((c for c in adapter.get_classes() if getattr(c, "name", "") == name), None)
    methods = _class_methods(adapter, cls, name) if cls is not None else []
    # 裸调用解析到当前类/祖先的方法；receiver 调用暂不猜类型（target_class=null）
    classes_by_name = {getattr(c, "name", ""): c for c in adapter.get_classes()}
    method_cache = {}

    def _method_names(owner: str) -> set[str]:
        if owner not in method_cache:
            c = classes_by_name.get(owner)
            method_cache[owner] = ({m["name"] for m in _class_methods(adapter, c, owner)}
                                   if c is not None else set())
        return method_cache[owner]

    for m in methods:
        for call in m.get("calls", []):
            if call.get("receiver") is not None:
                continue
            for owner in [name] + (hierarchy.get_ancestors(name) if hierarchy is not None else []):
                if call["method"] in _method_names(owner):
                    call["target_class"] = owner
                    break
    return {
        "class": name,
        "extends": extends,
        "ancestors": hierarchy.get_ancestors(name) if hierarchy is not None else [],
        "subclasses": hierarchy.get_subclasses(name) if hierarchy is not None else [],
        "descendants": hierarchy.get_all_descendants(name) if hierarchy is not None else [],
        "members": [node_dict(n) for n in members],
        "instances": [node_dict(n) for n in instances],
        "member_instances": member_instances,
        "constraints": constraints,
        "methods": methods,
    }


def class_cmd(
    name: str = typer.Argument(None, help="class 名 (如 packet); 省略则列出所有 class"),
    member: str = typer.Option(None, "--member", help="只看该成员的实例级节点 (如 data → packet.data 的各实例)"),
    relations: bool = typer.Option(False, "--relations", help="[iter_334] 查 class 关系: extends/成员/实例/约束/方法调用"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """class 查询: 不给 name 时列出所有 class; 给了则返回成员 (类型级) 与实例 (实例级)。

    [iter_247] 合并原 `classes` 命令 (2 → 1): 两者只是"有没有给 class 名"的差别,
    输出都是同一个 class 域的数据; 拆成两个命令只会让 agent 多一次猜测。

    注意: 只返回**图内已存在**的实例成员节点 (未使用的实例成员不臆造, 见 iter_152 C2)。
    """
    tracer = build_tracer(file, filelist, log_level)
    if tracer is None:
        return

    if relations:
        if name is None:
            fail("--relations requires a class name", json_output, pretty,
                 hint="例如 `svq class packet --relations`")
            return
        if name not in tracer.list_classes():
            fail("class not found", json_output, pretty, name=name,
                 hint="用 `svq class --json` (不带 class 名) 列可用 class")
            return
        rel = _class_relations(tracer, tracer.get_graph(), name)
        emit({"ok": True, "class": name, "relations": rel}, json_output, pretty)
        return

    if name is None:
        names = tracer.list_classes()
        emit({"ok": True, "count": len(names), "classes": names}, json_output, pretty)
        return

    if member:
        nodes = tracer.trace_member_instances(f"{name}.{member}")
        emit({"ok": True, "class": name, "member": member, "count": len(nodes),
              "instances": [node_dict(n) for n in nodes],
              "note": "只含图内已存在的实例成员节点"},
             json_output, pretty)
        return

    members = tracer.trace_class_members(name)
    instances = tracer.trace_class_instances(name)
    if not members and not instances:
        fail("class not found (no members/instances in graph)", json_output, pretty,
             name=name, hint="用 `svq class --json` (不带 class 名) 列可用 class")
    emit({"ok": True, "class": name,
          "member_count": len(members), "members": [node_dict(n) for n in members],
          "instance_count": len(instances), "instances": [node_dict(n) for n in instances]},
         json_output, pretty)
