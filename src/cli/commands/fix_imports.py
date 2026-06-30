# -*- coding: utf-8 -*-
"""
fix_imports.py - 自动找 UndeclaredIdentifier / UnknownModule 的源文件

[ADD 2026-06-12] 'fix imports' 通过诊断 + 扫项目, 推荐补 filelist 的文件.

设计目标 ('使用更方便' = minimal user input, smart defaults):
- 一行命令: python run_cli.py fix imports --filelist project.f
- 自动扫项目根目录 (filelist 同级), 找含缺失标识符定义的 .sv 文件
- 生成新 filelist (e.g. project_fixed.f) 加进原 filelist 即可
- 默认 dry-run, 加 --write 写到文件
- 显示每个缺失 identifier 推荐的 fix 来源 (e.g. 'service_message_t 可能在 npu_message_service_defines.sv')

Algorithm:
1. 跑 fix report 拿所有 UndeclaredIdentifier / UnknownModule / UnknownClassOrPackage 错
2. 每个 identifier, 扫项目 .sv/.svh 文件 (含 typedef/module/package/define)
3. 找匹配, 推荐文件
4. 输出 'add these files to filelist' 报告 + 生成新 filelist

不适用场景:
- identifier 是 system task (e.g. $clog2, $readmemh) — pyslang 自己处理
- identifier 是宏 (e.g. \`DCACHE_WAY) — 不能用 typedef/module 找
- identifier 是 NaplesPU 自身缺定义 (e.g. service_message_t) — 扫遍项目也找不到
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import typer

from cli._common import _build_tracer


# ----------------------------------------------------------------------------
# 核心算法: 扫项目找含 identifier 定义的文件
# ----------------------------------------------------------------------------

# 模式: module X / typedef X / package X / define X
DEFINE_PATTERNS = [
    re.compile(r"^\s*module\s+(?:static\s+)?(?:automatic\s+)?(\w+)", re.MULTILINE),  # module foo
    re.compile(r"^\s*typedef\s+[^;]+?\b(\w+)\s*(?:\[|$|\s*[;=])", re.MULTILINE),  # typedef foo (a-zA-Z0-9_ chars)
    re.compile(r"^\s*package\s+(\w+)", re.MULTILINE),  # package foo
    re.compile(r"^\s*interface\s+(\w+)", re.MULTILINE),  # interface foo
    re.compile(r"^\s*class\s+(\w+)", re.MULTILINE),  # class foo
    re.compile(r"^\s*program\s+(\w+)", re.MULTILINE),  # program foo
    re.compile(r"`define\s+(\w+)\b"),  # `define FOO
]


def _extract_definitions_from_file(filepath: Path) -> set[str]:
    """从单个 .sv/.svh 文件抽所有定义名 (typedef/module/package/define/class/interface/program)"""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return set()

    names: set[str] = set()
    for pat in DEFINE_PATTERNS:
        for m in pat.finditer(content):
            name = m.group(1)
            if name and not name.startswith("_"):
                names.add(name)
    return names


def _scan_project_for_identifier(
    project_root: Path,
    identifier: str,
    exclude_files: set[Path] | None = None,
) -> Path | None:
    """扫项目找含 identifier 定义的文件

    Returns:
        第一个含该 identifier 定义的文件 (按文件名字母序, 优先 .svh 然后 .sv)
    """
    if not project_root.exists() or not project_root.is_dir():
        return None

    exclude_files = exclude_files or set()
    candidates: list[Path] = []

    # 扫 .sv 和 .svh
    for ext in ("*.svh", "*.sv"):
        for fp in project_root.rglob(ext):
            if fp in exclude_files:
                continue
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            # 简单匹配: identifier 出现在定义行
            # 精确一点: 用 _extract_definitions_from_file (跟其他 algorithm 一致)
            if identifier in _extract_definitions_from_file(fp):
                candidates.append(fp)

    if not candidates:
        return None
    # 排序: .svh 优先, 然后 .sv, 然后按路径
    candidates.sort(key=lambda p: (0 if p.suffix == ".svh" else 1, str(p)))
    return candidates[0]


# ----------------------------------------------------------------------------
# 报告构建
# ----------------------------------------------------------------------------

def _build_suggestions(
    elaboration_errors: list[dict],
    project_root: Path,
    existing_files: set[Path],
) -> dict:
    """为每个缺失 identifier 找 fix 来源"""
    # 收集所有 unique identifier
    identifiers: dict[str, list[dict]] = defaultdict(list)  # identifier -> [errors引用]
    for err in elaboration_errors:
        code = err.get("code", "")
        if code not in ("UndeclaredIdentifier", "UnknownClassOrPackage", "UnknownModule"):
            continue
        ident = err.get("identifier")
        if ident:
            identifiers[ident].append(err)

    suggestions: list[dict] = []
    for ident, errs in identifiers.items():
        # 找 fix 来源
        source_file = _scan_project_for_identifier(
            project_root, ident, exclude_files=existing_files
        )
        suggestions.append({
            "identifier": ident,
            "count": len(errs),
            "sample_files": sorted({e.get("file", "?") for e in errs if e.get("file")})[:3],
            "found_in": str(source_file) if source_file else None,
            "fixable": source_file is not None,
        })
    return {
        "identifiers": suggestions,
        "fixable_count": sum(1 for s in suggestions if s["fixable"]),
        "unfixable_count": sum(1 for s in suggestions if not s["fixable"]),
    }


# ----------------------------------------------------------------------------
# CLI 命令
# ----------------------------------------------------------------------------

def fix_imports_cmd(
    filelist: str = typer.Option(..., "--filelist", help="Path to filelist (.f/.fl)"),
    project_root: str = typer.Option(
        None, "--project-root", help="要扫描的目录 (默认: filelist 所在目录的 src/)"
    ),
    write: str = typer.Option(
        None, "--write", help="把推荐的文件写到新 filelist (例: project_fixed.f). 不传则只打印"
    ),
    log_level: str = typer.Option("ERROR", "--log-level", help="Compiler log level"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="[JSON] Pretty-print"),
    top: int = typer.Option(20, "--top", "-n", help="[Text] 最多显示 N 个 identifier 建议"),
):
    """[ADD 2026-06-12] 自动找 UndeclaredIdentifier 错误的 fix 来源

    工作流:
    1. 跑 fix report 拿所有 UndeclaredIdentifier 错 (含 identifier 名字)
    2. 扫 --project-root 找含该 identifier 定义的文件
    3. 推荐 fix: 'add path/to/x.sv to your filelist'
    4. 默认 dry-run 打印, --write project_fixed.f 写新 filelist

    Examples:
        # 找 fix 源
        python run_cli.py fix imports --filelist project.f

        # 指定扫描目录
        python run_cli.py fix imports --filelist project.f --project-root /path/to/project/src

        # 生成新 filelist
        python run_cli.py fix imports --filelist project.f --write project_fixed.f

    Note: 不能 fix:
    - 标识符是 system task ($clog2 等)
    - 标识符是宏 (\`FOO)
    - 标识符是项目本身缺定义 (扫不到)
    """
    fl_path = Path(filelist)
    if not fl_path.exists():
        typer.echo(f"Error: filelist not found: {filelist}", err=True)
        raise typer.Exit(code=1)

    # 默认 project_root: 从 filelist 里第一个 .sv 文件的目录往回找
    if project_root is None:
        # 读 filelist 找第一个 .sv 路径
        first_sv = None
        try:
            for line in fl_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith(("//", "#", "+", "-")):
                    continue
                if line.endswith(".sv") or line.endswith(".svh"):
                    first_sv = Path(line).resolve()
                    break
        except Exception:
            pass

        if first_sv:
            # 从 first_sv 开始, 向上找含 src/ 的父级
            current = first_sv.parent
            for _ in range(5):  # 最多向上 5 层
                if (current / "src").exists() and (current / "src").is_dir():
                    project_root = str(current / "src")
                    break
                if current.parent == current:  # 到达根
                    break
                current = current.parent

        # 回退: filelist 同级
        if not project_root:
            fl_dir = fl_path.parent
            candidate = fl_dir / "src"
            if candidate.exists():
                project_root = str(candidate)
            else:
                project_root = str(fl_dir)
    project_root = Path(project_root).resolve()
    if not project_root.exists():
        typer.echo(f"Error: project_root not found: {project_root}", err=True)
        raise typer.Exit(code=1)

    # 读现有 filelist 内容
    existing_files: set[Path] = set()
    try:
        for line in fl_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("#") or line.startswith("+"):
                continue
            # 跳过 -F/-f/+/ 等指令
            if line.startswith("-"):
                continue
            existing_files.add(Path(line).resolve())
    except Exception as e:
        typer.echo(f"Error: read filelist failed: {e}", err=True)
        raise typer.Exit(code=1)

    # 拿 elaboration errors
    try:
        tracer = _build_tracer(filelist=filelist, strict=False, log_level=log_level)
        _ = tracer.build_graph()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None
    elaboration_errors = tracer.get_elaboration_errors()

    # 收集
    result = _build_suggestions(elaboration_errors, project_root, existing_files)

    if json_output:
        indent = 2 if pretty else None
        typer.echo(json.dumps(result, indent=indent, ensure_ascii=False))
        return

    # 文本输出
    typer.echo("=== Fix Imports Report ===\n")
    typer.echo(f"Project root: {project_root}")
    typer.echo(f"Filelist: {filelist}")
    typer.echo(f"Existing files: {len(existing_files)}\n")

    if not result["identifiers"]:
        typer.echo("✅ No UndeclaredIdentifier / UnknownModule errors found.")
        return

    typer.echo("=== Identifiers Needing Fix ===\n")
    for sug in result["identifiers"][:top]:
        icon = "🟢" if sug["fixable"] else "🔴"
        typer.echo(f"{icon} {sug['identifier']} ({sug['count']} error(s))")
        if sug["sample_files"]:
            sample_str = ", ".join(sug["sample_files"][:2])
            if len(sug["sample_files"]) > 2:
                sample_str += f" (+{len(sug['sample_files']) - 2} more)"
            typer.echo(f"    Used in: {sample_str}")
        if sug["fixable"]:
            rel = Path(sug["found_in"]).relative_to(project_root) if Path(sug["found_in"]).is_relative_to(project_root) else sug["found_in"]
            typer.echo(f"    Found in: {rel}")
        else:
            typer.echo("    Found in: (not in project — NaplesPU 自身缺定义或宏/系统函数)")

    if len(result["identifiers"]) > top:
        typer.echo(f"\n... ({len(result['identifiers']) - top} more not shown, use --top to increase)")

    typer.echo("\n=== Summary ===")
    typer.echo(f"  🟢 Fixable: {result['fixable_count']} identifier(s)  (扫到了定义文件)")
    typer.echo(f"  🔴 Not in project: {result['unfixable_count']} identifier(s)  (项目本身缺定义 / 宏 / 系统函数)")

    # 写新 filelist
    fixable = [s for s in result["identifiers"] if s["fixable"]]
    if fixable and write:
        try:
            new_files = []
            seen = set()
            for s in fixable:
                fp = Path(s["found_in"])
                if fp not in seen and fp not in existing_files:
                    new_files.append(fp)
                    seen.add(fp)
            # 追加到原 filelist
            with open(write, "w") as f:
                f.write("# Generated by sv_query fix imports\n")
                f.write(f"# Project: {project_root}\n")
                f.write(f"# Added {len(new_files)} file(s) to fix {len(fixable)} identifier(s)\n\n")
                f.write(fl_path.read_text(encoding="utf-8"))
                f.write("\n\n# === Auto-added by fix imports ===\n")
                for fp in new_files:
                    f.write(f"{fp}\n")
            typer.echo(f"\n✅ Wrote new filelist: {write}")
            typer.echo(f"   Added {len(new_files)} file(s):")
            for fp in new_files[:top]:
                rel = fp.relative_to(project_root) if fp.is_relative_to(project_root) else fp
                typer.echo(f"     + {rel}")
            if len(new_files) > top:
                typer.echo(f"     ... ({len(new_files) - top} more)")
            typer.echo(f"\nNext: 试 `python run_cli.py fix report --filelist {write}` 看剩余错")
        except Exception as e:
            typer.echo(f"\n❌ Write {write} failed: {e}", err=True)
    elif fixable:
        typer.echo("\nNext: 跑 'fix imports --write project_fixed.f' 自动生成新 filelist")
