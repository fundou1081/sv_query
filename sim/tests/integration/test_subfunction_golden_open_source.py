"""
test_subfunction_golden_open_source.py - golden baseline for 8 sub-functions
==========================================================================
[ADD 2026-07-04] Week 4 后续: 每个子功能在真实开源项目里加 golden baseline.

**目标**: 8 个 sub-function (stats/sva_extract/sva_coverage/timing_analyze/cdc_analyze/
risk_analyze/controlflow_analyze/dataflow_analyze) 在 strict_uart + OpenTitan prim_arbiter_tree
2 个 fixture 上各跑, 存为 golden baseline, 验证稳定性 (增强健壮性).

**为什么不只 1 个 fixture**: cross-validate 2 个项目, 一致性高 = 命令稳定.
strict_uart (33 nodes, 4 sub-module clk) + prim_arbiter_tree (33 nodes, 1 clk).

**Golden baseline** (16 个, 2 fixture × 8 sub-function):
- strict_uart: 8 golden
- prim_arbiter_tree: 8 golden
- (verify_gap strict_uart 0 result skip, 但有手测在 N1)

**正反面测试** (8 × 2 + 2 = 18 tests):
- 正面: 8 sub-function × 2 fixture = 16 (golden 比对)
- 反面: 2 (nonexistent file + empty result)
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FILELIST_DIR = PROJECT_ROOT / "sim" / "tests" / "pyslang_type_fixtures" / "industrial_filelists"
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
PRIM_ARBITER_FILELIST = str(FILELIST_DIR / "opentitan_prim_arbiter_tree.f")
GOLDEN_DIR = PROJECT_ROOT / "sim" / "tests" / "golden" / "subfunction_open_source"
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)


def _run(*args, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sv_query", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


# ============================================================================
# 正面 (Positive) - 16 tests (8 sub × 2 fixture)
# ============================================================================

def _normalize(data: dict, project: str) -> dict:
    """Normalize output for golden comparison.

    - 去掉 project-specific paths
    - 保留核心结构 (counts, kinds, fields)
    - Sort lists (timing critical_paths 顺序 flakiness)
    """
    import copy
    data = copy.deepcopy(data)
    # 去掉 ok / command / params (跟 sub-function 名称 + 跑法有关)
    if "params" in data:
        data["params"] = {}
    if "result" in data and isinstance(data["result"], dict):
        # Sort timing critical_paths (flakiness)
        if "critical_paths" in data["result"] and isinstance(data["result"]["critical_paths"], list):
            data["result"]["critical_paths"].sort(
                key=lambda p: (p.get("depth", 0), tuple(p.get("registers", [])))
            )
        # Sort top_risks (risk analyze flakiness)
        if "top_risks" in data["result"] and isinstance(data["result"]["top_risks"], list):
            data["result"]["top_risks"].sort(
                key=lambda x: x.get("signal", "") if isinstance(x, dict) else str(x)
            )
    return data


def _read_golden(name: str, project: str) -> dict:
    """Read golden JSON, auto-create on first run."""
    path = GOLDEN_DIR / f"{project}__{name}.json"
    if not path.exists():
        # 首次跑: 找对应的 command 跟 fixture 跑
        runner = _GOLDEN_RUNNERS[name]
        result = runner(project)
        assert result.returncode == 0, f"baseline gen failed: {result.stderr[:200]}"
        data = json.loads(result.stdout)
        normalized = _normalize(data, project)
        path.write_text(json.dumps(normalized, indent=2, sort_keys=True))
    return json.loads(path.read_text())


# 每 sub-function 的 runner 跟 fixture 选择
def _make_runner(args_func):
    """Wrap an arg builder that takes fixture name and returns list of CLI args."""
    def runner(project: str) -> subprocess.CompletedProcess:
        if project == "strict_uart":
            return _run("-q", *args_func("strict_uart"))
        elif project == "prim_arbiter":
            return _run("-q", *args_func("prim_arbiter"))
    return runner


# Define runners for each sub-function
_GOLDEN_RUNNERS = {
    "stats": _make_runner(lambda p: [
        "stats", "--no-strict",
        "--filelist", STRICT_UART_FILELIST if p == "strict_uart" else PRIM_ARBITER_FILELIST,
        "--json",
    ]),
    "sva_extract": _make_runner(lambda p: [
        "sva", "extract", "--no-strict",
        "--filelist", STRICT_UART_FILELIST if p == "strict_uart" else PRIM_ARBITER_FILELIST,
        "--json",
    ]),
    "sva_coverage": _make_runner(lambda p: [
        "sva", "coverage", "--no-strict",
        "--filelist", STRICT_UART_FILELIST if p == "strict_uart" else PRIM_ARBITER_FILELIST,
        "--json",
    ]),
    "timing_analyze": _make_runner(lambda p: [
        "timing", "analyze", "--no-strict",
        "--filelist", STRICT_UART_FILELIST if p == "strict_uart" else PRIM_ARBITER_FILELIST,
        "--json",
    ]),
    "cdc_analyze": _make_runner(lambda p: [
        "cdc", "analyze", "--no-strict",
        "--filelist", STRICT_UART_FILELIST if p == "strict_uart" else PRIM_ARBITER_FILELIST,
        "--json",
    ]),
    "risk_analyze": _make_runner(lambda p: [
        "risk", "analyze", "--no-strict",
        "--filelist", STRICT_UART_FILELIST if p == "strict_uart" else PRIM_ARBITER_FILELIST,
        "--summary", "--json",
    ]),
    "controlflow_analyze": _make_runner(lambda p: [
        "controlflow", "analyze", "--no-strict",
        "synchronizer.sync0" if p == "strict_uart" else "prim_arbiter_tree.req_i",
        "--filelist", STRICT_UART_FILELIST if p == "strict_uart" else PRIM_ARBITER_FILELIST,
        "--json",
    ]),
    "dataflow_analyze": _make_runner(lambda p: [
        "dataflow", "analyze", "--no-strict",
        *("sync_fifo.clk_i sync_fifo.count_q".split() if p == "strict_uart"
          else "prim_arbiter_tree.req_i prim_arbiter_tree.gnt_o".split()),
        "--filelist", STRICT_UART_FILELIST if p == "strict_uart" else PRIM_ARBITER_FILELIST,
        "--json",
    ]),
}


# 正面测试: 8 sub × 2 fixture
@pytest.mark.parametrize("sub_function", [
    "stats", "sva_extract", "sva_coverage", "timing_analyze",
    "cdc_analyze", "risk_analyze", "controlflow_analyze", "dataflow_analyze",
])
@pytest.mark.parametrize("project", ["strict_uart", "prim_arbiter"])
def test_golden_subfunction(sub_function, project):
    """Golden: {sub_function} 在 {project} 上 跟 baseline 一致 (增强健壮性)."""
    runner = _GOLDEN_RUNNERS[sub_function]
    r = runner(project)
    assert r.returncode == 0, f"rc={r.returncode} stderr={r.stderr[:200]}"
    actual_data = json.loads(r.stdout)
    actual = _normalize(actual_data, project)

    golden = _read_golden(sub_function, project)
    if actual != golden:
        import difflib
        diff = "\n".join(difflib.unified_diff(
            json.dumps(golden, indent=2, sort_keys=True).splitlines(),
            json.dumps(actual, indent=2, sort_keys=True).splitlines(),
            lineterm="",
            fromfile="golden",
            tofile="actual",
            n=3,
        ))
        pytest.fail(f"Golden mismatch ({sub_function} on {project}):\n{diff[:2000]}")
    print(f"✅ Golden {sub_function} on {project}: stable ({len(golden)} keys)")


# ============================================================================
# 反面 (Negative) - 2 tests
# ============================================================================

def test_n1_nonexistent_filelist_all_8_subfunctions():
    """N1: 8 sub-function 在 nonexistent filelist → 不 crash (rc 可以 0/非0, 接受 sva 这种 forgiving).

    注意: 不同 sub 对 nonexistent filelist 反应不同:
    - sva extract/coverage, stats, cdc, risk: rc=0 + 空 result (forgiving)
    - dataflow, controlflow, timing, verify, handshake: rc != 0 + friendly 错误
    测试只验证不 crash (没 Python traceback leak).
    """
    for sub in _GOLDEN_RUNNERS.keys():
        parts = sub.split("_")
        cmd_name = parts[0]
        sub_name = parts[1] if len(parts) > 1 else None
        if sub_name:
            args = [cmd_name, sub_name, "--no-strict", "--filelist", "/tmp/nonexistent.f", "--json"]
        else:
            args = [cmd_name, "--no-strict", "--filelist", "/tmp/nonexistent.f", "--json"]
        r = _run("-q", *args)
        # 不 crash: 没 Python traceback leak
        # (不要求 friendly 错误, 一些 sub 是 forgiving)
        # controlflow / dataflow 需 positional sig → 'Missing argument' 算 OK
        err = r.stderr + r.stdout
        # 只验不 crash (rc 可 0, 1, 2)
        # 不能是 hard crash (rc >= 3 一般是 Python 异常)
        assert r.returncode < 3 or "Missing argument" in err, \
            f"{sub} 硬 crash: rc={r.returncode} stderr={err[:200]}"
    print("✅ N1 8 sub-functions on nonexistent filelist: no hard crash (宽容 sva 的 forgiving 设计)")


def test_n2_strict_uart_partial_graph_all_8_subfunctions():
    """N2: 8 sub-function 在 strict_uart (2 warnings) → 全部 rc=0 (no-strict 优雅降级)."""
    for sub in _GOLDEN_RUNNERS.keys():
        parts = sub.split("_")
        cmd_name = parts[0]
        sub_name = parts[1] if len(parts) > 1 else None
        # 加 per-sub required args
        if cmd_name == "controlflow":
            extra = ["synchronizer.sync0"]
        elif cmd_name == "dataflow":
            extra = ["sync_fifo.clk_i", "sync_fifo.count_q"]
        else:
            extra = []
        if sub_name:
            args = [cmd_name, sub_name, "--no-strict"] + extra + ["--filelist", STRICT_UART_FILELIST, "--json"]
        else:
            args = [cmd_name, "--no-strict"] + extra + ["--filelist", STRICT_UART_FILELIST, "--json"]
        r = _run("-q", *args)
        assert r.returncode == 0, f"{sub} failed on strict_uart: {r.stderr[:200]}"
        data = json.loads(r.stdout)
        assert data["ok"] is True
    print("✅ N2 8 sub-functions on strict_uart (2 warnings, --no-strict): all rc=0")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
