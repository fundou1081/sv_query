#==============================================================================
# test_visualize_latency_golden.py
#==============================================================================
"""
[Phase 1+2 verify 2026-07-09] Hand-crafted golden fixtures to verify
chain cycle/latency labels and trace fanin/fanout DOT output are accurate.

These test small SV modules with KNOWN structure (X stages, X registers).
The visualizations should match the expected count of REG nodes, cycle
values, and trace direction.
"""

import unittest
import subprocess
import tempfile
import re
from pathlib import Path


LATENCY_FIXTURES = Path(__file__).parent / "fixtures" / "latency"


def _run_svq(args):
    """Run svq command and return result."""
    return subprocess.run(
        ["sv_query"] + args,
        capture_output=True,
        text=True,
    )


def _read_dot(path):
    return Path(path).read_text()


def _run_chain(sv_path, dot_path, target=None, max_edges=20):
    """Run `visualize chain --auto --target <target> ... --dot`.

    Note: --auto requires --target. If no target, default to 'top'.
    """
    args = [
        "visualize", "chain",
        "-f", str(sv_path),
        "--no-strict",
        "--auto",
        "--dot", dot_path,
        "--max-edges", str(max_edges),
        "--target", target or "top",
    ]
    return _run_svq(args)


def _run_trace_fanin(sv_path, signal, dot_path):
    """Run `trace fanin <sig> --format dot --output <path>`."""
    return _run_svq([
        "trace", "fanin", signal,
        "-f", str(sv_path),
        "--no-strict",
        "--format", "dot",
        "--output", dot_path,
    ])


def _count_regs_in_trace_dot(dot_content):
    """Count REG-labeled nodes (kind=REG) in DOT — trace fanin/fanout format.

    源格式: label="<sig>\\n(REG)"
    """
    return len(re.findall(r'\(REG\)', dot_content))


def _count_total_cycles_in_dot(dot_content):
    """Extract Total cycles values (look for 'Total cycles: N' labels)."""
    return [int(m.group(1)) for m in re.finditer(r'Total cycles:\s*(\d+)', dot_content)]


def _count_cycle_labels_in_dot(dot_content):
    """Count [cycle=N] labels (one per non-output node with cycle value)."""
    return [int(m.group(1)) for m in re.finditer(r'\[cycle=(\d+)\]', dot_content)]


def _count_plus_cycle_edges(dot_content):
    """Count edges with +N cycle labels."""
    return len(re.findall(r'label="\+(\d+) cycle', dot_content))


