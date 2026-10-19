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


def class_cmd(
    name: str = typer.Argument(None, help="class 名 (如 packet); 省略则列出所有 class"),
    member: str = typer.Option(None, "--member", help="只看该成员的实例级节点 (如 data → packet.data 的各实例)"),
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
