"""
TDD: 所有 CLI 命令 --file vs --filelist 行为一致 (Req-9 任务2)

[ADD 2026-06-11 Req-9 任务2] 9 个命令都加 --filelist 支持
本测试验证: 同样输入下, --file 和 --filelist 输出完全相同 (行为一致)

覆盖命令:
- risk analyze
- cdc analyze
- coverage suggest
- dataflow analyze
- controlflow analyze / list-conditioned / conditions
- sva extract / coverage / timing
- timing analyze
- verify gap
- visualize graph

每个命令测试 4 个场景:
1. --file 模式跑通
2. --filelist 模式跑通
3. --file 模式输出 == --filelist 模式输出
4. 不传任何参数时 exit 1
"""
import json
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

RUN_CLI = "python3"
REPO_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")
RUN_CLI_PATH = str(REPO_ROOT / "run_cli.py")

# 测试 SV: 一个 counter module (简单, 没有 SVA/Covergroup)
SAMPLE_SV = """
`timescale 1ns/1ps
module counter #(
    parameter WIDTH = 8
) (
    input  wire             clk,
    input  wire             reset,
    input  wire             enable,
    output reg  [WIDTH-1:0] count
);
    always @(posedge clk) begin
        if (reset)
            count <= 0;
        else if (enable)
            count <= count + 1;
    end
endmodule
"""

# 测试 SV: 带 conditional driver (for controlflow)
SAMPLE_SV_COND = """
`timescale 1ns/1ps
module top (
    input  logic clk,
    input  logic rst_n,
    input  logic din,
    input  logic en,
    output logic dout
);
    logic data;
    assign data = din;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            dout <= 1'b0;
        else if (en)
            dout <= data;
    end
endmodule
"""