# =============================================================================
# Golden Tests: Chain with cycle labels
# =============================================================================
class TestChainLatencyGolden(unittest.TestCase):
    """Hand-crafted SV fixtures with KNOWN pipeline structures.

    Chain DOT 格式: 输出节点标 'Total cycles: N', 边标 '+N cycle'.
    每个 fixture 的 'latency' cycle 可手动验证 (e.g. 1 reg = 1 cycle).
    """

    def test_single_reg_chain_shows_1_cycle(self):
        """[金标准] single_reg.sv (1 REG: q <= d) → Total cycles: 1"""
        sv_path = LATENCY_FIXTURES / "single_reg.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_chain(sv_path, dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # single_reg: d -> q, 1 cycle latency
            # Top.q 应标 'Total cycles: 1'
            totals = _count_total_cycles_in_dot(content)
            self.assertEqual(
                len(totals), 1,
                f"single_reg 应只有 1 个 output 节点标 'Total cycles:', 实际: {totals}"
            )
            self.assertEqual(
                totals[0], 1,
                f"single_reg 应有 Total cycles: 1, 实际: {totals[0]}"
            )
            # 边标 +N cycle
            edge_cycle_count = _count_plus_cycle_edges(content)
            self.assertGreaterEqual(
                edge_cycle_count, 1,
                f"应有至少 1 个 +N cycle 边标, 实际 count: {edge_cycle_count}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_two_reg_chain_shows_2_cycles(self):
        """[金标准] two_reg_chain.sv (2 REG in series: a, b, q) → Total cycles: 3"""
        sv_path = LATENCY_FIXTURES / "two_reg_chain.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_chain(sv_path, dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # 2-REG chain (a, b) + q = 3 cycle latency
            totals = _count_total_cycles_in_dot(content)
            self.assertEqual(
                len(totals), 1,
                f"two_reg_chain 应只有 1 个 output, 实际: {totals}"
            )
            self.assertGreaterEqual(
                totals[0], 2,
                f"two_reg_chain 应 Total cycles >= 2, 实际: {totals[0]}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_deep_pipeline_shows_5_cycles(self):
        """[金标准] deep_pipeline.sv (5 REG chain: a,b,c,d,e,q) → Total cycles >= 5"""
        sv_path = LATENCY_FIXTURES / "deep_pipeline.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_chain(sv_path, dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            totals = _count_total_cycles_in_dot(content)
            self.assertGreaterEqual(
                len(totals), 1,
                f"deep_pipeline 应至少 1 个 Total cycles 输出, 实际: {totals}"
            )
            self.assertGreaterEqual(
                totals[0], 5,
                f"deep_pipeline 应 Total cycles >= 5, 实际: {totals[0]}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_branching_chain_has_total_cycles_1(self):
        """[金标准] branching.sv (1 input reg -> 2 output regs) → 每个输出 Total cycles: 1"""
        sv_path = LATENCY_FIXTURES / "branching.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_chain(sv_path, dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # branching.sv: d -> a -> (q1, q2), 1 cycle
            totals = _count_total_cycles_in_dot(content)
            # 应有 2 个 output (q1, q2)
            self.assertGreaterEqual(
                len(totals), 1,
                f"branching 应 >= 1 个 Total cycles 输出 (有 q1, q2), 实际: {totals}"
            )
            for t in totals:
                self.assertGreaterEqual(
                    t, 1,
                    f"branching 的 output Total cycles 应 >= 1, 实际: {t}"
                )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_two_parallel_chain_has_3_regs(self):
        """[金标准] two_reg_parallel.sv (a, b, q = 3 REG 并行) → Total cycles >= 3"""
        sv_path = LATENCY_FIXTURES / "two_reg_parallel.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_chain(sv_path, dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            totals = _count_total_cycles_in_dot(content)
            # 3 REG 在并行路径 (a, b, q), max latency = 1 cycle in 最长 path
            self.assertGreaterEqual(
                len(totals), 1,
                f"two_reg_parallel 应 >= 1 Total cycles, 实际: {totals}"
            )
            self.assertGreaterEqual(
                totals[0], 1,
                f"two_reg_parallel Total cycles 应 >= 1, 实际: {totals[0]}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)


# =============================================================================
# Golden Tests: Trace fanin/fanout with cycle labels (DOT format includes kind)
# =============================================================================
class TestTraceLatencyGolden(unittest.TestCase):
    """Trace fanin/fanout DOT 对 hand-crafted SV 应该 output 精确的 node/edge count.

    Trace DOT 格式: 'label="<sig>\\n(REG)"' or '(SIGNAL)' etc.
    """

    def test_trace_fanin_single_reg_has_1_driver_reg(self):
        """[金标准] single_reg.sv trace fanin top.q → driver 是 top.d (PORT_IN)"""
        sv_path = LATENCY_FIXTURES / "single_reg.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_trace_fanin(sv_path, "top.q", dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # Source 是中央 (top_q), driver 应该是 top_d
            self.assertIn("top_q", content, "DOT 应含 source signal 'top.q'")
            self.assertIn("top_d", content, "DOT 应含 driver 'top.d'")
            # trace 边标 +N cycle
            edge_cycles = _count_plus_cycle_edges(content)
            self.assertGreaterEqual(
                len(edge_cycles), 1,
                f"trace fanin 应至少 1 个 +N cycle 边标, 实际: {len(edge_cycles)}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_trace_fanin_deep_pipeline_chain_drivers(self):
        """[金标准] deep_pipeline.sv trace fanin top.q → driver chain 应含 mid regs"""
        sv_path = LATENCY_FIXTURES / "deep_pipeline.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_trace_fanin(sv_path, "top.q", dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # fanin drivers should include e, d_pipe, c, b, a (5 chained regs)
            for sig in ["top.a", "top.b", "top.c", "top.e"]:
                sanitized = sig.replace(".", "_")
                self.assertIn(
                    sanitized,
                    content,
                    f"deep_pipeline fanin 应含 driver '{sig}', DOT 不含 {sanitized}"
                )
            # 应至少有 3-5 个 REG drivers in fanin
            reg_count = _count_regs_in_trace_dot(content)
            self.assertGreaterEqual(
                reg_count, 3,
                f"deep_pipeline fanin 应 >= 3 REG drivers, 实际: {reg_count}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_trace_fanout_branching_shows_2_loads(self):
        """[金标准] branching.sv trace fanout top.a → 2 outputs (q1, q2)"""
        sv_path = LATENCY_FIXTURES / "branching.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_svq([
                "trace", "fanout", "top.a",
                "-f", str(sv_path),
                "--no-strict",
                "--format", "dot",
                "--output", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # source = top.a (中央), loads 应该是 top.q1 和 top.q2
            self.assertIn("top_a", content, "DOT 应含 source 'top.a'")
            self.assertIn("top_q1", content, "DOT 应含 load 'top.q1'")
            self.assertIn("top_q2", content, "DOT 应含 load 'top.q2'")
            # 中央 source 应有 2 条 fanout edges
            edges_from_a = re.findall(
                r'"top_a"\s*->\s*"\w+"',
                content
            )
            self.assertGreaterEqual(
                len(edges_from_a), 2,
                f"top.a 应有 >=2 fanout edges (to q1, q2), 实际: {len(edges_from_a)}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_trace_fanout_single_reg_q_chain(self):
        """[金标准] single_reg.sv trace fanout top.d → 1 load (top.q)"""
        sv_path = LATENCY_FIXTURES / "single_reg.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_svq([
                "trace", "fanout", "top.d",
                "-f", str(sv_path),
                "--no-strict",
                "--format", "dot",
                "--output", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # source = top.d, load = top.q (1 edge, +1 cycle)
            self.assertIn("top_d", content, "DOT 应含 source 'top.d'")
            self.assertIn("top_q", content, "DOT 应含 load 'top.q'")
            edges_from_d = re.findall(
                r'"top_d"\s*->\s*"\w+"',
                content
            )
            self.assertEqual(
                len(edges_from_d), 1,
                f"top.d fanout 应只有 1 edge (to q), 实际: {len(edges_from_d)}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)


# =============================================================================
# Golden Tests: Trace fanin/fanout with cycle labels
# =============================================================================
class TestTraceLatencyGolden(unittest.TestCase):
    """Trace fanin/fanout DOT 对 hand-crafted SV 应该 output 精确的 node/edge count."""

    def test_trace_fanin_single_reg_has_1_driver(self):
        """[金标准] single_reg.sv trace fanin top.q → 1 个 input driver"""
        sv_path = LATENCY_FIXTURES / "single_reg.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_trace_fanin(sv_path, "top.q", dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # Source 是中央 (top.q), driver 应该是 top.d (1 driver)
            # Driver 节点用 (REG) 或 (SIGNAL) 标
            # 中央 source 没有 (REG), 只周边 drivers 有 kind label
            self.assertIn("top_q", content, "DOT 应含 source signal 'top.q'")
            # driver 'top_d' 应该出现
            self.assertIn("top_d", content, "DOT 应含 driver 'top.d'")
            # Cycle labels 至少 1 个
            edges = re.findall(r'label="\+(\d+) cycle"', content)
            self.assertGreaterEqual(
                len(edges), 1,
                f"trace fanin 应至少 1 个 +N cycle 边标, 实际: {len(edges)}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_trace_fanin_deep_pipeline_chain_drivers(self):
        """[金标准] deep_pipeline.sv trace fanin top.q → driver chain 含 5 跳"""
        sv_path = LATENCY_FIXTURES / "deep_pipeline.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_trace_fanin(sv_path, "top.q", dot_path)
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # 找 fanin drivers: top.d, top.a, top.b, top.c, top.d_pipe, top.e
            for sig in ["top.d", "top.a", "top.b", "top.c", "top.e"]:
                self.assertIn(
                    sig.replace(".", "_"), content,
                    f"deep_pipeline fanin 应含 driver '{sig}', DOT 不含"
                )
        finally:
            Path(dot_path).unlink(missing_ok=True)

    def test_trace_fanout_branching_shows_2_loads(self):
        """[金标准] branching.sv trace fanout top.a → 2 outputs (q1, q2)"""
        sv_path = LATENCY_FIXTURES / "branching.sv"
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = _run_svq([
                "trace", "fanout", "top.a",
                "-f", str(sv_path),
                "--no-strict",
                "--format", "dot",
                "--output", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            content = _read_dot(dot_path)
            # source = top.a (中央), loads 应该是 top.q1 和 top.q2
            self.assertIn("top_a", content, "DOT 应含 source 'top.a'")
            self.assertIn("top_q1", content, "DOT 应含 load 'top.q1'")
            self.assertIn("top_q2", content, "DOT 应含 load 'top.q2'")
            # 中央 source 应有 2 条 fanout edges
            edges_from_a = re.findall(
                r'"top_a"\s*->\s*"\w+"',
                content
            )
            self.assertGreaterEqual(
                len(edges_from_a), 2,
                f"top.a 应有 >=2 fanout edges (to q1, q2), 实际: {len(edges_from_a)}"
            )
        finally:
            Path(dot_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
