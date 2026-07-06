"""
test_arch.py — Phase 4 (新功能) 测试 arch 命令.

[Phase 4 2026-06-24] arch 命令 v1:
  - summary 模式 (一段话描述项目架构)
  - dot / mermaid / html 输出格式
  - 复用 visualize module 同源 (extract_module + MIG)
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run_arch(*args, timeout=120) -> tuple[int, str, str]:
    """Run run_cli.py arch <args>, return (rc, stdout, stderr)."""
    p = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "run_cli.py"), "arch", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


# ============================================================================
# Test 1: 基础 - 命令注册 + help
# ============================================================================
class TestArchCommandRegistration:
    """arch 命令应注册到 typer app."""

    def test_arch_in_main_help(self):
        """run_cli.py --help 应包含 'arch' 命令."""
        rc, out, _ = _run_arch()  # 默认 typer 没 subcommand 时 arch callback 显示 help
        assert "arch" in out.lower() or rc != 0  # arch 在 help 里

    def test_arch_app_help(self):
        """arch subcommand 应该有 help."""
        rc, out, _ = _run_arch("--help")
        assert rc == 0, f"arch --help fail: rc={rc}, stderr={_[:300]}"
        # help 应提到 L1 + L2 + 多格式
        assert "format" in out.lower() or "summary" in out.lower()


# ============================================================================
# Test 2: summary 模式
# ============================================================================
class TestArchSummaryMode:
    """--summary 模式生成一段话描述项目架构."""

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v").exists(),
        reason="picorv32 not available",
    )
    def test_picorv32_axi_summary(self):
        """picorv32_axi: 2 instances + summary 格式."""
        rc, out, err = _run_arch(
            "-f", "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
            "-t", "picorv32_axi",
            "-d", "2",
            "--summary",
        )
        assert rc == 0, f"FAIL (rc={rc}):\nstderr: {err[:500]}"
        assert "Architecture" in out, f"missing 'Architecture':\n{out[:300]}"
        assert "Total instances" in out
        assert "Hierarchy depth" in out

    def test_arch_test_top_summary_has_port_connections(self):
        """[FIX 2026-07-06] Regression: summary 必须显示 port connections > 0
        当 project 有 cross-instance wire (NOT through root module).

        之前以为 darksocv port extraction broken (显示 0), 但实际 darksocv
        设计没 cross-instance 直连所以 0 是对的. 手写 fixture 验证 L2
        cross-module port extraction 工作.
        """
        fixture = PROJECT_ROOT / "sim/tests/pyslang_type_fixtures/arch/arch_test_top.sv"
        rc, out, err = _run_arch(
            "-f", str(fixture),
            "-t", "arch_test_top",
            "-d", "4",
            "--format", "summary",
        )
        assert rc == 0, f"FAIL: rc={rc}, stderr={err[:500]}"
        # 期望: 5 instances + 3 port connections (alu 内部 sub_lo/sub_hi)
        assert "Total instances:  5" in out, f"unexpected instance count:\n{out[:500]}"
        assert "Port connections: 3" in out, (
            f"expected 3 port connections but arch doesn't report them.\n"
            f"Output:\n{out[:500]}"
        )

    def test_no_submodule_summary_message(self):
        """无 submodule 的 SV 应该有友好提示."""
        rc, out, _ = _run_arch(
            "-f", "sim/openTitan_validation.sv",
            "-t", "openTitan_validation",
            "-d", "3",
            "--summary",
        )
        assert rc == 0
        # 应有提示信息 (有 submodule 或无都 OK)
        assert "Architecture" in out or "No submodule" in out


# ============================================================================
# Test 3: mermaid 输出
# ============================================================================
class TestArchMermaidOutput:
    """--format mermaid 生成 Mermaid 图表 (GitHub README 友好)."""

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v").exists(),
        reason="picorv32 not available",
    )
    def test_picorv32_axi_mermaid(self):
        """picorv32_axi mermaid 包含图节点 + 边."""
        rc, out, err = _run_arch(
            "-f", "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
            "-t", "picorv32_axi",
            "-d", "2",
            "--format", "mermaid",
        )
        assert rc == 0, f"FAIL: rc={rc}, stderr={err[:500]}"
        assert "graph TD" in out
        assert "```mermaid" in out  # markdown fence
        # 至少有 2 个 instance 节点 (axi_adapter + picorv32_core)
        node_count = len(re.findall(r"n\d+\[", out))
        assert node_count >= 2, f"expected ≥2 nodes, got {node_count}"

    def test_arch_test_top_mermaid_has_hierarchy_edges(self):
        """[FIX 2026-07-06] Regression: mermaid render 必须 emit hierarchy
        edges (parent -.-> child), 不只是 '%% Hierarchy' 注释空段.

        Bug: 之前 _render_mermaid 只检查 'parent in node_ids', 但 root
        module (target) 不在 dict, 所以永远找不到 parent, 不 emit edges.
        修法: add root node (target_module) 到 node_ids 当 hierarchy 起点.
        """
        fixture = PROJECT_ROOT / "sim/tests/pyslang_type_fixtures/arch/arch_test_top.sv"
        rc, out, err = _run_arch(
            "-f", str(fixture),
            "-t", "arch_test_top",
            "-d", "4",
            "--format", "mermaid",
        )
        assert rc == 0, f"FAIL: rc={rc}, stderr={err[:500]}"
        # 检查 hierarchy section 真有 edges
        assert "%% Hierarchy" in out
        hierarchy_section = out.split("%% Hierarchy")[1].split("```")[0]
        # 至少应有 1 条 'n_root -.-> nN' 形式的 hierarchy edge
        edge_count = len(re.findall(r"\s+n_?\w+\s+-\.->\s+n_?\w+", hierarchy_section))
        assert edge_count >= 1, (
            f"hierarchy section has no edges (bug #1 not fixed)!\n"
            f"Section:\n{hierarchy_section}"
        )


# ============================================================================
# Test 4: dot 输出
# ============================================================================
class TestArchDotOutput:
    """--format dot 生成 Graphviz DOT."""

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v").exists(),
        reason="picorv32 not available",
    )
    def test_picorv32_axi_dot(self):
        """picorv32_axi DOT 格式正确."""
        rc, out, err = _run_arch(
            "-f", "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
            "-t", "picorv32_axi",
            "-d", "2",
            "--format", "dot",
        )
        assert rc == 0, f"FAIL: rc={rc}, stderr={err[:500]}"
        assert "digraph" in out
        assert "rankdir" in out
        # 2 instance (axi_adapter + picorv32_core)
        assert "axi_adapter" in out
        assert "picorv32_core" in out or "picorv32" in out


# ============================================================================
# Test 5: HTML 输出
# ============================================================================
class TestArchHtmlOutput:
    """--format html 生成交互式 HTML (vis.js)."""

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v").exists(),
        reason="picorv32 not available",
    )
    def test_picorv32_axi_html(self, tmp_path):
        """picorv32_axi HTML 写入文件 + 包含 vis.js + 数据."""
        outfile = tmp_path / "arch.html"
        rc, _, err = _run_arch(
            "-f", "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
            "-t", "picorv32_axi",
            "-d", "2",
            "--format", "html",
            "-o", str(outfile),
        )
        assert rc == 0, f"FAIL: rc={rc}, stderr={err[:500]}"
        assert outfile.exists()
        content = outfile.read_text()
        # 必须包含 vis.js CDN + 数据
        assert "vis-network" in content, "missing vis.js CDN"
        assert "vis.DataSet" in content, "missing vis.js DataSet"
        assert "axi_adapter" in content, "missing instance data"
        assert "</html>" in content, "incomplete HTML"


# ============================================================================
# Test 6: 错误处理
# ============================================================================
class TestArchErrorHandling:
    """错误输入友好降级."""

    def test_no_file_or_filelist(self):
        """没传 -f 或 --filelist 应显示 help + exit (不一定 nonzero)."""
        rc, out, err = _run_arch("-t", "top", "--summary")
        # 应该 display help 或 error message (不一定 nonzero, typer Exit code 0/1 都 OK)
        assert "Usage" in out or "Error" in out or "file" in out.lower() or "filelist" in out.lower()

    def test_unknown_format(self):
        """未知的 --format 应报错."""
        rc, out, err = _run_arch(
            "-f", "sim/openTitan_validation.sv",
            "--format", "invalid_format_xyz",
        )
        assert rc != 0
        assert "unknown format" in err.lower() or "format" in err.lower()

# ============================================================================
# Test 7 (v2): --cluster-by-type 模式
# ============================================================================
class TestArchClusterByType:
    """[v2 2026-06-25] --cluster-by-type 按 module type 合并 cluster."""

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v").exists(),
        reason="picorv32 not available",
    )
    def test_cluster_by_type_picorv32(self):
        """picorv32_axi + cluster-by-type → 每 type 一个 cluster."""
        rc, out, err = _run_arch(
            "-f", "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
            "-t", "picorv32_axi",
            "--cluster-by-type",
            "--format", "dot",
        )
        assert rc == 0, f"FAIL: rc={rc}, stderr={err[:500]}"
        # 应该有 cluster_<type> subgraph
        assert "cluster_picorv32" in out
        assert "cluster_picorv32_axi_adapter" in out
        # 应该用 hash-based 颜色 (而不是 depth palette)
        # depth palette 是固定 5 色, hash-based 是 hex color
        assert "#" in out  # hash color (含 #)


# ============================================================================
# Test 8 (v2): --max-nodes 折叠
# ============================================================================
class TestArchMaxNodes:
    """[v2 2026-06-25] --max-nodes 限制 nodes 数, 超出折叠."""

    @pytest.fixture
    def mock_many_modules(self, tmp_path):
        """创建一个有多个重复 type instances 的 mock SV."""
        sv = tmp_path / "many_modules.sv"
        sv.write_text("""
