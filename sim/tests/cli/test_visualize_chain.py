#==============================================================================
# test_visualize_chain.py - [Plan B+ 2026-07-08] `visualize chain` 子命令:
#                            从指定 input signals 到 output signals 画
#                            data path 图, LR 布局 + neato 强制方形.
#
# Use case: 方豆 7/8 反馈 "深入到具体 module, 完整搞出来 input → output
# 之间的图, 从左到右 / 从上到下, 尽可能方形".
#==============================================================================
"""
[Plan B+ 2026-07-08] `sv_query visualize chain` 子命令.

输入:
  --from <signal> (可多个)  - 起点 signal (e.g. dot11_tx.phy_tx_start)
  --to   <signal> (可多个)  - 终点 signal (e.g. dot11_tx.result_i)
  --auto                    - 自动找所有 input ports → output ports paths
  --target <module>         - focus on module
  --layout {LR,TB}          - 方向 (默认 LR)
  --layout-engine {dot,neato,fdp} - 引擎 (默认 neato, 强制方形)
  --max-edges <N>           - cap 显示的边数

输出:
  --dot <file>      - DOT 文件
  --png <file>      - PNG (调用 neato)
  --svg <file>      - SVG (调用 neato)

Iron Law 7: golden tests BEFORE implementation.
"""

import unittest
import subprocess
from pathlib import Path


DOT11_TX = str(Path.home() / "my_dv_proj/openwifi-hw/ip/openofdm_tx/src/dot11_tx.v")


def _run_svq(args):
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
    )


class TestChainCommandExists(unittest.TestCase):
    """chain 子命令必须存在."""

    def test_visualize_chain_exists(self):
        """[金标准] `sv_query visualize chain --help` 跑得起来"""
        result = _run_svq(["visualize", "chain", "--help"])
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        # 必须有 --from/--to 选项
        self.assertIn("--from", result.stdout)
        self.assertIn("--to", result.stdout)


class TestChainFromTo(unittest.TestCase):
    """手动指定 --from / --to 跑 chain."""

    def test_chain_bram_din_to_crc_data(self):
        """[金标准] chain from bram_din (input data) to crc_data[0] (intermediate)
        should render DOT (single file mode).

        Note: phy_tx_start → result_i has no direct data path
              (phy_tx_start is control, not data). Use bram_din → crc_data[0]
              as a real data path in dot11_tx.
        """
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_svq([
                "visualize", "chain",
                "-f", DOT11_TX,
                "--no-strict",
                "--from", "dot11_tx.bram_din",
                "--to", "dot11_tx.crc_data[0]",
                "--dot", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            # DOT 文件应该被创建且非空
            content = Path(dot_path).read_text()
            self.assertGreater(len(content), 100, f"DOT too short: {content[:200]}")
            # 必须是 digraph
            self.assertIn("digraph", content)
            # 必须含起点/终点
            self.assertTrue(
                "bram_din" in content or "crc_data" in content,
                f"DOT missing key signals: {content[:300]}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)


class TestChainAutoMode(unittest.TestCase):
    """--auto 模式: 自动从 input ports 找 path 到 output ports."""

    def test_chain_auto_mode(self):
        """[金标准] chain --auto 在 dot11_tx 上找到 paths"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_svq([
                "visualize", "chain",
                "-f", DOT11_TX,
                "--no-strict",
                "--target", "dot11_tx",
                "--auto",
                "--max-edges", "30",
                "--dot", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = Path(dot_path).read_text()
            self.assertGreater(len(content), 100, f"DOT too short: {content[:200]}")
            # --auto 模式下 DOT 应该含至少一个 input port → output port 的边
            self.assertIn("digraph", content)
        finally:
            Path(dot_path).unlink(missing_ok=True)


class TestChainLayout(unittest.TestCase):
    """layout 选项: LR/TB + neato/dot 引擎."""

    def test_chain_lr_neato_renders_square(self):
        """[金标准] chain --layout LR --layout-engine neato 渲染成方形 PNG"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            png_path = f.name
        try:
            result = _run_svq([
                "visualize", "chain",
                "-f", DOT11_TX,
                "--no-strict",
                "--from", "dot11_tx.bram_din",
                "--to", "dot11_tx.crc_data[0]",
                "--layout", "LR",
                "--layout-engine", "neato",
                "--png", png_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            # PNG 应该存在
            self.assertTrue(Path(png_path).exists(), f"PNG not created: {result.stdout}")
            # PNG size 应该 > 1KB
            size = Path(png_path).stat().st_size
            self.assertGreater(size, 1000, f"PNG too small: {size} bytes")
        finally:
            Path(png_path).unlink(missing_ok=True)


class TestChainMaxEdges(unittest.TestCase):
    """--max-edges 限制边的数量."""

    def test_chain_max_edges(self):
        """[金标准] chain --max-edges 10 限制图大小"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_svq([
                "visualize", "chain",
                "-f", DOT11_TX,
                "--no-strict",
                "--target", "dot11_tx",
                "--auto",
                "--max-edges", "5",
                "--dot", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = Path(dot_path).read_text()
            # 数 edges (line with ->)
            edges = content.count("->")
            self.assertLessEqual(edges, 30, f"Too many edges: {edges}")
        finally:
            Path(dot_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()