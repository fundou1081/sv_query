"""
capabilities.py — [iter_230 P0] 机器可读的能力清单 (agent 的工具面真相源)

为什么需要: 项目有 60+ 个叶子命令, agent 无法靠 `--help` 文本可靠地知道
"哪些是稳定契约、哪些是试验、哪个该用"。本命令把 `cli/_registry.py` 的声明
直接吐成 JSON, 让 agent 先读清单再决定调什么, 而不是猜命令名。

设计:
- **只读** + **JSON-first** (核心纪律 4: core 层不得写文件)
- 默认列 core + view (方豆 2026-09-09 决定);
  `--recommended` 只列推荐子集 (agent 首选);
  `--include-exp` 才列出降级区 (bus/verif/struct)
- 输出带 `schema_version`, 字段变更按版本管理

[P183.4 / D11] 本命令是第一个 `sv_query.Session.execute` adapter:
命令只负责构造 request + 渲染 response; 能力数据仍由 `cli._registry.to_json`
唯一提供, Session 通过注入 handler 调用它 (session 层不 import CLI)。

用法:
    sv_query capabilities --json
    sv_query capabilities --json --recommended
    sv_query capabilities --json --include-exp
    sv_query capabilities            # 人类可读的层/组概览
"""
from __future__ import annotations

import json
from collections.abc import Mapping

import typer

from cli._output import fail
from cli._registry import LAYERS, to_json
from sv_query import Session


def _option(request: Mapping[str, object], name: str) -> bool:
    """读取一个 Session request 选项; 非 bool 是调用方错误（显式失败）。"""
    value = request.get(name, False)
    if not isinstance(value, bool):
        raise TypeError(f"capabilities option {name!r} must be a bool")
    return value


def _capabilities_provider(request: Mapping[str, object]) -> dict:
    """Session handler: 能力数据的唯一来源仍是 `cli._registry.to_json`。"""
    return to_json(
        include_exp=_option(request, "include_exp"),
        recommended_only=_option(request, "recommended"),
    )


def capabilities(
    json_output: bool = typer.Option(False, "--json", "-j", help="输出 JSON (agent 用)"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="[JSON] 缩进"),
    recommended: bool = typer.Option(
        False, "--recommended", "-r",
        help="只列推荐子集 (agent 首选; 语义事实 + 常用原语)",
    ),
    include_exp: bool = typer.Option(
        False, "--include-exp",
        help="包含降级区 exp (bus/verif/struct: 无 schema 承诺, 只修 bug)",
    ),
) -> None:
    """[iter_230] 机器可读的能力清单: 分层/契约/成本/recommended (agent 首选入口)

    列出可用能力及其契约 (只读, 不修改任何文件)。
    """
    response = Session(handlers={"capabilities": _capabilities_provider}).execute({
        "op": "capabilities",
        "recommended": recommended,
        "include_exp": include_exp,
    })

    if response.get("ok") is not True:
        error = response.get("error")
        message = error.get("message") if isinstance(error, dict) else None
        fail(
            f"capabilities 查询失败: {message or 'unknown error'}",
            json_output,
            pretty,
            error_code=response.get("error_code"),
        )

    data = response["result"]

    if json_output:
        typer.echo(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))
        return

    _render_human(data, include_exp=include_exp)


def _render_human(data: dict, *, include_exp: bool) -> None:
    """人类可读概览 (与 D11 之前的输出逐字节一致)。"""
    c = data["counts"]
    typer.echo("=== sv_query capabilities ===")
    typer.echo(f"总命令数: {c['total']}  |  按层: " +
               ", ".join(f"{k}={v}" for k, v in sorted(c["by_layer"].items())))
    typer.echo("")
    for name, spec in LAYERS.items():
        if not spec.in_capabilities and not include_exp:
            continue
        cmds = [x for x in data["commands"] if x["layer"] == name]
        if not cmds:
            continue
        typer.echo(f"[{name}] consumer={spec.consumer} stability={spec.stability} "
                   f"readonly={spec.readonly} schema={spec.schema_version}  ({len(cmds)} 个)")
        for x in cmds:
            _render_command(x)
        typer.echo("")
    if data["planned_new"]:
        typer.echo("[计划新增 —— 语义 core 缺口]")
        for n in data["planned_new"]:
            typer.echo(f"    + {n['name']:<14} 复用 {n['reuse']}")
        typer.echo("")
    bp = data["bit_precision"]
    typer.echo(f"[bit precision] modes={', '.join(bp['modes'])}  "
               f"precise={len(bp['precise_forms'])} forms  coarse={len(bp['coarse_forms'])} forms")
    typer.echo("   详见 `--json` 的 bit_precision 段; 位查询结果看 precision/coarse_fallback。")
    typer.echo("")
    typer.echo("提示: agent 建议用 `sv_query capabilities --json --recommended` 取最小工具集;")
    typer.echo("      降级区需显式 `--include-exp`。")


def _render_command(command: dict) -> None:
    flag = "★" if command["recommended"] else " "
    planned = f" → {command['planned_name']}" if command["planned_name"] else ""
    typer.echo(f"   {flag} {command['name']:<28}{planned:<20} "
               f"cost={command['cost']:<9} json={str(command['json']):<5} {command['note']}")
