"""[iter_234 P2] core/diagnose —— **只读诊断** (原 fix report/widths/imports/timescale)。

分层决定 (方豆 2026-09-09): `sv_query` **不改 RTL**。
因此本目录的命令一律只读 (dry-run/报告), 会写文件的动作移出 CLI:
  - 加 `timescale` (改 .sv) → `tools/fix_timescale.py --apply`
  - 生成新 filelist (--write) → `tools/fix_imports.py --write`
命令名变更: `fix <x>` → 规范名 `diagnose <x>` (老名保留为兼容别名, 见 cli/_registry.py ALIASES)。
"""
from cli._registry import LAYERS

LAYER = LAYERS["core"]
