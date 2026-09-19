# ruff: noqa: B007
"""
diagnose/report.py — [iter_234 P2] `fix report` 的只读报告 (规范名 `diagnose report`)

按错误码分类给出"怎么修"的建议 + 下一步命令。**只读**: 不改任何文件。
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from cli._common import collect_elaboration_diagnostics

diagnose_app = typer.Typer(help="[core/diagnose] 只读诊断: 编译/依赖问题报告 (不改任何文件)")

# 错误码 -> 修复建议 (按用户反馈: "先试着从 filelist 入手解决问题")
FIX_RECOMMENDATIONS = {
    "MissingTimeScale": {
        "category": "1. timescale",
        "fix_command": "python tools/fix_timescale.py <filelist> --apply",
        "auto_fixable": True,
        "doc": "用 tools/fix_timescale.py 自动加 `timescale 1ns/1ps` (CLI 只做诊断)",
    },
    "UndeclaredIdentifier": {
        "category": "2. filelist 完整性",
        "fix_command": "检查 filelist 是否含所有依赖 module/include",
        "auto_fixable": False,
        "doc": "UndeclaredIdentifier 通常是缺 include/instance 文件, 检查 filelist",
    },
    "UnknownModule": {
        "category": "2. filelist 完整性",
        "fix_command": "检查 filelist 是否含所有 instance module 的定义",
        "auto_fixable": False,
        "doc": "instance 的 module 定义不在 filelist, 加上去",
    },
    "TooFewArguments": {
        "category": "3. system function / 宏",
        "fix_command": "检查 $clog2 等 system function 参数 (含宏展开问题)",
        "auto_fixable": False,
        "doc": "pyslang 限制: 宏里有 system function 难解析, 可能需手改或提供新 filelist",
    },
    "CaseTypeMismatch": {
        "category": "4. 类型推断",
        "fix_command": "检查 case 表达式 / enum 类型, 可能需 type cast",
        "auto_fixable": False,
        "doc": "case 表达式类型跟 item 不匹配 (e.g. enum vs 4'd4), sv_query 推断过严",
    },
    "DuplicateDefinition": {
        "category": "5. include 顺序",
        "fix_command": "检查重复定义 (typedef/package/parameter), 可能是 include 顺序问题",
        "auto_fixable": False,
        "doc": "同一个标识符在多处定义, 需查 include 顺序",
    },
    "EmptyMember": {
        "category": "6. typedef struct",
        "fix_command": "检查 typedef struct 的成员, 不能为空",
        "auto_fixable": False,
        "doc": "typedef struct 含空成员, 可能是条件编译空体",
    },
}


@diagnose_app.command(name="report")
def fix_report(
    filelist: str = typer.Option(..., "--filelist", help="Path to filelist (.f/.fl)"),
    log_level: str = typer.Option("ERROR", "--log-level", help="Compiler log level"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="[JSON] Pretty-print"),
):
    """[ADD 2026-06-12] 生成'修复方向'报告 - 告诉用户每个错误类别怎么修

    按错误码分类, 给出:
    - 多少个文件受响
    - 该怎么修 (fix command + 文档说明)
    - 是否可自动修

    不修改任何文件, 只是诊断报告.

    Example:
        python run_cli.py fix report --filelist project.f
        python run_cli.py fix report --filelist project.f --json --pretty
    """
    from collections import defaultdict

    if not Path(filelist).exists():
        typer.echo(f"Error: filelist not found: {filelist}", err=True)
        raise typer.Exit(code=1)

    # 拿 elaboration errors (fix 的输入就是有错的项目, 见 helper 契约)
    diag = collect_elaboration_diagnostics(filelist=filelist, log_level=log_level)
    if diag.compile_failed and not diag.errors:
        typer.echo(f"Error: {diag.failure}", err=True)
        raise typer.Exit(code=1)
    elaboration_errors = diag.errors
    if not elaboration_errors:
        typer.echo("✅ No elaboration errors found. Project is clean!")
        raise typer.Exit(code=0)

    # 按 category 分组
    by_category: dict[str, list[dict]] = defaultdict(list)
    by_code: dict[str, int] = defaultdict(int)
    by_code_files: dict[str, set] = defaultdict(set)
    unknown_codes: set[str] = set()

    for err in elaboration_errors:
        code = err.get("code", "Unknown")
        rec = FIX_RECOMMENDATIONS.get(code)
        category = rec["category"] if rec else "7. 其他"
        by_category[category].append(err)
        by_code[code] += 1
        if err.get("file"):
            by_code_files[code].add(err["file"])
        if code not in FIX_RECOMMENDATIONS:
            unknown_codes.add(code)

    if json_output:
        out = {
            "total_errors": len(elaboration_errors),
            "total_unique_files": len({e.get("file", "") for e in elaboration_errors if e.get("file")}),
            "by_category": {
                cat: {
                    "count": len(errs),
                    "unique_files": len({e.get("file", "") for e in errs if e.get("file")}),
                    "sample_errors": errs[:3],  # 头 3 个 example
                }
                for cat, errs in sorted(by_category.items())
            },
            "by_code": dict(by_code),
            "auto_fixable": sum(by_code.get(c, 0) for c in FIX_RECOMMENDATIONS if FIX_RECOMMENDATIONS[c]["auto_fixable"]),
        }
        indent = 2 if pretty else None
        typer.echo(json.dumps(out, indent=indent, ensure_ascii=False))
        raise typer.Exit(code=0)

    # 文本输出
    unique_files = len({e.get("file", "") for e in elaboration_errors if e.get("file")})
    typer.echo("=== Fix Report ===\n")
    typer.echo(f"Total errors: {len(elaboration_errors)}")
    typer.echo(f"Affected files: {unique_files}\n")

    typer.echo("=== Error Categories ===\n")
    # 按 category 排序
    for category in sorted(by_category.keys()):
        errs = by_category[category]
        uniq = len({e.get("file", "") for e in errs if e.get("file")})
        # 找该 category 下的 code
        codes_in_cat = sorted({e.get("code", "Unknown") for e in errs})
        typer.echo(f"{category}: {len(errs)} error(s) in {uniq} file(s)")
        for code in codes_in_cat:
            cnt = by_code[code]
            uniq_f = len(by_code_files[code])
            rec = FIX_RECOMMENDATIONS.get(code)
            auto = "🟢 auto-fixable" if (rec and rec["auto_fixable"]) else "🟡 manual"
            typer.echo(f"    [{code}] {cnt} error(s) in {uniq_f} file(s) {auto}")
            if rec:
                typer.echo(f"        Fix: {rec['fix_command']}")
                typer.echo(f"        Doc: {rec['doc']}")

    if unknown_codes:
        typer.echo("\n=== Unknown Error Codes ===")
        for code in sorted(unknown_codes):
            cnt = by_code[code]
            typer.echo(f"    [{code}]: {cnt} error(s)  (无推荐修复, 需查 sv_query docs)")

    auto_fixable = sum(by_code.get(c, 0) for c in FIX_RECOMMENDATIONS if FIX_RECOMMENDATIONS[c]["auto_fixable"])
    typer.echo("\n=== Summary ===")
    typer.echo(f"  🟢 Auto-fixable: {auto_fixable} error(s)")
    typer.echo(f"  🟡 Manual fix needed: {len(elaboration_errors) - auto_fixable} error(s)")
    if auto_fixable > 0:
        typer.echo("\nNext step: 跑 'python tools/fix_timescale.py <filelist> --apply' 修 auto-fixable 部分")
    raise typer.Exit(code=0)
