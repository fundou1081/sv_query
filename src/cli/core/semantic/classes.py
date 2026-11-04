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

from pathlib import Path

import typer

from cli.core.semantic._common import build_tracer, emit, fail, node_dict
from trace.core.query.uvm import uvm_class_info

_CALL_KW = {"if", "for", "while", "case", "return", "sizeof", "new", "function", "task"}


def _call_receiver(adapter, node):
    this_class = getattr(node, "thisClass", None)
    if this_class is None:
        return None
    sigs = adapter._extract_signals_from_expr(this_class) or []
    return sigs[0] if sigs else None


def _call_record(adapter, node, method_name: str) -> dict | None:
    kind = str(getattr(node, "kind", ""))
    if "Call" not in kind and "Invocation" not in kind:
        return None
    sub = getattr(node, "subroutine", None)
    name = str(getattr(sub, "name", "") or "").strip()
    if not name or name in _CALL_KW or name == method_name:
        return None
    return {"receiver": _call_receiver(adapter, node), "method": name,
            "target_class": None}


def _walk_calls(adapter, node, method_name: str, out: list[dict],
                seen: set, depth: int = 0) -> None:
    if node is None or depth > 8:
        return
    record = _call_record(adapter, node, method_name)
    if record is not None:
        key = (record["receiver"], record["method"])
        if key not in seen:
            seen.add(key)
            out.append(record)
    for child in adapter._iter_children(node):
        _walk_calls(adapter, child, method_name, out, seen, depth + 1)


def _semantic_calls(adapter, body, method_name: str) -> list[dict]:
    out: list[dict] = []
    _walk_calls(adapter, body, method_name, out, set())
    return out


def _class_methods(adapter, cls, class_name: str) -> list[dict]:
    """class 方法定义 + 方法体调用（semantic AST，不展开内部实现）。"""
    methods = []
    for member in adapter.get_class_members(cls):
        if "Subroutine" not in str(getattr(member, "kind", "")):
            continue
        if getattr(member, "syntax", None) is None:
            continue  # built-in methods (randomize 等) 不是类声明
        name = str(getattr(member, "name", "") or "").strip()
        if not name:
            continue
        sub_kind = str(getattr(member, "subroutineKind", ""))
        kind = "task" if "Task" in sub_kind else "function"
        try:
            file, line, _, _ = adapter.get_source_location(member)
        except Exception:
            file, line = "", 0
        methods.append({"name": name, "kind": kind, "file": file, "line": line,
                        "calls": _semantic_calls(adapter, getattr(member, "body", None), name)})
    return methods


def _member_dict(node) -> dict:
    item = node_dict(node)
    extra = node.extra or {}
    item["is_rand"] = bool(extra.get("rand", False))
    item["rand_mode"] = extra.get("rand_mode")
    item["type"] = extra.get("type")
    return item


def _constraint_info(info, graph) -> dict:
    rand_vars = []
    for var in info.vars:
        node = graph.get_node(var)
        if node is not None and (node.extra or {}).get("rand"):
            rand_vars.append(var)
    return {
        "id": info.block_id,
        "vars": list(info.vars),
        "conditions": list(info.conditions),
        "expr_count": info.expr_count,
        "defined_in": info.defined_in,
        "inherited": info.inherited,
        "rand_vars": rand_vars,
    }


def _class_constraint_blocks(tracer, graph, members) -> list[dict]:
    seen = set()
    out = []
    for member in members:
        for info in tracer.trace_constraints(member.id):
            if info.block_id in seen:
                continue
            seen.add(info.block_id)
            out.append(_constraint_info(info, graph))
    return sorted(out, key=lambda x: x["id"])


