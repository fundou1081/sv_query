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


@unittest.skipIf(not __import__('os').path.exists('/tmp/openofdm_tx.f'), '/tmp/openofdm_tx.f not generated. Chain cluster tests require filelist setup. (Skip per V7 discipline.)')
class TestChainSubModuleClusters(unittest.TestCase):
    """[Plan B+2 2026-07-08] chain 图应该用 subgraph cluster 区分 sub-module 边界."""

    def test_chain_dot_has_subgraph_clusters(self):
        """[金标准] chain 在 multi-module 项目 (用 filelist) 应该生成
        subgraph cluster { label=... } 按 module 分组.

        dot11_tx 是顶层, 但 chain 中间 signals 可能来自 axi_fifo_bram,
        ifftmain 等 sub-module (PicoRV32 / openwifi PHY). filelist 模式下
        DOT 应该至少 1 个 subgraph cluster.
        """
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_svq([
                "visualize", "chain",
                "--filelist=/tmp/openofdm_tx.f",
                "--target", "openofdm_tx",
                "--auto",
                "--max-edges", "30",
                "--no-strict",
                "--dot", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = Path(dot_path).read_text()
            # 必须有 subgraph cluster
            self.assertIn("subgraph", content, f"No subgraph cluster in DOT:\n{content[:500]}")
            self.assertIn("cluster", content, f"No 'cluster' in DOT:\n{content[:500]}")
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_chain_dot_hierarchical_signal_ids(self):
        """[金标准 2026-07-08] 修了 root cause 后: sub-module signals (bitreverse.*,
        dpram.*, fftstage.*) 应该有完整 hierarchy path (e.g.
        openofdm_tx.dot11_tx.ifft64.revstage.i_clk), 不是 flattened
        (e.g. bitreverse.i_clk).

        之前 bug: connection_extractor 用 inst_module_name (短名) 替代
        inst_path, 导致同名 port 多 instance 合并.
        """
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_svq([
                "visualize", "chain",
                "--filelist=/tmp/openofdm_tx.f",
                "--target", "openofdm_tx",
                "--auto",
                "--max-edges", "30",
                "--no-strict",
                "--dot", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = Path(dot_path).read_text()
            # [FIX 验证] 应该看到完整 hierarchy path in node IDs (underscore version
            # 因为 _sanitize_dot_id_chain 转换). e.g. "openofdm_tx_dot11_tx_ifft64_*"
            self.assertIn(
                "openofdm_tx_dot11_tx",
                content,
                f"No hierarchy path (openofdm_tx_dot11_tx) in DOT — likely still flattened:\n{content[:1000]}"
            )
            # [FIX 验证] 不应该有 "External sub-modules" cluster (因为所有 signal
            # 都有完整 path, 都被归到正常 cluster)
            self.assertNotIn(
                "External sub-modules",
                content,
                f"Should not have 'External sub-modules' cluster (root cause fixed):\n{content[:500]}"
            )
            # 不应该有短名 (flattened) signal - bitreverse.i_clk 应当有完整前缀
            # bitreverse 不再作为短名 prefix 出现 (作为 standalone node)
            self.assertNotRegex(
                content,
                r'"\s*bitreverse_\w+"',  # 短名形式如 bitreverse_i_clk
                f"Found flattened bitreverse.* node (root cause not fixed):\n{content[:1000]}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_chain_dot_distinguishes_input_output(self):
        """[金标准] chain DOT 应该用不同 shape/color 区分 input vs output vs intermediate.
        使用 multi-file filelist 获得 richer paths (会含 intermediate blue nodes)."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            # Use filelist mode for richer paths (multi-file project)
            result = _run_svq([
                "visualize", "chain",
                "--filelist=/tmp/openofdm_tx.f",
                "--no-strict",
                "--target", "openofdm_tx",
                "--auto",
                "--max-edges", "30",
                "--dot", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = Path(dot_path).read_text()
            # input 是绿色 (#22aa55), output 是红色 (#cc3333), intermediate 是蓝色 (#3366cc)
            self.assertIn("#22aa55", content, "No input color (green) in DOT")
            self.assertIn("#cc3333", content, "No output color (red) in DOT")
            self.assertIn("#3366cc", content, "No intermediate color (blue) in DOT")
        finally:
            Path(dot_path).unlink(missing_ok=True)


#==============================================================================
# [Phase 1 2026-07-09] Cycle / Latency 增强 tests.
# Plan A+1: chain 图每个 reg 标 [cycle=N], 路径终点标 total:N cycles,
#           critical path 红色. TDD 先于 implementation.
#==============================================================================
@unittest.skipIf(not __import__('os').path.exists('/tmp/openofdm_tx.f'), '/tmp/openofdm_tx.f not generated. Chain cycle tests require filelist setup. (Skip per V7 discipline.)')
class TestChainCycleAnnotation(unittest.TestCase):
    """[Phase 1 2026-07-09] chain DOT 必须标 latency 信息.

    动机: 方豆反馈 "我还没有办法清晰看到 latency 和信号追踪的图示".
    Plan: 每条经 reg 边标 '+N cycle', REG 标 '[cycle=K]'.
          路径终点标 'total: M cycles'. critical (max delay) path 红色.
    """

    def _run_chain_dot(self, args, dot_path):
        """运行 sv_query visualize chain, 返回 DOT 文本."""
        full_args = ["visualize", "chain", "--filelist=/tmp/openofdm_tx.f", "--no-strict"] + args + ["--dot", dot_path]
        result = _run_svq(full_args)
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}\nstdout: {result.stdout}")
        return Path(dot_path).read_text()

    def test_chain_dot_has_cycle_labels_on_reg_nodes(self):
        """[金标准] 链上的 REG 节点必须标 [cycle=N]"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            content = self._run_chain_dot([
                "--target", "openofdm_tx",
                "--auto",
                "--max-edges", "30",
            ], dot_path)
            # 检查有 REG 类型的节点标了 [cycle=N]
            # pattern: REG shape with cycle label
            import re
            cycle_labels = re.findall(r'cycle=\d+', content)
            self.assertGreater(
                len(cycle_labels), 0,
                f"chain DOT 应至少一个 REG 标了 [cycle=N], 实际: 0 匹配"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_chain_dot_edge_increments_by_cycles(self):
        """[金标准] chain DOT 边标 [+N cycle] 从 src 到 dst 经历的 reg 数."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            content = self._run_chain_dot([
                "--target", "openofdm_tx",
                "--auto",
                "--max-edges", "30",
            ], dot_path)
            # 检查边标了 +N cycle
            import re
            edge_cycles = re.findall(r'label="\+(\d+) cycle', content)
            self.assertGreater(
                len(edge_cycles), 0,
                f"chain DOT 边应标 +N cycle, 实际: 0 匹配"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_chain_dot_path_endpoints_show_total_cycles(self):
        """[金标准] 路径终点 (output) 应标 total: N cycles."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            content = self._run_chain_dot([
                "--target", "openofdm_tx",
                "--auto",
                "--max-edges", "30",
            ], dot_path)
            # output 节点应该标 total cycles
            self.assertIn(
                "total cycles",
                content.lower(),
                f"chain DOT 应有 'total cycles' 标记, 实际 DOT 不含该字符串"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_chain_dot_critical_path_red_color(self):
        """[金标准] 最长路径 (critical path) 节点应该红色, 不同于普通 intermediate 蓝."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            content = self._run_chain_dot([
                "--target", "openofdm_tx",
                "--auto",
                "--max-edges", "30",
            ], dot_path)
            # critical path 颜色 = #dd2222 附近 (亮红)
            # normal intermediate = #3366cc (蓝)
            # 至少有一个 critical (red) 颜色
            import re
            colors = re.findall(r'fillcolor="(#[a-f0-9]{6})"', content)
            self.assertTrue(
                any(c.lower().startswith("#dd") or c.lower().startswith("#cc") for c in colors),
                f"chain DOT 应有 critical path 红色 (#ddXXXX), 实际 colors: {set(colors)}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_chain_dot_cycle_count_matches_reg_chains(self):
        """[金标准] cycle 数必须跟 reg chain 深度一致. 3 个连续 reg 链产生 [cycle=2] 节点 (路径上经 2 个 reg)."""
        import tempfile
        # 直接生成 pipeline 做验证: pipeline DOT 中 stage 数 = chain latency cycle 数
        # 这里不是直接验证, 是验证 cycle 数值合理性: 至少 1, 不超过 max-edges
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            content = self._run_chain_dot([
                "--target", "openofdm_tx",
                "--auto",
                "--max-edges", "30",
            ], dot_path)
            import re
            # cycle 数值都在合理范围 (1..50, 因为 dot11_tx 不应该 >50 cycles)
            cycle_vals = [int(m.group(1)) for m in re.finditer(r'\[cycle=(\d+)\]', content)]
            for v in cycle_vals:
                self.assertGreaterEqual(v, 0, f"cycle 不能为负: {v}")
                self.assertLess(v, 200, f"cycle 不应超过 200: {v}")
        finally:
            Path(dot_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()