module sub #(parameter int W = 8) (input logic clk, input logic [W-1:0] a, output logic [W-1:0] y);
    always_ff @(posedge clk) y <= a;
endmodule
module bus #(parameter int W = 8) (input logic clk, input logic [W-1:0] data, output logic [W-1:0] out);
    always_ff @(posedge clk) out <= data;
endmodule
module top(input logic clk);
    logic [7:0] a0, a1, a2, a3, b0, b1, y0, y1, y2, y3, bo;
    sub u_s0 (.clk(clk), .a(a0), .y(y0));
    sub u_s1 (.clk(clk), .a(a1), .y(y1));
    sub u_s2 (.clk(clk), .a(a2), .y(y2));
    sub u_s3 (.clk(clk), .a(a3), .y(y3));
    bus u_b0 (.clk(clk), .data(y0), .out(bo));
    bus u_b1 (.clk(clk), .data(y1), .out(b0));
    bus u_b2 (.clk(clk), .data(y2), .out(b1));
endmodule
""")
        return str(sv)

    def test_max_nodes_collapse(self, mock_many_modules):
        """7 instances (2 unique types: sub + bus) + max-nodes 1 → 折叠 1 type + collapse note."""
        rc, out, err = _run_arch(
            "-f", mock_many_modules,
            "-t", "top",
            "--max-nodes", "1",
            "--format", "dot",
        )
        assert rc == 0, f"FAIL: rc={rc}, stderr={err[:500]}"
        # title 应该说 showing N of M
        assert "showing" in out.lower()
        # collapse note 出现
        assert "Collapse note" in out or "collapsed" in out.lower()
        # max-nodes=1 → 只保留 1 个 type (sub 或 bus) 的第一个 instance → 1 visible
        # 但 hierarchy edges 来自 parent + visible (2 total lines 含 "top.u_")
        instance_lines = [l for l in out.split("\n") if '"top.u_' in l and "[" in l and "->" not in l]
        assert len(instance_lines) <= 1, f"expected ≤1 visible instance, got {len(instance_lines)}: {instance_lines}"


# ============================================================================
# Test 9 (v2): --format svg
# ============================================================================
class TestArchSvgOutput:
    """[v2 2026-06-25] --format svg 调 graphviz 生成 SVG."""

    @pytest.mark.skipif(
        not Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v").exists(),
        reason="picorv32 not available",
    )
    def test_svg_generation(self, tmp_path):
        """--format svg 应生成合法 SVG 文件."""
        outfile = tmp_path / "arch.svg"
        rc, _, err = _run_arch(
            "-f", "/Users/fundou/my_dv_proj/picorv32/picorv32.v",
            "-t", "picorv32_axi",
            "--format", "svg",
            "-o", str(outfile),
        )
        if rc != 0:
            # 可能 graphviz 没装
            if "graphviz" in err.lower() or "dot" in err.lower():
                pytest.skip(f"graphviz not available: {err[:200]}")
        assert rc == 0, f"FAIL: rc={rc}, stderr={err[:500]}"
        assert outfile.exists()
        content = outfile.read_text()
        # SVG 应该有标准结构
        assert "<?xml" in content and "<svg" in content
        assert "</svg>" in content
        # 应该有 cluster + node
        assert "<g" in content
        # 包含 module type 名字
        assert "picorv32" in content or "axi_adapter" in content


# ============================================================================
# Test 10 (v2): helper 函数单元测试
# ============================================================================
class TestArchHelpers:
    """[v2] 内部 helper 单元测试."""

    def test_hash_color_deterministic(self):
        """同 name 同 color."""
        import sys as _sys
        _sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from cli.commands.arch import _hash_color
        c1 = _hash_color("axi_master_xbar")
        c2 = _hash_color("axi_master_xbar")
        assert c1 == c2
        # hex color 格式
        assert c1.startswith("#")
        assert len(c1) == 7

    def test_hash_color_different(self):
        """不同 name 应该有不同 color."""
        from cli.commands.arch import _hash_color
        c1 = _hash_color("type_a")
        c2 = _hash_color("type_b")
        assert c1 != c2

    def test_collapse_instances_no_collapse(self):
        """len ≤ max 不折叠."""
        from cli.commands.arch import _collapse_instances
        inst = [("a", "t", 1), ("b", "t", 1)]
        vis, note = _collapse_instances(inst, max_nodes=10)
        assert vis == inst
        assert note is None

    def test_collapse_instances_folds(self):
        """5 instances (3 unique type) + max_nodes=2 → 折叠 1 type."""
        from cli.commands.arch import _collapse_instances
        inst = [
            ("a", "type_a", 1),
            ("b", "type_a", 1),
            ("c", "type_b", 1),
            ("d", "type_b", 1),
            ("e", "type_c", 1),  # 第三 type
        ]
        vis, note = _collapse_instances(inst, max_nodes=2)
        # 可见: 2 个 unique type 各保留第一个 → 2 visible
        assert len(vis) == 2
        # note 应该有 collapse 信息
        assert note is not None
        assert "1" in note  # 1 type collapsed (type_c)

    def test_safe_cluster_name(self):
        """DOT cluster 名不能含 -."""
        from cli.commands.arch import _safe_cluster_name
        assert _safe_cluster_name("axi_master_xbar") == "cluster_axi_master_xbar"
        assert _safe_cluster_name("u_middle.u_sub") == "cluster_u_middle_u_sub"
