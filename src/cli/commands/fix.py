# -*- coding: utf-8 -*-
"""
fix.py - 自动修复 elaboration 问题

[ADD 2026-06-12] 配合 strict=True 默认 (Req-15 后续) 提供修复工具.
当用户跑 `stats` 看到 MissingTimeScale 错, 可以直接:
  python run_cli.py fix timescale --filelist project.f
列出会改哪些文件 (dry-run), 加 --apply 才真改.

设计原则:
- 跟 strict=True 默认一脉相承: '从 filelist 入手解决问题', 不是 bypass
- 复用 sv_query 的 pyslang 编译器检测, 跟 strict default 行为一致
- 默认 dry-run (防止误改)
- idempotent: 文件已有 timescale 跳过, 不会重复加
- 备份: --apply 默认备份原文件到 .bak
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

import typer

# [ADD 2026-06-12] 复用 _common
from cli._common import _build_tracer
# [ADD 2026-06-12] fix imports 子命令
from cli.commands.fix_imports import fix_imports_cmd
# [ADD 2026-06-12 Req-19] fix widths: 用 syntax tree + pyslang.clog2 拿 $clog2(\`MACRO) 真实位宽
from cli.commands.fix_widths import fix_widths_cmd

fix_app = typer.Typer(help="[EXPERIMENTAL] 自动修复 elaboration 问题 (MissingTimeScale 等)")


# ----------------------------------------------------------------------------
# timescale 检测 + 修复
# ----------------------------------------------------------------------------

TIMESCALE_RE = re.compile(r"^\s*`?\s*timescale\s+\S+\s*/\s*\S+", re.IGNORECASE | re.MULTILINE)
# module / package / interface / program 关键字位置 (用于判断 timescale 插入点)
MODULE_START_RE = re.compile(r"^\s*(?:module|package|interface|program|class)\s+\w+", re.MULTILINE)


def _has_timescale(content: str) -> bool:
    """检查文件是否已有 `timescale` 指令"""
    # 只看前 30 行 (一般 timescale 在最开头)
    head = "\n".join(content.splitlines()[:30])
    return bool(TIMESCALE_RE.search(head))


def _find_insertion_point(content: str) -> int:
    """找 timescale 插入位置 (返回字符 index)

    [ADD 2026-06-12 改进] 插到文件最开头 (注释前), 避免 timescale 被埋在
    30+ 行 // 注释后. timescale 是文件级指令, 习惯上在文件最顶上.

    Returns:
        文件最开头的字符位置 (0 通常)
    """
    return 0


def _insert_timescale(content: str, timescale: str = "1ns/1ps") -> tuple[str, int]:
    """在合适位置插入 `timescale directive

    Args:
        content: 文件内容
        timescale: timescale 字符串 (e.g. "1ns/1ps")

    Returns:
        (new_content, line_no) - 修改后内容 + 插入的行号
    """
    insert_pos = _find_insertion_point(content)
    directive = f"`timescale {timescale}\n"
    new_content = content[:insert_pos] + directive + content[insert_pos:]
    # 计算插入的行号
    line_no = content[:insert_pos].count("\n") + 1
    return new_content, line_no


# ----------------------------------------------------------------------------
# CLI: fix timescale
# ----------------------------------------------------------------------------

