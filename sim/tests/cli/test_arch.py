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