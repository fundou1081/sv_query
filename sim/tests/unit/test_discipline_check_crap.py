"""
test_discipline_check_crap.py — [P57] 复杂度门禁 (tools/check_crap.py) 的机械保障

背景 (2026-11-02): 方豆把 ub-mode 的 "Reduce each function under CRAP 10"
并入 sv_query 纪律。sv_query 现状实测 1223 个函数 / CC 中位 5 / p90 22 /
max 142 —— 全树门禁必红, 所以落地为**棘轮 (ratchet)**: 只拦新增的、以及从
阈值下方涨过阈值的复杂度。

三层保证:
  1. 纯逻辑层: compare() 的四条规则逐条锁死 (**不依赖 crapper**, CI 也能跑);
  2. 集成层: 真实仓库当前无违规 (需 crapper, 缺则显式 skip);
  3. 显式降级: crapper 缺失时退出码是 3 (**未执行, 不等于通过**)。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
CHECKER = REPO / "tools" / "check_crap.py"

sys.path.insert(0, str(REPO / "tools"))
import check_crap as cc  # noqa: E402

CRAPPER = cc.find_crapper()
needs_crapper = pytest.mark.skipif(
    CRAPPER is None,
    reason="crapper 未安装 (~/my_skills/vendor/crapper) —— 集成测试显式跳过",
)


# ---------------------------------------------------------------- 纯逻辑层

def _k(ns, fn):
    """函数的比对键 —— namespace + name (与 crapper 的 EDN 一致)。"""
    return (ns, fn)


def test_compare_flags_new_function_over_threshold():
    """新增函数 CC 超阈值 -> 违规 (R1)。"""
    violations, notes = cc.compare(
        "src/a.py", {_k("a", "new_fn"): 15}, {}, threshold=10
    )
    assert len(violations) == 1, violations
    assert violations[0]["baseline"] is None
    assert "新增函数" in violations[0]["reason"]


def test_compare_allows_new_function_under_threshold():
    """新增函数 CC 未超阈值 -> 不违规。"""
    violations, _ = cc.compare(
        "src/a.py", {_k("a", "new_fn"): 5}, {}, threshold=10
    )
    assert not violations


def test_compare_flags_existing_function_crossing_threshold():
    """已有函数从阈值下方涨过阈值 -> 违规 (R2)。"""
    violations, _ = cc.compare(
        "src/a.py", {_k("a", "fn"): 13}, {_k("a", "fn"): 1}, threshold=10
    )
    assert len(violations) == 1, violations
    assert violations[0]["baseline"] == 1
    assert violations[0]["complexity"] == 13
    assert "跨过阈值" in violations[0]["reason"]


def test_compare_allows_existing_function_staying_under_threshold():
    """已有函数涨了但仍在阈值内 -> 不违规。"""
    violations, _ = cc.compare(
        "src/a.py", {_k("a", "fn"): 9}, {_k("a", "fn"): 1}, threshold=10
    )
    assert not violations


def test_compare_reports_but_does_not_block_preexisting_over_threshold():
    """存量函数本就超阈值 -> 只报告不拦截 (R3), 否则门禁永远红。"""
    violations, notes = cc.compare(
        "src/a.py", {_k("a", "legacy"): 142}, {_k("a", "legacy"): 140}, threshold=10
    )
    assert not violations, "存量超阈值函数不该被拦截"
    assert len(notes) == 1, notes
    assert notes[0]["baseline"] == 140


def test_compare_allows_complexity_reduction():
    """复杂度下降 -> 不违规 (R4)。"""
    violations, notes = cc.compare(
        "src/a.py", {_k("a", "fn"): 3}, {_k("a", "fn"): 12}, threshold=10
    )
    assert not violations
    assert not notes


# ---------------------------------------------------------------- 显式降级

def test_missing_crapper_exits_3_not_zero():
    """crapper 不可用 -> 退出码 3。**不是 0** —— 未执行不等于通过。"""
    env = dict(os.environ, CRAPPER_BIN="/nonexistent/crapper")
    r = subprocess.run(
        [sys.executable, str(CHECKER)], cwd=REPO, capture_output=True, text=True, env=env
    )
    assert r.returncode == 3, (
        f"crapper 缺失时应退出 3 (未执行), 实际 {r.returncode}: {r.stdout}{r.stderr}"
    )
    assert "未执行" in (r.stdout + r.stderr)


# ---------------------------------------------------------------- 集成层

@needs_crapper
def test_repo_currently_has_no_complexity_violation():
    """仓库当前状态 = 0 违规 (跑真实检查器, 不是 import 后自证)。"""
    r = subprocess.run(
        [sys.executable, str(CHECKER)], cwd=REPO, capture_output=True, text=True
    )
    assert r.returncode == 0, (
        f"check_crap.py 报违规 (AGENTS 纪律: 新增/跨阈值的复杂度):\n{r.stdout}\n{r.stderr}"
    )


@needs_crapper
def test_checker_detects_violation_in_a_real_repo(tmp_path):
    """检查器在真实 git 仓库里能检出违规 (自检: 否则它是摆设)。"""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    (repo / "src" / "mod.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    git("add", "src/mod.py")
    git("commit", "-qm", "init")

    # 新增一个高 CC 函数
    (repo / "src" / "mod.py").write_text(
        "def f(x):\n"
        + "".join(f"    if x > {i}:\n        x += {i}\n" for i in range(14))
        + "    return x\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(CHECKER), "--repo", str(repo)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert r.returncode == 2, (
        f"检查器漏掉了高 CC 新增函数: {r.stdout}{r.stderr}"
    )
    assert "违规" in r.stdout
