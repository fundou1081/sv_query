#!/usr/bin/env python3
"""
fix_timescale.py - Standalone MissingTimeScale fixer (no CLI overhead)

[ADD 2026-06-12] 跟 `python run_cli.py fix timescale` 等价, 但作为独立 script,
用户可以直接 python tools/fix_timescale.py project.f --apply 调用, 不用依赖
完整 sv_query CLI 启动.

Usage:
    # Dry-run: 看哪些文件会改
    python tools/fix_timescale.py project.f

    # 真改 + 备份
    python tools/fix_timescale.py project.f --apply

    # 自定义 timescale
    python tools/fix_timescale.py project.f --apply --timescale 1ps/1ps

    # 不备份
    python tools/fix_timescale.py project.f --apply --no-backup

适用于:
- CI pipeline: 检测项目是否所有 .sv 都有 timescale
- 一次性大批量修: 项目 scale-up 前的批量修复
- 跨项目: 在多个 SV 项目复用同一修复逻辑
"""
import argparse
import re
import sys
from pathlib import Path

# 让 script 能 import sv_query (假定从 sv_query 仓库根目录跑)
_sv_query_root = Path(__file__).resolve().parent.parent
if str(_sv_query_root / "src") not in sys.path:
    sys.path.insert(0, str(_sv_query_root / "src"))


def _has_timescale(content: str) -> bool:
    head = "\n".join(content.splitlines()[:30])
    return bool(re.search(r"^\s*`?\s*timescale\s+\S+\s*/\s*\S+", head, re.IGNORECASE | re.MULTILINE))


def _insert_timescale(content: str, timescale: str) -> tuple[str, int]:
    """[ADD 2026-06-12] 插 timescale 在 line 1, 返回 (new_content, line_no)"""
    directive = f"`timescale {timescale}\n"
    return directive + content, 1


def find_files_needing_fix(filelist_path: str, include_headers: bool = False):
    """用 sv_query 检测 filelist 里的 MissingTimeScale 错, 返回待修文件列表"""
    from cli._common import _build_tracer
    from collections import defaultdict

    tracer = _build_tracer(filelist=filelist_path, strict=False, log_level="ERROR")
    _ = tracer.build_graph()
    elaboration_errors = tracer.get_elaboration_errors()

    files_to_fix = defaultdict(list)
    for err in elaboration_errors:
        if err.get("code") == "MissingTimeScale":
            file_path = err.get("file", "")
            if file_path and (include_headers or not file_path.endswith(".svh")):
                files_to_fix[file_path].append(err)
    return dict(files_to_fix)


def main():
    parser = argparse.ArgumentParser(
        description="自动修复 MissingTimeScale 错误",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("filelist", help="Path to filelist (.f/.fl)")
    parser.add_argument("--apply", action="store_true", help="真改文件 (默认 dry-run)")
    parser.add_argument("--timescale", default="1ns/1ps", help="Timescale directive (默认 1ns/1ps)")
    parser.add_argument("--include-headers", action="store_true", help="也修 .svh 头文件")
    parser.add_argument("--backup", action=argparse.BooleanOptionalAction, default=True, help="改前备份原文件 (.bak)")
    args = parser.parse_args()

    if not Path(args.filelist).exists():
        print(f"Error: filelist not found: {args.filelist}", file=sys.stderr)
        sys.exit(1)

    files_to_fix = find_files_needing_fix(args.filelist, args.include_headers)
    if not files_to_fix:
        print("✅ No MissingTimeScale errors found. Nothing to fix.")
        sys.exit(0)

    if not args.apply:
        print(f"[DRY-RUN] Would insert `timescale {args.timescale}` into {len(files_to_fix)} file(s):\n")
        for fpath, errs in files_to_fix.items():
            lines = sorted({e["line"] for e in errs})
            print(f"  {fpath}")
            print(f"    lines with error: {lines[:5]}{'...' if len(lines) > 5 else ''}")
        print(f"\nRun with --apply to actually modify these files.")
        sys.exit(0)

    # 真改
    print(f"Applying `timescale {args.timescale}` to {len(files_to_fix)} file(s)...\n")
    fixed = 0
    skipped = 0
    for fpath, _ in files_to_fix.items():
        try:
            content = Path(fpath).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  ❌ {fpath}: read failed ({e})")
            continue

        if _has_timescale(content):
            print(f"  ⏭  {fpath}: already has timescale, skipped")
            skipped += 1
            continue

        new_content, line_no = _insert_timescale(content, args.timescale)

        if args.backup:
            try:
                Path(fpath + ".bak").write_text(content, encoding="utf-8")
            except Exception as e:
                print(f"  ⚠️  {fpath}: backup failed ({e}), continue anyway")

        try:
            Path(fpath).write_text(new_content, encoding="utf-8")
            print(f"  ✅ {fpath}: inserted `timescale {args.timescale}` at line {line_no}")
            fixed += 1
        except Exception as e:
            print(f"  ❌ {fpath}: write failed ({e})")

    print(f"\nDone: {fixed} fixed, {skipped} skipped (already has timescale).")
    if args.backup and fixed > 0:
        print(f"Original files backed up to *.bak")
    sys.exit(0)


if __name__ == "__main__":
    main()
