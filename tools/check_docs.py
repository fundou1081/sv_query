#!/usr/bin/env python3
# check_docs.py — 文档卫生检查 (iter_171, 方豆 "先把文档清理")
#
# 检查项 (非 0 退出 = 有问题):
#   1. 死链: md 内的相对 .md 链接目标不存在
#   2. 归档越界: 非 docs/archive/ 的文档引用被归档的路径 (应更新或指向索引)
#   3. 索引登记: docs/ 下 (非 archive/) 的 .md 未登记在 docs/INDEX.md
#   4. 陈旧计数: 文档里出现与 docs/INDEX.md 基准不符的 "N passed/测试" 硬编码
#      (仅警告, 需人工确认 — 计数会漂移, 以 INDEX.md 单一真相源为准)
#
# 用法: python3 tools/check_docs.py [--strict]
import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
ARCHIVE = DOCS / "archive"
INDEX = DOCS / "INDEX.md"

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache"}


def iter_md():
    for p in REPO.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def check_links():
    dead = []
    for md in iter_md():
        txt = md.read_text(encoding="utf-8", errors="ignore")
        for _label, target in LINK_RE.findall(txt):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = target.split("#", 1)[0]
            if not target or not target.endswith(".md"):
                continue  # 仅查 .md 链接 (目录/代码块内的伪链接不算)
            resolved = (md.parent / target).resolve()
            if not resolved.exists():
                dead.append((md.relative_to(REPO), target))
    return dead


def check_archive_refs():
    """非归档文档不应引用归档路径之外的归档内容 (除 archive/README 与历史迭代记录)."""
    bad = []
    for md in iter_md():
        rel = md.relative_to(REPO)
        if any(str(rel).startswith(k) for k in
               ("docs/archive/", "docs/task_tree/iterations/", "memory/")):
            continue  # 归档自身 / 历史迭代记录 / memory 日志 = 快照, 允许
        if rel.name in ("CHANGELOG.md",):
            continue  # 变更日志 = 历史记录, 允许引用归档
        txt = md.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"docs/archive/[A-Za-z0-9_./-]+\.md", txt):
            bad.append((rel, m.group(0)))
    return bad


def check_index_registration():
    """docs/ 下非 archive/task_tree 的文档应在 docs/INDEX.md 登记."""
    if not INDEX.exists():
        return None, ["docs/INDEX.md 不存在"]
    index_txt = INDEX.read_text(encoding="utf-8", errors="ignore")
    missing = []
    for p in sorted(DOCS.rglob("*.md")):
        rel = p.relative_to(DOCS)
        if str(rel).startswith("archive/") or str(rel).startswith("task_tree/"):
            continue
        if rel.name == "INDEX.md" or rel.name == "README.md":
            continue
        if str(rel) not in index_txt and rel.name not in index_txt:
            missing.append(str(rel))
    return index_txt, missing


def check_stale_counts(index_txt, strict=False):
    """文档内硬编码测试计数 vs INDEX.md 基准 (警告级)."""
    if index_txt is None:
        return []
    base = re.findall(r"(\d{3,5})\s*(?:passed|测试)", index_txt)
    base_nums = set(base)
    warn = []
    for md in iter_md():
        rel = md.relative_to(REPO)
        if any(str(rel).startswith(k) for k in
               ("docs/archive/", "docs/task_tree/", "memory/")):
            continue  # 历史快照允许保留当时计数
        if rel.name in ("CHANGELOG.md", "CURRENT_TODO.md", "ARCHITECTURE_TODOLIST.md",
                        "ARCHITECTURE_EVOLUTION.md"):
            continue  # 变更日志 / 滚动日志 / 改造步骤记录 / 演进时间线 = 历史快照
        if str(rel).startswith("docs/refactoring/"):
            continue  # 重构轮快照 (带日期)
        txt = md.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"(\d{3,5})\s*(?:passed|tests?)", txt):
            num = int(m.group(1))
            # 只查"全量级"计数 (>=1000): 分套件计数 (419 passed 等) 属
            # 局部事实, 不在本检查范围; 全量基线必须与 INDEX 一致
            if num < 1000:
                continue
            if m.group(1) not in base_nums:
                warn.append((rel, m.group(0).strip()))
    return warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="警告也视为失败")
    args = ap.parse_args()

    dead = check_links()
    arch = check_archive_refs()
    index_txt, missing = check_index_registration()
    stale = check_stale_counts(index_txt)

    print(f"[1] 死链: {len(dead)}")
    for rel, t in dead[:30]:
        print(f"    {rel} -> {t}")
    print(f"[2] 非归档文档引用归档路径: {len(arch)}")
    for rel, t in arch[:15]:
        print(f"    {rel} -> {t}")
    print(f"[3] 未登记入 docs/INDEX.md: {len(missing)}")
    for m in missing[:30]:
        print(f"    {m}")
    print(f"[4] 计数漂移警告: {len(stale)}")
    for rel, t in stale[:40]:
        print(f"    {rel}: {t}")

    fail = bool(dead or arch or missing) or (args.strict and stale)
    print("\n结果:", "❌ 有问题" if fail else "✅ 通过")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
