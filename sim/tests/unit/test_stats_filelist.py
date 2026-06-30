"""
TDD: stats --filelist 支持 (Req-9)

[ADD 2026-06-11 Req-9] stats 命令加 --filelist 参数支持多文件项目
- 单文件模式 (-f) 保持不变
- filelist 模式 (--filelist .f/.fl) 加载多文件建图
- 走 _build_tracer helper, elaboration error 统一 catch
- 修 _read_filelist 用 cwd 作 base_dir (filelist 相对项目根)
"""
import os
import subprocess
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, "src")


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


def test_stats_with_file_still_works():
    """stats -f 旧接口不变"""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".sv", delete=False, mode="w") as f:
        f.write(SAMPLE_SV)
        path = f.name
    try:
        r = subprocess.run(
            ["python3", "/Users/fundou/my_dv_proj/sv_query/run_cli.py", "stats", "-f", path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0, f"应 exit 0, 实际 {r.returncode}, stderr={r.stderr[:500]}"
        assert "Total nodes" in r.stdout
        assert "Total edges" in r.stdout
        print("✅ stats -f 单文件模式工作 (exit 0)")
    finally:
        os.unlink(path)


def test_stats_with_filelist_loads_all_files():
    """stats --filelist 加载多文件"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        # 写 2 个互相 instance 的 sv
        leaf_path = Path(tmpdir) / "leaf.sv"
        leaf_path.write_text(
            """
`timescale 1ns/1ps
module leaf_mod(
    input wire a,
    output wire y
);
    assign y = a;
endmodule
"""
        )
        top_path = Path(tmpdir) / "top.sv"
        top_path.write_text(
            """
`timescale 1ns/1ps
module top_mod(
    input wire in_sig,
    output wire out_sig
);
    leaf_mod u_leaf (.a(in_sig), .y(out_sig));
endmodule
"""
        )
        filelist_path = Path(tmpdir) / "files.f"
        filelist_path.write_text("leaf.sv\ntop.sv\n")

        # 跑 stats --filelist (cwd 是 tmpdir)
        r = subprocess.run(
            [
                "python3",
                "/Users/fundou/my_dv_proj/sv_query/run_cli.py",
                "stats",
                "--filelist",
                str(filelist_path),
            ],
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=60,
        )
        assert r.returncode == 0, f"应 exit 0, 实际 {r.returncode}, stderr={r.stderr[:500]}"
        assert "Total nodes" in r.stdout
        # 至少应该比单文件多 (2 个 module + 一些 PORT)
        assert r.stdout.count("Total nodes") == 1
        # 提取 Total nodes 后的数字
        import re
        m = re.search(r"Total nodes:\s*(\d+)", r.stdout)
        assert m, f"应能 extract node count from: {r.stdout[:300]}"
        n_nodes = int(m.group(1))
        assert n_nodes > 5, f"应 > 5 节点 (2 module + ports), 实际 {n_nodes}"
        print(f"✅ stats --filelist 多文件模式: {n_nodes} nodes")


def test_stats_filelist_does_not_require_file():
    """stats 不传 -f 也能跑 filelist"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        sv_path = Path(tmpdir) / "x.sv"
        sv_path.write_text(SAMPLE_SV)
        filelist = Path(tmpdir) / "x.f"
        filelist.write_text("x.sv\n")
        r = subprocess.run(
            [
                "python3",
                "/Users/fundou/my_dv_proj/sv_query/run_cli.py",
                "stats",
                "--filelist",
                str(filelist),
            ],
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=60,
        )
        assert r.returncode == 0, f"应 exit 0 (无 -f), 实际 {r.returncode}, stderr={r.stderr[:500]}"
        assert "Error: --file or --filelist is required" not in r.stderr
        print("✅ stats --filelist 不要求 --file")


def test_stats_without_file_or_filelist_errors():
    """stats 不传任何参数应报错 exit 1"""
    r = subprocess.run(
        ["python3", "/Users/fundou/my_dv_proj/sv_query/run_cli.py", "stats"],
        capture_output=True,
        text=True,
        cwd="/tmp",
        timeout=30,
    )
    assert r.returncode != 0, f"应 fail, 实际 exit {r.returncode}"
    assert "--file" in r.stderr or "--filelist" in r.stderr
    print(f"✅ stats 无参数正确 exit {r.returncode}")


def test_stats_filelist_in_params_json():
    """stats --json 输出 params 包含 filelist 字段"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        sv_path = Path(tmpdir) / "y.sv"
        sv_path.write_text(SAMPLE_SV)
        filelist = Path(tmpdir) / "y.f"
        filelist.write_text("y.sv\n")
        r = subprocess.run(
            [
                "python3",
                "/Users/fundou/my_dv_proj/sv_query/run_cli.py",
                "stats",
                "--filelist",
                str(filelist),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=tmpdir,
            timeout=60,
        )
        assert r.returncode == 0
        import json
        data = json.loads(r.stdout)
        assert "filelist" in data["params"], f"params 应有 filelist: {data['params']}"
        assert data["params"]["filelist"] == str(filelist)
        print(f"✅ stats --json 输出 params.filelist = {data['params']['filelist']}")


if __name__ == "__main__":
    test_stats_with_file_still_works()
    test_stats_with_filelist_loads_all_files()
    test_stats_filelist_does_not_require_file()
    test_stats_without_file_or_filelist_errors()
    test_stats_filelist_in_params_json()
    print("\n🎉 All stats filelist tests passed!")