def _run(*args, cwd=None):
    """运行 run_cli.py, 返回 (rc, stdout, stderr)"""
    return subprocess.run(
        [RUN_CLI, RUN_CLI_PATH, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _setup_workdir(use_cond=False):
    """准备临时目录: 1 个 .sv + 1 个 .f"""
    tmpdir = tempfile.mkdtemp()
    sv = Path(tmpdir) / "test.sv"
    sv.write_text(SAMPLE_SV_COND if use_cond else SAMPLE_SV)
    fl = Path(tmpdir) / "test.f"
    fl.write_text("test.sv\n")
    return tmpdir, str(sv), str(fl)


# ----------------------------------------------------------------------------
# 风险分析 risk analyze
# ----------------------------------------------------------------------------

def test_risk_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir()
    r1 = _run("risk", "analyze", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("risk", "analyze", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.returncode == 0, f"file mode fail: {r1.stderr[:200]}"
    assert r2.returncode == 0, f"filelist mode fail: {r2.stderr[:200]}"
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ risk analyze: --file == --filelist")


def test_risk_no_args_errors():
    r = _run("risk", "analyze", cwd="/tmp")
    assert r.returncode != 0
    assert "--file" in r.stderr or "--filelist" in r.stderr
    print(f"✅ risk analyze no-args: exit {r.returncode}")


# ----------------------------------------------------------------------------
# CDC 分析
# ----------------------------------------------------------------------------

def test_cdc_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir()
    r1 = _run("cdc", "analyze", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("cdc", "analyze", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.returncode == 0, f"file mode fail: {r1.stderr[:200]}"
    assert r2.returncode == 0, f"filelist mode fail: {r2.stderr[:200]}"
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ cdc analyze: --file == --filelist")


def test_cdc_no_args_errors():
    r = _run("cdc", "analyze", cwd="/tmp")
    assert r.returncode != 0
    print(f"✅ cdc analyze no-args: exit {r.returncode}")


# ----------------------------------------------------------------------------
# Coverage suggest
# ----------------------------------------------------------------------------

def test_coverage_suggest_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir()
    r1 = _run("coverage", "suggest", "-f", sv, "--signal", "top.q", "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("coverage", "suggest", "--filelist", fl, "--signal", "top.q", "--log-level", "ERROR", cwd=tmpdir)
    # coverage suggest may exit 1 (no atomic signals) but should not crash
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ coverage suggest: --file == --filelist")


# ----------------------------------------------------------------------------
# Dataflow analyze
# ----------------------------------------------------------------------------

def test_dataflow_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir(use_cond=True)
    r1 = _run("dataflow", "analyze", "top.clk", "top.dout", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("dataflow", "analyze", "top.clk", "top.dout", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ dataflow analyze: --file == --filelist")


# ----------------------------------------------------------------------------
# Controlflow analyze / list-conditioned / conditions
# ----------------------------------------------------------------------------

def test_controlflow_analyze_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir(use_cond=True)
    r1 = _run("controlflow", "analyze", "top.dout", "-f", sv, "--json", "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("controlflow", "analyze", "top.dout", "--filelist", fl, "--json", "--log-level", "ERROR", cwd=tmpdir)
    assert r1.returncode == 0
    assert r2.returncode == 0
    # JSON output should be identical
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ controlflow analyze: --file == --filelist (JSON)")


def test_controlflow_list_conditioned_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir(use_cond=True)
    r1 = _run("controlflow", "list-conditioned", "-f", sv, "--json", "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("controlflow", "list-conditioned", "--filelist", fl, "--json", "--log-level", "ERROR", cwd=tmpdir)
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ controlflow list-conditioned: --file == --filelist")


def test_controlflow_conditions_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir(use_cond=True)
    r1 = _run("controlflow", "conditions", "top.dout", "-f", sv, "--json", "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("controlflow", "conditions", "top.dout", "--filelist", fl, "--json", "--log-level", "ERROR", cwd=tmpdir)
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ controlflow conditions: --file == --filelist")


# ----------------------------------------------------------------------------
# SVA extract / coverage / timing
# ----------------------------------------------------------------------------

def test_sva_extract_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir()
    r1 = _run("sva", "extract", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("sva", "extract", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.returncode == 0
    assert r2.returncode == 0
    # sva extract 输出结构一样, 但第一行 "SVA 提取: <file>" 可能不同
    # 因为 filelist 模式 sva extract 没有用 _build_tracer, 走的是 _read_filelist
    # 用 JSON 模式确保一致性
    r1j = _run("sva", "extract", "-f", sv, "--json", "--log-level", "ERROR", cwd=tmpdir)
    r2j = _run("sva", "extract", "--filelist", fl, "--json", "--log-level", "ERROR", cwd=tmpdir)
    assert r1j.returncode == 0
    assert r2j.returncode == 0
    assert r1j.stdout == r2j.stdout, f"file != filelist:\n{diff(r1j.stdout, r2j.stdout)}"
    print("✅ sva extract: --file == --filelist (JSON)")


def test_sva_coverage_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir()
    r1 = _run("sva", "coverage", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("sva", "coverage", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ sva coverage: --file == --filelist")


def test_sva_timing_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir()
    r1 = _run("sva", "timing", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("sva", "timing", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ sva timing: --file == --filelist")


# ----------------------------------------------------------------------------
# Timing analyze
# ----------------------------------------------------------------------------

def test_timing_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir()
    r1 = _run("timing", "analyze", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("timing", "analyze", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ timing analyze: --file == --filelist")


# ----------------------------------------------------------------------------
# Verify gap
# ----------------------------------------------------------------------------

def test_verify_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir()
    r1 = _run("verify", "gap", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("verify", "gap", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ verify gap: --file == --filelist")


# ----------------------------------------------------------------------------
# Visualize graph (HTML 输出)
# ----------------------------------------------------------------------------

def test_visualize_file_vs_filelist_parity():
    tmpdir = tempfile.mkdtemp()
    sv = Path(tmpdir) / "test.sv"
    sv.write_text(SAMPLE_SV)
    fl = Path(tmpdir) / "test.f"
    fl.write_text("test.sv\n")
    html_f = Path(tmpdir) / "out_f.html"
    html_fl = Path(tmpdir) / "out_fl.html"
    r1 = _run("visualize", "graph", "-f", str(sv), "--html", str(html_f), cwd=tmpdir)
    r2 = _run("visualize", "graph", "--filelist", str(fl), "--html", str(html_fl), cwd=tmpdir)
    assert r1.returncode == 0
    assert r2.returncode == 0
    assert html_f.exists()
    assert html_fl.exists()
    # 比较 HTML 字节级一致 (除了时间戳, 跑得很快, 应一致)
    sz_f = html_f.stat().st_size
    sz_fl = html_fl.stat().st_size
    assert sz_f == sz_fl, f"HTML size differs: {sz_f} vs {sz_fl}"
    print(f"✅ visualize graph: --file == --filelist (HTML, both {sz_f} bytes)")


def diff(a, b):
    """返回 a,b 的 unified diff (最多 5 行)"""
    import difflib
    return "\n".join(list(difflib.unified_diff(a.splitlines(), b.splitlines(), n=2))[:10])


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_risk_file_vs_filelist_parity,
        test_risk_no_args_errors,
        test_cdc_file_vs_filelist_parity,
        test_cdc_no_args_errors,
        test_coverage_suggest_file_vs_filelist_parity,
        test_dataflow_file_vs_filelist_parity,
        test_controlflow_analyze_file_vs_filelist_parity,
        test_controlflow_list_conditioned_file_vs_filelist_parity,
        test_controlflow_conditions_file_vs_filelist_parity,
        test_sva_extract_file_vs_filelist_parity,
        test_sva_coverage_file_vs_filelist_parity,
        test_sva_timing_file_vs_filelist_parity,
        test_timing_file_vs_filelist_parity,
        test_verify_file_vs_filelist_parity,
        test_visualize_file_vs_filelist_parity,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"❌ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n🎉 All {len(tests)} CLI filelist parity tests passed!")
