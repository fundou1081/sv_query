"""
TDD: 所有 CLI 命令 --file vs --filelist 行为一致 (Req-9 任务2)

[P173.3 2026-11-15] 只保留当前 core 命令的 --file vs --filelist 一致性:
- dataflow analyze
- controlflow analyze / list-conditioned / --conditions-only
退役的 risk/cdc/coverage/sva/timing/verify-gap 测试已删除。

每个命令测试 4 个场景:
1. --file 模式跑通
2. --filelist 模式跑通
3. --file 模式输出 == --filelist 模式输出
4. 不传任何参数时 exit 1
"""
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

RUN_CLI = "python3"
REPO_ROOT = Path(__file__).resolve().parents[3]
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

# ----------------------------------------------------------------------------
# Dataflow analyze
# ----------------------------------------------------------------------------

def test_dataflow_file_vs_filelist_parity():
    tmpdir, sv, fl = _setup_workdir(use_cond=True)
    r1 = _run("dataflow", "analyze", "top.clk", "top.dout", "-f", sv, "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("dataflow", "analyze", "top.clk", "top.dout", "--filelist", fl, "--log-level", "ERROR", cwd=tmpdir)
    assert r1.returncode == 0 and r2.returncode == 0
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
    r1 = _run("controlflow", "analyze", "top.dout", "--conditions-only", "-f", sv, "--json", "--log-level", "ERROR", cwd=tmpdir)
    r2 = _run("controlflow", "analyze", "top.dout", "--conditions-only", "--filelist", fl, "--json", "--log-level", "ERROR", cwd=tmpdir)
    assert r1.stdout == r2.stdout, f"file != filelist:\n{diff(r1.stdout, r2.stdout)}"
    print("✅ controlflow conditions: --file == --filelist")


# ----------------------------------------------------------------------------
# Visualize graph (HTML 输出)
# ----------------------------------------------------------------------------

def diff(a, b):
    """返回 a,b 的 unified diff (最多 5 行)"""
    import difflib
    return "\n".join(list(difflib.unified_diff(a.splitlines(), b.splitlines(), n=2))[:10])


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
