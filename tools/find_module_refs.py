#!/usr/bin/env python3
"""
find_module_refs.py — 搬模块前/后的引用扫描 (P1b 目录分层专用)

[iter_232 2026-09-09] 起因: 把 `src/cli/commands/*.py` 搬到 `src/cli/exp/**` 时,
两轮 `grep` 都漏了引用形式, 结果全量门禁抓到 17 个红:
  ① `from src.cli.commands import coverage`  ← `from X import Y` 形式 (不是 X.Y)
  ② `open(src/cli/commands/handshake.py)`    ← 测试直接**按路径读源码**做断言
  ③ `Path(__file__).parents[3] / "tools"`     ← 文件里的 __file__ 深度运算 (搬一层即错位)
本工具把这三类一次性扫出来, 作为搬目录的**搬前检查单**。

用法:
    python3 tools/find_module_refs.py cli.commands.coverage            # 逻辑模块名
    python3 tools/find_module_refs.py cli/commands/coverage.py         # 文件路径
    python3 tools/find_module_refs.py cli.exp.verif.coverage --quiet   # 只报计数
退出码: 0 = 无引用; 1 = 有引用 (搬前需同步)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCAN_DIRS = ["src", "sim/tests", "tools"]
SKIP_PARTS = {"__pycache__", "docs/archive", "docs/task_tree/iterations",
              ".git", ".ruff_cache", "node_modules", "sv_query.egg-info"}

# 允许的文档引用 (历史记录不必追改)
DOC_GLOBS = ["docs/*.md", "*.md", "TESTING.md", "AGENTS.md"]


def _skip(p: Path) -> bool:
    s = str(p.relative_to(ROOT))
    return any(part in s for part in SKIP_PARTS)


def build_patterns(module: str, file_path: str | None) -> list[tuple[str, re.Pattern]]:
    """四类引用形式 (每一类都是实测踩过的坑)。"""
    dotted = module.replace("/", ".").replace(".py", "")
    pkg, _, leaf = dotted.rpartition(".")
    pats = [
        ("import-dotted", re.compile(rf"\b{re.escape(dotted)}\b")),
        ("import-from", re.compile(rf"from\s+\S*{re.escape(pkg)}\s+import\s+[^\n]*\b{re.escape(leaf)}\b")),
        ("path-string", re.compile(rf"{re.escape(dotted.replace('.', '/'))}\.py")),
        ("__file__-depth", re.compile(r"__file__[^\n]*(\.parent){2,}|__file__[^\n]*parents\[")),
    ]
    if file_path:
        pats.append(("file-path", re.compile(re.escape(file_path))))
    return pats


def scan(module: str, file_path: str | None) -> list[tuple[str, str, int, str]]:
    pats = build_patterns(module, file_path)
    hits: list[tuple[str, str, int, str]] = []
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or _skip(p):
                continue
            if p.suffix not in (".py", ".sh", ".md", ".txt", ".yaml", ".yml", ".cfg", ".toml"):
                continue
            try:
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            is_cli = str(p.relative_to(ROOT)).startswith("src/cli")
            for lineno, line in enumerate(text.splitlines(), 1):
                for kind, pat in pats:
                    if kind == "__file__-depth" and not is_cli:
                        continue        # 只与 R8 的范围一致 (src/cli/**)
                    if pat.search(line):
                        hits.append((kind, str(p.relative_to(ROOT)), lineno, line.strip()[:100]))
                        break
    # 文档引用 (只报, 供人工判断是否需要更新)
    for g in DOC_GLOBS:
        for p in sorted(ROOT.glob(g)):
            if p.is_file() and not _skip(p):
                for lineno, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
                    if pats[2][1].search(line) or pats[0][1].search(line):
                        hits.append(("doc", str(p.relative_to(ROOT)), lineno, line.strip()[:100]))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="搬模块前的引用扫描 (iter_232)")
    ap.add_argument("target", help="逻辑模块名 (cli.commands.coverage) 或文件路径 (cli/commands/coverage.py)")
    ap.add_argument("--quiet", "-q", action="store_true", help="只输出计数")
    args = ap.parse_args()

    module = args.target
    file_path = None
    if module.endswith(".py") or "/" in module:
        file_path = module
        module = module[len("src/"):] if module.startswith("src/") else module
        module = module.replace("/", ".")[:-3]

    hits = scan(module, file_path)
    if args.quiet:
        print(f"{module}: {len(hits)} 处引用")
        return 1 if hits else 0

    print(f"=== {module} 的引用 ({len(hits)} 处) ===")
    by_kind: dict[str, list] = {}
    for kind, f, ln, line in hits:
        by_kind.setdefault(kind, []).append((f, ln, line))
    for kind, items in sorted(by_kind.items()):
        print(f"\n[{kind}] {len(items)} 处")
        for f, ln, line in items[:30]:
            print(f"   {f}:{ln}  {line}")
        if len(items) > 30:
            print(f"   ... 还有 {len(items) - 30} 处")
    print("\n提示: `import-from` / `path-string` / `doc` 三类最容易被普通 grep 漏掉;")
    print("      `__file__-depth` 出现即意味着该文件搬一层就会错位 (见 cli/_paths.py, R8)。")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