@fix_app.command(name="timescale")
def fix_timescale(
    filelist: str = typer.Option(..., "--filelist", help="Path to filelist (.f/.fl)"),
    apply: bool = typer.Option(False, "--apply", help="[危险] 真改文件. 默认 dry-run 只列出会改哪些"),
    timescale: str = typer.Option("1ns/1ps", "--timescale", help="Timescale directive (默认 1ns/1ps)"),
    include_headers: bool = typer.Option(False, "--include-headers", help="也修 .svh 头文件 (默认跳过)"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="[--apply 时] 改前备份原文件到 .bak"),
    log_level: str = typer.Option("ERROR", "--log-level", help="Compiler log level"),
):
    """[ADD 2026-06-12] 自动修复 MissingTimeScale 错误

    工作流:
    1. 用 sv_query 编译器检测 filelist 里所有 MissingTimeScale 错
    2. 列出每个缺 timescale 的 .sv 文件
    3. 默认 dry-run, 加 --apply 才真改
    4. idempotent: 已有 timescale 的文件跳过

    Examples:
        # 看哪些文件会改 (不改)
        python run_cli.py fix timescale --filelist project.f

        # 真改
        python run_cli.py fix timescale --filelist project.f --apply

        # 自定义 timescale
        python run_cli.py fix timescale --filelist project.f --apply --timescale 1ps/1ps
    """
    if not Path(filelist).exists():
        typer.echo(f"Error: filelist not found: {filelist}", err=True)
        raise typer.Exit(code=1)

    # 用 non-strict 模式获取 errors (不抛异常)
    try:
        tracer = _build_tracer(filelist=filelist, strict=False, log_level=log_level)
        _ = tracer.build_graph()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    elaboration_errors = tracer.get_elaboration_errors()

    # 找所有 MissingTimeScale 错误, 按文件分组
    from collections import defaultdict
    files_to_fix: dict[str, list[dict]] = defaultdict(list)
    for err in elaboration_errors:
        if err.get("code") == "MissingTimeScale":
            file_path = err.get("file", "")
            if file_path:
                # 排除 .svh 头文件 (除非 --include-headers)
                if not include_headers and file_path.endswith(".svh"):
                    continue
                files_to_fix[file_path].append(err)

    if not files_to_fix:
        typer.echo("✅ No MissingTimeScale errors found. Nothing to fix.")
        raise typer.Exit(code=0)

    # 干跑 / 真改
    if not apply:
        typer.echo(f"[DRY-RUN] Would insert `timescale {timescale}` into {len(files_to_fix)} file(s):\n")
        for fpath, errs in files_to_fix.items():
            lines = sorted({e["line"] for e in errs})
            typer.echo(f"  {fpath}")
            typer.echo(f"    lines with error: {lines[:5]}{'...' if len(lines) > 5 else ''}")
        typer.echo("\nRun with --apply to actually modify these files.")
        raise typer.Exit(code=0)

    # 真改
    typer.echo(f"Applying `timescale {timescale}` to {len(files_to_fix)} file(s)...\n")
    fixed = 0
    skipped = 0
    for fpath, errs in files_to_fix.items():
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            typer.echo(f"  ❌ {fpath}: read failed ({e})")
            continue

        # idempotent: 已有 timescale 跳过
        if _has_timescale(content):
            typer.echo(f"  ⏭  {fpath}: already has timescale, skipped")
            skipped += 1
            continue

        new_content, line_no = _insert_timescale(content, timescale)

        # 备份
        if backup:
            try:
                Path(fpath + ".bak").write_text(content, encoding="utf-8")
            except Exception as e:
                typer.echo(f"  ⚠️  {fpath}: backup failed ({e}), continue anyway")

        # 写
        try:
            Path(fpath).write_text(new_content, encoding="utf-8")
            typer.echo(f"  ✅ {fpath}: inserted `timescale {timescale}` at line {line_no}")
            fixed += 1
        except Exception as e:
            typer.echo(f"  ❌ {fpath}: write failed ({e})")

    typer.echo(f"\nDone: {fixed} fixed, {skipped} skipped (already has timescale).")
    if backup and fixed > 0:
        typer.echo("Original files backed up to *.bak")
    raise typer.Exit(code=0)


# ----------------------------------------------------------------------------
# CLI: fix report - 修复方向报告
# ----------------------------------------------------------------------------

# 错误码 -> 修复建议 (按用户反馈: "先试着从 filelist 入手解决问题")
FIX_RECOMMENDATIONS = {
    "MissingTimeScale": {
        "category": "1. timescale",
        "fix_command": "python run_cli.py fix timescale --filelist <f> --apply",
        "auto_fixable": True,
        "doc": "用 fix timescale 自动加 `timescale 1ns/1ps`",
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


@fix_app.command(name="report")
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

    # 拿 elaboration errors
    try:
        tracer = _build_tracer(filelist=filelist, strict=False, log_level=log_level)
        _ = tracer.build_graph()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    elaboration_errors = tracer.get_elaboration_errors()
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
        typer.echo("\nNext step: 跑 'fix timescale --apply' 修 auto-fixable 部分")
    raise typer.Exit(code=0)


# [ADD 2026-06-12] 复用 fix_app 注册 fix imports 子命令
fix_app.command(name="imports")(fix_imports_cmd)
# [ADD 2026-06-12] fix widths: 解析 typedef 真实位宽 (用 syntax tree + pyslang.clog2)
fix_app.command(name="widths")(fix_widths_cmd)


if __name__ == "__main__":
    typer.run(fix_app)
