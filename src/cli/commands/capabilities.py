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

用法:
    svq capabilities --json
    svq capabilities --json --recommended
    svq capabilities --json --include-exp
    svq capabilities            # 人类可读的层/组概览
"""
from __future__ import annotations

import json

import typer

from cli._registry import LAYERS, counts, to_json

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
    data = to_json(include_exp=include_exp, recommended_only=recommended)

    if json_output:
        typer.echo(json.dumps(data, indent=2 if pretty else None, ensure_ascii=False))
        return

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
            flag = "★" if x["recommended"] else " "
            planned = f" → {x['planned_name']}" if x["planned_name"] else ""
            typer.echo(f"   {flag} {x['name']:<28}{planned:<20} "
                       f"cost={x['cost']:<9} json={str(x['json']):<5} {x['note']}")
        typer.echo("")
    if data["planned_new"]:
        typer.echo("[计划新增 —— 语义 core 缺口]")
        for n in data["planned_new"]:
            typer.echo(f"    + {n['name']:<14} 复用 {n['reuse']}")
        typer.echo("")
    typer.echo("提示: agent 建议用 `svq capabilities --json --recommended` 取最小工具集;")
    typer.echo("      降级区需显式 `--include-exp`。")
