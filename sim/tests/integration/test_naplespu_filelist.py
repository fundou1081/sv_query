"""
TDD: NaplesPU 141 个 .sv 文件 filelist 验证 (Req-15)

[ADD 2026-06-12 Req-15] 验证 Req-9/10/11/12/13/14 修复在真实项目上是否有效.

NaplesPU 测试对象: 141 个 .sv 文件, 65 个 elaboration errors
                  (MissingTimeScale, UndeclaredIdentifier, TooFewArguments 等)

预期: 9 个 CLI 命令都能在 filelist 模式跑通, 不 crash, 不暴露 Python traceback.
"""
import json
import subprocess
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI = "python3"
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")

# 完整 141 .sv (排除 test_/tb_ 避免 simulator-specific 文件)
NAPLESPU_ROOT = "/Users/fundou/my_dv_proj/NaplesPU/NaplesPU"
FILELIST_PATH = "/tmp/naples_full/all.f"

# 生成 filelist (如果不存在)
import os
if not os.path.exists(FILELIST_PATH):
    os.makedirs(os.path.dirname(FILELIST_PATH), exist_ok=True)
    with open(FILELIST_PATH, "w") as f:
        subprocess.run(
            ["find", f"{NAPLESPU_ROOT}/src", "-name", "*.sv"],
            stdout=f,
        )
    # 排除测试文件
    subprocess.run(
        f"grep -v 'test_\\|tb_' {FILELIST_PATH} > /tmp/_f && mv /tmp/_f {FILELIST_PATH}",
        shell=True,
    )


def _run(*args):
    """运行命令. NaplesPU 有 65 errors, 需逐个传 --no-strict 在子命令后"""
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

def test_naplespu_stats_filelist():
    """stats 在 NaplesPU 141 文件跑通 partial result"""
    r = _run("stats", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0, f"应 exit 0, got {r.returncode}, stderr={r.stderr[:300]}"
    assert "elaboration error(s)" in r.stdout, f"应输出 error count, stdout={r.stdout[:300]}"
    assert "partial graph shown" in r.stdout
    print("✅ stats on NaplesPU 141 files: partial result + 65 error count")


def test_naplespu_risk_filelist():
    """risk analyze: 真实风险信号统计"""
    r = _run("risk", "analyze", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "CRITICAL" in r.stdout, f"应输出 CRITICAL 风险, stdout={r.stdout[:300]}"
    # 验证没有"编译失败"误报
    assert "编译失败" not in r.stdout, f"risk 不应再报编译失败, stdout={r.stdout[:500]}"
    print("✅ risk analyze on NaplesPU: 风险分析 + 无'编译失败'误报")


def test_naplespu_cdc_filelist():
    """cdc analyze: CDC 路径分析"""
    r = _run("cdc", "analyze", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "时钟域" in r.stdout or "domain" in r.stdout.lower()
    print("✅ cdc analyze on NaplesPU: 时钟域分析")


def test_naplespu_sva_extract_filelist():
    """sva extract"""
    r = _run("sva", "extract", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "SVA 提取" in r.stdout
    print("✅ sva extract on NaplesPU: 跑通")


def test_naplespu_sva_coverage_filelist():
    """sva coverage: 应输出覆盖率, 不应再报'编译失败'"""
    r = _run("sva", "coverage", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "编译失败" not in r.stdout, f"sva coverage 不应报编译失败, stdout={r.stdout[:500]}"
    assert "覆盖率" in r.stdout
    print("✅ sva coverage on NaplesPU: 覆盖率分析 + 无'编译失败'误报")


def test_naplespu_sva_timing_filelist():
    """sva timing"""
    r = _run("sva", "timing", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    print("✅ sva timing on NaplesPU: 跑通")


def test_naplespu_timing_filelist():
    """timing analyze: 关键路径"""
    r = _run("timing", "analyze", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "关键路径" in r.stdout or "路径" in r.stdout
    print("✅ timing analyze on NaplesPU: 关键路径分析")


def test_naplespu_verify_gap_filelist():
    """verify gap: 验证缺口, 不应再报'编译失败'"""
    r = _run("verify", "gap", "--no-strict", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "编译失败" not in r.stdout
    assert "高风险缺口" in r.stdout or "缺口" in r.stdout
    print("✅ verify gap on NaplesPU: 高风险缺口 + 无'编译失败'误报")


def test_naplespu_coverage_suggest_filelist():
    """coverage suggest"""
    r = _run("coverage", "suggest", "--no-strict", "-s", "synchronizer.sync0", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "分解报告" in r.stdout or "atomic" in r.stdout.lower()
    print("✅ coverage suggest on NaplesPU: 跑通")


def test_naplespu_controlflow_filelist():
    """controlflow analyze: 应正常输出, 不应 traceback"""
    r = _run("controlflow", "analyze", "--no-strict", "synchronizer.sync0", "--filelist", FILELIST_PATH)
    assert r.returncode == 0, f"controlflow 应 exit 0, got {r.returncode}, stderr={r.stderr[:500]}"
    assert "Traceback" not in r.stderr
    assert "ControlFlow" in r.stdout or "Conditional" in r.stdout
    print("✅ controlflow on NaplesPU: 跑通 (无 traceback)")


def test_naplespu_dataflow_filelist():
    """dataflow analyze: 应正常输出"""
    r = _run("dataflow", "analyze", "--no-strict", "synchronizer.sync0", "synchronizer.data_o", "--filelist", FILELIST_PATH)
    assert r.returncode == 0
    assert "Reachable" in r.stdout
    print("✅ dataflow on NaplesPU: 跑通")


def test_naplespu_visualize_filelist():
    """visualize graph: HTML 应生成, exit 0"""
    out_html = "/tmp/naples_full/viz_test.html"
    r = _run("visualize", "graph", "--no-strict", "--html", out_html, "--filelist", FILELIST_PATH)
    assert r.returncode == 0, f"visualize 应 exit 0, got {r.returncode}, stderr={r.stderr[:500]}"
    import os
    assert os.path.exists(out_html), f"HTML 应生成: {out_html}"
    assert os.path.getsize(out_html) > 1000, f"HTML 应 > 1KB, got {os.path.getsize(out_html)}"
    print(f"✅ visualize on NaplesPU: HTML {os.path.getsize(out_html)} bytes 生成")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_naplespu_stats_filelist,
        test_naplespu_risk_filelist,
        test_naplespu_cdc_filelist,
        test_naplespu_sva_extract_filelist,
        test_naplespu_sva_coverage_filelist,
        test_naplespu_sva_timing_filelist,
        test_naplespu_timing_filelist,
        test_naplespu_verify_gap_filelist,
        test_naplespu_coverage_suggest_filelist,
        test_naplespu_controlflow_filelist,
        test_naplespu_dataflow_filelist,
        test_naplespu_visualize_filelist,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} NaplesPU integration tests passed!")
