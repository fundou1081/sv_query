"""
TDD: minimal_3module filelist verification

[User 2026-07-17] Switched from NaplesPU 141-file filelist to minimal_3module fixture
per "如果开源本身有问题, 就只把代码模式独立出来" feedback:
- NaplesPU 141 files cause OOM on 8GB MBA (cannot fully elaborate)
- minimal_3module fixture (top + sub + 2 leaves + synchronizer) compiles cleanly
- All 12 CLI commands verified on minimal filelist without timeout/OOM

Validates 12 CLI commands all run cleanly on multi-file filelist (no crash, no
Python traceback): stats / risk / cdc / sva extract / sva coverage / sva timing /
timing / verify gap / coverage suggest / controlflow / dataflow / visualize.
"""
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI = "python3"
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")

# [User 2026-07-17] Switched from NaplesPU 141-file filelist (caused OOM + 65 partial-AST
# errors) to minimal_3module fixture (3 modules, 0 errors, full elaboration).
# minimal_3module contains: top_minimal, sub_aggregator, leaf_pipeline, leaf_adder,
# synchronizer (CDC pattern from NaplesPU uart). Compiles cleanly in pyslang.
FILELIST_PATH = str(REPO_ROOT / "sim" / "tests" / "fixtures" / "minimal_3module" / "filelist.f")


def _run(*args):
    """运行 CLI. minimal_3module fixture 无 errors, 跑 9 commands 测 integration."""
    return subprocess.run(
        [RUN_CLI, RUN_CLI_PATH, *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )


# ----------------------------------------------------------------------------
# 9 个命令全部跑通
# ----------------------------------------------------------------------------

def test_m01_stats_filelist():
    """stats on minimal_3module filelist (compiles cleanly in pyslang)."""
    r = _run("stats", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0, f"Expected exit 0, got {r.returncode}, stderr={r.stderr[:300]}"
    # minimal_3module has 0 errors (pyslang fully elaborates), so no
    # "elaboration error(s)" message. Just verify total graph built.
    assert "Total nodes:" in r.stdout, f"Expected stats output, got {r.stdout[:300]}"
    print("✅ m01 stats on minimal_3module: clean compile + graph built")


def test_m02_risk_filelist():
    """risk analyze: 真实风险信号统计"""
    r = _run("risk", "analyze", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "CRITICAL" in r.stdout, f"应输出 CRITICAL 风险, stdout={r.stdout[:300]}"
    # 验证没有"编译失败"误报
    assert "编译失败" not in r.stdout, f"risk 不应再报编译失败, stdout={r.stdout[:500]}"
    print("✅ risk analyze on minimal_3module: 风险分析 + 无'编译失败'误报")


def test_m03_cdc_filelist():
    """cdc analyze: CDC 路径分析"""
    r = _run("cdc", "analyze", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "时钟域" in r.stdout or "domain" in r.stdout.lower()
    print("✅ cdc analyze on minimal_3module: 时钟域分析")


def test_m04_sva_extract_filelist():
    """sva extract"""
    r = _run("sva", "extract", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "SVA 提取" in r.stdout
    print("✅ sva extract on minimal_3module: 跑通")


def test_m05_sva_coverage_filelist():
    """sva coverage: 应输出覆盖率, 不应再报'编译失败'"""
    r = _run("sva", "coverage", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "编译失败" not in r.stdout, f"sva coverage 不应报编译失败, stdout={r.stdout[:500]}"
    assert "覆盖率" in r.stdout
    print("✅ sva coverage on minimal_3module: 覆盖率分析 + 无'编译失败'误报")


def test_m06_sva_timing_filelist():
    """sva timing"""
    r = _run("sva", "timing", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    print("✅ sva timing on minimal_3module: 跑通")


def test_m07_timing_filelist():
    """timing analyze: 关键路径"""
    r = _run("timing", "analyze", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "关键路径" in r.stdout or "路径" in r.stdout
    print("✅ timing analyze on minimal_3module: 关键路径分析")


def test_m08_verify_gap_filelist():
    """verify gap: 验证缺口, 不应再报'编译失败'"""
    r = _run("verify", "gap", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "编译失败" not in r.stdout
    assert "高风险缺口" in r.stdout or "缺口" in r.stdout
    print("✅ verify gap on minimal_3module: 高风险缺口 + 无'编译失败'误报")


def test_m09_coverage_suggest_filelist():
    """coverage suggest"""
    r = _run("coverage", "suggest", "--no-strict", "-s", "synchronizer.sync0", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "分解报告" in r.stdout or "atomic" in r.stdout.lower()
    print("✅ coverage suggest on minimal_3module: 跑通")


def test_m10_controlflow_filelist():
    """controlflow analyze: 应正常输出, 不应 traceback"""
    r = _run("controlflow", "analyze", "--no-strict", "synchronizer.sync0", "--filelist", FILELIST_PATH)
    assert r.returncode == 0, f"controlflow 应 exit 0, got {r.returncode}, stderr={r.stderr[:500]}"
    assert "Traceback" not in r.stderr
    assert "ControlFlow" in r.stdout or "Conditional" in r.stdout
    print("✅ controlflow on minimal_3module: 跑通 (无 traceback)")


def test_m11_dataflow_filelist():
    """dataflow analyze: 应正常输出"""
    r = _run("dataflow", "analyze", "--no-strict", "synchronizer.sync0", "synchronizer.data_o", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "Reachable" in r.stdout
    print("✅ dataflow on minimal_3module: 跑通")


def test_m12_visualize_filelist():
    """visualize graph: HTML 应生成, exit 0"""
    out_html = "/tmp/naples_full/viz_test.html"
    r = _run("visualize", "graph", "--no-strict", "--html", out_html, "--filelist", FILELIST_PATH)
    assert r.returncode == 0, f"visualize 应 exit 0, got {r.returncode}, stderr={r.stderr[:500]}"
    import os
    assert os.path.exists(out_html), f"HTML 应生成: {out_html}"
    assert os.path.getsize(out_html) > 1000, f"HTML 应 > 1KB, got {os.path.getsize(out_html)}"
    print(f"✅ visualize on minimal_3module: HTML {os.path.getsize(out_html)} bytes 生成")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_mstats_filelist,
        test_mrisk_filelist,
        test_mcdc_filelist,
        test_msva_extract_filelist,
        test_msva_coverage_filelist,
        test_msva_timing_filelist,
        test_mtiming_filelist,
        test_mverify_gap_filelist,
        test_mcoverage_suggest_filelist,
        test_mcontrolflow_filelist,
        test_mdataflow_filelist,
        test_mvisualize_filelist,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} minimal_3module integration tests passed!")