def _class_covergroups(tracer, name: str, hierarchy) -> list[dict]:
    owners = [name]
    if hierarchy is not None:
        owners.extend(hierarchy.get_ancestors(name))
    out = []
    for cg in tracer.list_covergroups():
        if cg.in_class not in owners:
            continue
        out.append({
            "name": cg.name,
            "in_class": cg.in_class,
            "clock": cg.clock,
            "coverpoints": [cp.name or cp.signal for cp in cg.coverpoints],
            "crosses": [cross.name for cross in cg.crosses],
            "instance_rule": cg.instance_rule,
            "file": cg.source_file,
            "line": cg.source_line,
        })
    return sorted(out, key=lambda x: x["name"])


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
        "members": [_member_dict(n) for n in members],
        "instances": [node_dict(n) for n in instances],
        "member_instances": member_instances,
        "constraint_blocks": _class_constraint_blocks(tracer, graph, members),
        "covergroups": _class_covergroups(tracer, name, hierarchy),
        "uvm": uvm_class_info(adapter, cls, name, hierarchy) if cls is not None else None,
        "constraints": constraints,
        "methods": methods,
    }


def _class_member_candidates(tracer, class_name: str, member: str) -> list[dict]:
    """[iter_348 / PLAN P47] 语义推导 class member 的实际实例路径。

    不往图里造节点：从真实根 class 实例出发，沿 CLASS_INSTANCE 成员递归；
    输出 candidate + in_graph，让 UVM testbench 能看到未使用的成员路径。
    """
    graph = tracer.get_graph()
    class_types = set(tracer.list_classes())
    type_members = {}
    for cid in class_types:
        members = []
        for dst in graph.successors(cid):
            n = graph.get_node(dst)
            if n is not None and n.kind.name in ("CLASS_PROPERTY", "CLASS_INSTANCE"):
                members.append((n.name, dst, n))
        type_members[cid] = sorted(members, key=lambda x: x[0])

    def inst_type(type_member_id: str) -> str | None:
        for succ in graph.successors(type_member_id):
            for e in graph.get_edges(type_member_id, succ):
                if e.kind.name == "IS_INSTANCE_OF":
                    return succ
        return None

    roots = []
    for nid in graph.nodes():
        n = graph.get_node(nid)
        if n is None or n.kind.name != "CLASS_INSTANCE":
            continue
        # type-level 成员实例的 module 是 class 名；真实根实例的 module 是 RTL scope
        if n.module in class_types:
            continue
        roots.append((nid, inst_type(nid)))

    out = []
    seen = set()

    def walk(inst_path: str, class_id: str | None, visited: set):
        if not class_id or (inst_path, class_id) in visited:
            return
        visited.add((inst_path, class_id))
        for mname, mid, mnode in type_members.get(class_id, []):
            if class_id == class_name and mname == member:
                cid = f"{inst_path}.{mname}"
                key = (cid, mid)
                if key not in seen:
                    seen.add(key)
                    extra = mnode.extra or {}
                    out.append({"canonical_id": cid, "member": mname,
                                "class_instance": inst_path,
                                "in_graph": cid in graph.nodes(),
                                "kind": mnode.kind.name,
                                "width": list(mnode.width) if mnode.width else None,
                                "is_rand": bool(extra.get("rand", False)),
                                "rand_mode": extra.get("rand_mode"),
                                "type": extra.get("type")})
            if mnode.kind.name == "CLASS_INSTANCE":
                walk(f"{inst_path}.{mname}", inst_type(mid), visited)

    for ip, ct in roots:
        walk(ip, ct, set())
    return sorted(out, key=lambda x: x["canonical_id"])


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
        candidates = _class_member_candidates(tracer, name, member)
        emit({"ok": True, "class": name, "member": member, "count": len(nodes),
              "instances": [node_dict(n) for n in nodes],
              "candidate_count": len(candidates), "candidates": candidates,
              "note": "instances 仅含图内已存在节点; candidates 是语义推导的完整实例路径"},
             json_output, pretty)
        return

    members = tracer.trace_class_members(name)
    instances = tracer.trace_class_instances(name)
    if not members and not instances:
        fail("class not found (no members/instances in graph)", json_output, pretty,
             name=name, hint="用 `svq class --json` (不带 class 名) 列可用 class")
    emit({"ok": True, "class": name,
          "member_count": len(members), "members": [_member_dict(n) for n in members],
          "instance_count": len(instances), "instances": [node_dict(n) for n in instances]},
         json_output, pretty)
