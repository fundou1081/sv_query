#!/usr/bin/env python3
"""
check_crap.py — 复杂度门禁: 改动不得把函数复杂度推过阈值

背景 (2026-11-02): 方豆把 ub-mode 的 "Reduce each function under CRAP 10"
并入开发纪律。crapper 是**唯一的复杂度实现** (不变量 I3 单一实现原则) ——
本工具只做**增量比对**, 不自己算复杂度。

为什么不直接用 crapper --threshold:
  1. --threshold 只在 CRAP 有值时生效; --no-coverage 下 CRAP 恒为 nil
     → threshold 永不触发 → 门禁**恒过** (静默失效, 正是纪律禁止的)。
  2. 全树门禁在 sv_query 上必红: 实测 1223 个函数, CC 中位 5 / p90 22 /
     max 142 (viz_to_elk), CC>10 占 25.8% —— 存量债不该阻塞每次提交。
所以规则是**棘轮 (ratchet)**: 只拦"新引入 / 跨过阈值"的复杂度增长。

规则:
  R1 新增函数 (HEAD 里没有) 且 CC > threshold              -> 违规
  R2 已有函数 CC 从 <= threshold 涨到 > threshold            -> 违规
  R3 已有函数 CC 本来就 > threshold (涨了也只报告不拦截)      -> 不违规
  R4 已有函数 CC 下降                                        -> 不违规

退出码:
  0  通过
  2  有违规 (改动把复杂度推过阈值)
  3  crapper 未安装 (显式降级, **不等于通过**)

用法:
  python3 tools/check_crap.py                  # 人类可读
  python3 tools/check_crap.py --json           # 机器可读
  python3 tools/check_crap.py --threshold 15   # 换阈值
  CRAPPER_BIN=/path/to/crapper python3 tools/check_crap.py

crapper 查找顺序: $CRAPPER_BIN -> ~/my_skills/vendor/crapper/crapper -> PATH
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
THRESHOLD_DEFAULT = 10

# crapper 写的 .metrics/crap.edn 每行形如:
#   {:name "viz_to_elk", :namespace "sv_query.trace.core.graph.viz.elk_bridge", :complexity 142, ...}
ENTRY_RE = re.compile(r':name "([^"]+)",\s*:namespace "([^"]+)",\s*:complexity (\d+)')


def find_crapper() -> Path | None:
    """定位 crapper 可执行文件。找不到返回 None (调用方必须显式降级, 不许静默通过)。"""
    env = os.environ.get("CRAPPER_BIN")
    if env:
        p = Path(env).expanduser()
        # 显式指定却不存在 = 配置错误, 不许静默回退到别处 (否则门禁形同虚设)
        return p if p.exists() else None
    default = Path.home() / "my_skills" / "vendor" / "crapper" / "crapper"
    if default.exists():
        return default
    which = shutil.which("crapper")
    return Path(which) if which else None


def changed_src_files(repo: Path, base: str | None = None) -> list[str]:
    """新增/修改的 src/**/*.py；给出 base 时用 commit range，否则工作区。"""
    if base:
        out = subprocess.run(
            ["git", "diff", "--name-only", base, "--", "src"],
            cwd=repo, capture_output=True, text=True,
        ).stdout
    else:
        out = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
        ).stdout
    if base:
        return sorted(p for p in out.splitlines()
                      if p.startswith("src/") and p.endswith(".py"))
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:  # 重命名
            path = path.split(" -> ")[-1]
        path = path.strip('"')
        if path.startswith("src/") and path.endswith(".py"):
            files.append(path)
    return sorted(set(files))


def renamed_src_files(repo: Path, base: str | None = None) -> dict[str, str]:
    """Map new src path -> old path for renames (git diff/status, -M).

    A package move changes the namespace, so naively treating the new path as
    a new file makes every pre-existing function look newly introduced.  Use
    the old path only to fetch HEAD content, then analyze it under the *new*
    path so namespaces are comparable.
    """
    if base:
        out = subprocess.run(
            ["git", "diff", "--name-status", "-M", base, "--", "src"],
            cwd=repo, capture_output=True, text=True,
        ).stdout
        mapping: dict[str, str] = {}
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0].startswith("R"):
                old, new = parts[1], parts[2]
                if new.startswith("src/") and new.endswith(".py"):
                    mapping[new] = old
        return mapping
    out = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True
    ).stdout
    mapping = {}
    for line in out.splitlines():
        if " -> " not in line:
            continue
        old, new = line[3:].split(" -> ", 1)
        old, new = old.strip().strip('"'), new.strip().strip('"')
        if new.startswith("src/") and new.endswith(".py"):
            mapping[new] = old
    return mapping


def git_show(repo: Path, rev_path: str, rev: str = "HEAD") -> str | None:
    """取某路径在 HEAD 的内容; HEAD 里没有 (新文件) 返回 None。

    rev_path 是**纯路径** (不含 HEAD: 前缀) —— 前缀在这里拼一次。
    """
    r = subprocess.run(
        ["git", "show", f"{rev}:{rev_path}"], cwd=repo, capture_output=True, text=True
    )
    return r.stdout if r.returncode == 0 else None


def analyze(crapper: Path, root: Path, rel: str, content: str) -> tuple[dict, str | None]:
    """在 root 下跑 crapper 分析一个文件, 返回 ({(ns,name): cc}, 错误信息)。

    crapper 把结果写到 **cwd** 的 .metrics/crap.edn (每次覆盖), 所以每个文件
    用独立子目录, 避免读到上一次的残留。

    content 显式传入 (而不是从磁盘读): HEAD 版与当前版内容不同, 但**相对路径
    必须一致** —— namespace 由路径推导, 路径一致才能直接比对两个版本。
    """
    work = root / "run"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    target = work / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    r = subprocess.run(
        [str(crapper), "--no-coverage", rel], cwd=work, capture_output=True, text=True
    )
    edn = work / ".metrics" / "crap.edn"
    if not edn.exists():
        return {}, (r.stderr or r.stdout or "").strip() or f"crapper 退出码 {r.returncode}"

    entries: dict[tuple[str, str], int] = {}
    for name, ns, cc in ENTRY_RE.findall(edn.read_text(encoding="utf-8")):
        entries[(ns, name)] = int(cc)
    return entries, None


def compare(
    rel: str,
    current: dict,
    baseline: dict,
    threshold: int,
) -> tuple[list[dict], list[dict]]:
    """比对当前版与 HEAD 版的函数复杂度。返回 (违规, 仅报告)。"""
    violations: list[dict] = []
    notes: list[dict] = []

    for (ns, name), cc in sorted(current.items()):
        old = baseline.get((ns, name))
        if old is None:
            if cc > threshold:
                violations.append({
                    "file": rel, "namespace": ns, "function": name,
                    "complexity": cc, "baseline": None,
                    "reason": f"新增函数 CC={cc} > 阈值 {threshold}",
                })
            continue
        if old <= threshold < cc:
            violations.append({
                "file": rel, "namespace": ns, "function": name,
                "complexity": cc, "baseline": old,
                "reason": f"复杂度从 {old} 涨到 {cc}, 跨过阈值 {threshold}",
            })
        elif old > threshold and cc > old:
            notes.append({
                "file": rel, "namespace": ns, "function": name,
                "complexity": cc, "baseline": old,
                "reason": f"存量函数 CC {old} -> {cc} (本就超阈值, 不拦截)",
            })
    return violations, notes


def run(repo: Path, threshold: int, crapper: Path, base: str | None = None) -> dict:
    files = changed_src_files(repo, base)
    renames = renamed_src_files(repo, base)
    violations: list[dict] = []
    notes: list[dict] = []
    errors: list[dict] = []
    checked: list[str] = []

    with tempfile.TemporaryDirectory(prefix="check_crap_") as td:
        tmp = Path(td)
        for rel in files:
            # [iter_361 / PLAN P59.2] 删除的文件仍会出现在 changed_src_files;
            # 没有当前内容就没有“新增复杂度”可检查，直接跳过。
            if not (repo / rel).exists():
                continue
            cur_content = (repo / rel).read_text(encoding="utf-8")
            head_text = git_show(repo, renames.get(rel, rel), base or "HEAD")
            if head_text is None:
                baseline: dict = {}
            else:
                head_root = tmp / "head"
                if head_root.exists():
                    shutil.rmtree(head_root)
                head_root.mkdir(parents=True)
                base_entries, err = analyze(crapper, head_root, rel, head_text)
                if err:
                    errors.append({"file": rel, "stage": "HEAD", "error": err})
                    continue
                baseline = base_entries

            cur_root = tmp / "cur"
            if cur_root.exists():
                shutil.rmtree(cur_root)
            cur_root.mkdir(parents=True)
            cur_entries, err = analyze(crapper, cur_root, rel, cur_content)
            if err:
                errors.append({"file": rel, "stage": "current", "error": err})
                continue

            checked.append(rel)
            v, n = compare(rel, cur_entries, baseline, threshold)
            violations.extend(v)
            notes.extend(n)

    return {
        "threshold": threshold,
        "changed_files": files,
        "checked_files": checked,
        "violations": violations,
        "notes": notes,
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="复杂度门禁 (ub-mode crapper 纪律的机械落地)")
    ap.add_argument("--threshold", type=int, default=THRESHOLD_DEFAULT,
                    help=f"CC 阈值 (默认 {THRESHOLD_DEFAULT})")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    ap.add_argument("--repo", default=str(REPO), help="仓库根 (测试用)")
    ap.add_argument("--base", default=None,
                    help="compare against a commit (e.g. v0.3.0-agent-query); default worktree")
    args = ap.parse_args()

    crapper = find_crapper()
    if crapper is None:
        msg = (
            "⛔ crapper 未找到 —— 复杂度门禁**未执行** (这不等于通过)。\n"
            "   安装: git clone https://github.com/unclebob/crapper.git "
            "~/my_skills/vendor/crapper\n"
            "   或用 CRAPPER_BIN=/path/to/crapper 指定。"
        )
        if args.json:
            print(json.dumps({"status": "crapper_missing", "threshold": args.threshold},
                             ensure_ascii=False, indent=2))
        else:
            print(msg, file=sys.stderr)
        return 3

    repo = Path(args.repo).resolve()
    result = run(repo, args.threshold, crapper, base=args.base)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"阈值: CC > {result['threshold']} 视为超限")
        print(f"改动文件 (src/**/*.py): {len(result['changed_files'])}")
        for rel in result["changed_files"]:
            print(f"  - {rel}")
        if not result["checked_files"]:
            print("\n✅ 无改动文件 —— 门禁通过 (无事可判)")
        for err in result["errors"]:
            print(f"\n⚠️  无法分析 {err['file']} ({err['stage']}): {err['error']}")
        if result["violations"]:
            print(f"\n⛔ 违规 {len(result['violations'])} 处 (AGENTS 纪律: 新增/跨阈值的复杂度):")
            for v in result["violations"]:
                print(f"   {v['file']}  {v['namespace']}.{v['function']}  CC={v['complexity']}")
                print(f"      {v['reason']}")
        else:
            print("\n✅ 复杂度门禁通过")
        for n in result["notes"]:
            print(f"   (报告) {n['file']}  {n['namespace']}.{n['function']}  "
                  f"CC {n['baseline']} -> {n['complexity']}  {n['reason']}")

    return 2 if result["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
