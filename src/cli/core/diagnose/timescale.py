# ruff: noqa: B007
"""
diagnose/timescale.py — [iter_234 P2] `timescale` 只读诊断 (原 `fix timescale`)

分层: core/diagnose (只读)。**本命令不再改文件** —— 方豆决定 "sv_query 不改 RTL":
  - 本命令: dry-run 列出缺 `timescale` 的文件 (供人/agent 决策)
  - 真正改文件: `python tools/fix_timescale.py <filelist> --apply` (带 .bak 备份)

规范名 `svq diagnose timescale`; 老名 `svq fix timescale` 保留为兼容别名。
"""

from __future__ import annotations

import re
from pathlib import Path

import typer

from cli._common import collect_elaboration_diagnostics

diagnose_app = typer.Typer(help="[core/diagnose] 只读诊断: 编译/依赖问题报告 (不改任何文件)")


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

@diagnose_app.command(name="timescale")
def fix_timescale(
    filelist: str = typer.Option(..., "--filelist", help="Path to filelist (.f/.fl)"),
    timescale: str = typer.Option("1ns/1ps", "--timescale", help="Timescale directive (默认 1ns/1ps)"),
    include_headers: bool = typer.Option(False, "--include-headers", help="也修 .svh 头文件 (默认跳过)"),
    log_level: str = typer.Option("ERROR", "--log-level", help="Compiler log level"),
    json_output: bool = typer.Option(False, "--json", "-j", help="[iter_234] Output JSON (core 契约)"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="[JSON] Pretty-print"),
):
    """[ADD 2026-06-12] 报告 MissingTimeScale 错误 (只读)

    工作流:
    1. 用 sv_query 编译器检测 filelist 里所有 MissingTimeScale 错
    2. 列出每个缺 timescale 的 .sv 文件
    3. **只读**: 只做 dry-run 报告 (写文件见 tools/fix_timescale.py)
    4. idempotent: 已有 timescale 的文件跳过

    Examples:
        # 看哪些文件会改 (不改)
        python run_cli.py fix timescale --filelist project.f

        # 真改
        python run_cli.py diagnose timescale --filelist project.f

        # 自定义 timescale
        python run_cli.py diagnose timescale --filelist project.f --timescale 1ps/1ps
    """
    if not Path(filelist).exists():
        typer.echo(f"Error: filelist not found: {filelist}", err=True)
        raise typer.Exit(code=1)

    # [iter_225] fix 的输入就是"有 elab 错的项目" —— 编译失败是预期路径,
    # 用结构化诊断入口 (不解析报错文本, 也不把 partial AST 当成功)。
    diag = collect_elaboration_diagnostics(filelist=filelist, log_level=log_level)
    if diag.compile_failed and not diag.errors:
        typer.echo(f"Error: {diag.failure}", err=True)
        raise typer.Exit(code=1)
    elaboration_errors = diag.errors

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
        if json_output:
            import json as _json
            typer.echo(_json.dumps({
                "ok": True, "filelist": filelist, "count": 0, "files": [],
                "suggested_timescale": timescale, "writes_files": False,
            }, indent=2 if pretty else None, ensure_ascii=False))
            raise typer.Exit(code=0)
        typer.echo("✅ No MissingTimeScale errors found. Nothing to fix.")
        raise typer.Exit(code=0)

    # [iter_234 P2] 只读: 本命令不再提供 --apply (方豆决定 "sv_query 不改 RTL")。
    # 真正的写入在 tools/fix_timescale.py (带 .bak 备份), 见本文件 docstring。
    if json_output:
        import json as _json
        typer.echo(_json.dumps({
            "ok": True,
            "filelist": filelist,
            "suggested_timescale": timescale,
            "count": len(files_to_fix),
            "files": [
                {"file": fpath, "error_lines": sorted({e["line"] for e in errs})}
                for fpath, errs in files_to_fix.items()
            ],
            "apply_command": "python tools/fix_timescale.py <filelist> --apply",
            "writes_files": False,
        }, indent=2 if pretty else None, ensure_ascii=False))
        raise typer.Exit(code=0)

    typer.echo(f"[DRY-RUN] Would insert `timescale {timescale}` into {len(files_to_fix)} file(s):\n")
    for fpath, errs in files_to_fix.items():
        lines = sorted({e["line"] for e in errs})
        typer.echo(f"  {fpath}")
        typer.echo(f"    lines with error: {lines[:5]}{'...' if len(lines) > 5 else ''}")
    typer.echo(f"\n要真正修改: python tools/fix_timescale.py <filelist> --apply"
               f" [--timescale {timescale}]")
    raise typer.Exit(code=0)
