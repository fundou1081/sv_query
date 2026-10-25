"""[iter_288 / PLAN P3.3] `svq audit` —— 设计审计（只读、JSON 友好）。

原 exp 10 条创意（`docs/EXP_IDEAS.md`）重新落地为 **一个命令的 8 个检查**：
协议识别 / 握手配对 / 反压环路候选 / 断言覆盖 / 覆盖缺口 /
验证缺口 / 改动风险 / 约束覆盖 / CDC 候选 / 组合链长度。

为什么要一个命令而不是 10 个：这些是"拿到陌生 RTL 时的一次性体检"，
agent 一次调用拿全量结构化结果，比记 10 个命令名更省上下文；
CLI 面也不应为一组启发式各自开一个命令（与"命令面减法"一致）。

每条检查都带 `confidence`（pattern / measured / heuristic），
输出用 candidates/findings 措辞 —— 不把启发式伪装成结论。
"""
from __future__ import annotations

import json
from pathlib import Path

import typer

from cli.core.semantic._common import build_tracer


def audit_cmd(
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="filelist (.f/.fl) for multi-file projects"),
    target: str = typer.Option(None, "--target", "-t", help="target module (实例命名空间根)"),
    checks: str = typer.Option(
        None, "--checks",
        help="逗号分隔的检查项 (默认全部): protocols,handshakes,backpressure_cycles,"
             "assertions,coverage,verification_gaps,risk,constraints,cdc,timing",
    ),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
    log_level: str = typer.Option("WARNING", "--log-level"),
) -> None:
    """设计审计：协议/握手/反压/断言/覆盖/风险/CDC/时序链（只读，启发式有标注）。

    - 每条检查输出 `confidence`（pattern / measured / heuristic）
    - 启发式结果用 `candidates` 措辞，不当作结论
    - 一次调用返回所有检查 → agent 不必逐条尝试
    """
    tracer = build_tracer(file, filelist, log_level)
    if tracer is None:
        return

    from trace.core.analysis import audit as audit_mod

    selected = [c.strip() for c in checks.split(",")] if checks else None
    try:
        result = audit_mod.run_audit(tracer, selected)
    except ValueError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(1) from e

    if json_output:
        typer.echo(json.dumps(result, indent=2 if pretty else None, ensure_ascii=False))
        return

    if pretty:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # 人类可读摘要
    typer.echo(f"Audit: target={result.get('target') or '(all tops)'}")
    typer.echo(f"Checks: {', '.join(result['checks'])}")
    for name, value in result["sections"].items():
        if isinstance(value, list):
            typer.echo(f"\n[{name}] {len(value)} 条")
            for item in value[:5]:
                typer.echo(f"  - {_short(item)}")
        elif isinstance(value, dict):
            typer.echo(f"\n[{name}]")
            for k, v in value.items():
                if k == "samples":
                    typer.echo(f"  {k}: {len(v)}")
                elif isinstance(v, (list, dict)):
                    typer.echo(f"  {k}: {len(v)}")
                else:
                    typer.echo(f"  {k}: {v}")
        else:
            typer.echo(f"\n[{name}] {value}")


def _short(item) -> str:
    """列表项的单行摘要（dict 取几个关键字段）。"""
    if not isinstance(item, dict):
        return str(item)
    for key in ("instance", "signal", "class", "candidate_cycle"):
        if key in item:
            extra = ""
            if "classification" in item:
                extra = f" ({item['classification']})"
            elif "candidates" in item:
                extra = f" → {[c.get('protocol') for c in item['candidates']]}"
            return f"{item[key]}{extra}"
    return json.dumps(item, ensure_ascii=False)[:120]
