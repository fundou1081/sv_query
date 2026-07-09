#==============================================================================
# test_trace.py - trace command tests
#============================================================================

import unittest
import subprocess
import tempfile
import os


class TestTraceCLI(unittest.TestCase):
    """CLI trace command tests"""

    def _run_svq(self, args):
        """Run svq command and return output"""
        # From sim/tests/cli/test_trace.py:
        # sim/tests/cli/ -> sim/tests/ -> sim/ -> project root -> src/
        src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
        cmd = ["python", "-m", "cli.main"] + args
        result = subprocess.run(
            cmd,
            cwd=src_dir,
            capture_output=True,
            text=True,
        )
        return result

    def _write_sv(self, source):
        """Write SV source to temp file"""
        fd, path = tempfile.mkstemp(suffix=".sv")
        with os.fdopen(fd, "w") as f:
            f.write(source)
        return path

    def test_fanin_basic(self):
        """[Golden] trace fanin returns drivers"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanin", "top.a", "--file", path])
            self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")
            self.assertIn("top.q", result.stdout)
            # [FIX 2026-07-05] 单 signal backward compat: legacy "Fanin of 'sig':" format
            # batch mode (--batch) 才输出 'signal 1/1'
            self.assertIn("Fanin of 'top.a'", result.stdout)
        finally:
            os.unlink(path)

    def test_fanout_basic(self):
        """[Golden] trace fanout returns loads"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanout", "top.q", "--file", path])
            self.assertEqual(result.returncode, 0, f"Error: {result.stderr}")
            self.assertIn("top.a", result.stdout)
            # [B1 2026-07-03] batch mode
            self.assertIn("signal 1/1", result.stdout)
        finally:
            os.unlink(path)

    def test_fanin_json(self):
        """[Golden] trace fanin --json outputs valid JSON with batch schema"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanin", "top.a", "--file", path, "--json"])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            import json
            data = json.loads(result.stdout)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("command"), "trace_fanin")
            # [B1 2026-07-03] batch schema: result.signals[].drivers
            signals = data["result"]["signals"]
            self.assertEqual(len(signals), 1)
            self.assertEqual(signals[0]["signal"], "top.a")
            self.assertIn("drivers", signals[0])
        finally:
            os.unlink(path)

    def test_fanout_json(self):
        """[Golden] trace fanout --json outputs valid JSON with batch schema"""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) a <= q;
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanout", "top.q", "--file", path, "--json"])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            import json
            data = json.loads(result.stdout)
            self.assertTrue(data.get("ok"))
            self.assertEqual(data.get("command"), "trace_fanout")
            # [B1 2026-07-03] batch schema
            signals = data["result"]["signals"]
            self.assertEqual(len(signals), 1)
            self.assertEqual(signals[0]["signal"], "top.q")
            self.assertIn("loads", signals[0])
        finally:
            os.unlink(path)

    def test_fanin_not_found(self):
        """[Golden] trace fanin for non-existent signal returns empty"""
        source = '''
module top(input clk);
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq(["trace", "fanin", "top.nonexistent", "--file", path])
            self.assertEqual(result.returncode, 0)
            self.assertIn("(no drivers)", result.stdout)
        finally:
            os.unlink(path)

    def test_trace_help(self):
        """[Golden] trace --help shows subcommands"""
        result = self._run_svq(["trace", "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("fanin", result.stdout)
        self.assertIn("fanout", result.stdout)


#==============================================================================
# [Phase 2 2026-07-09] trace fanin/fanout --format dot golden tests
# 需求: sv_query trace fanin X --format dot --png Y.png 输出 DOT/PNG 图
#       类似 chain 风格: 中央 source 信号, 每个 driver 一条 path,
#       边标 cycle 数, REG 粗框, CONST 浅色.
#==============================================================================
class TestTraceFaninDotOutput(unittest.TestCase):
    """[Phase 2 2026-07-09] trace fanin --format dot 输出限制测试."""

    def _run_svq(self, args):
        """Run svq and return result."""
        import subprocess
        src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
        cmd = ["python", "-m", "cli.main"] + args
        result = subprocess.run(cmd, cwd=src_dir, capture_output=True, text=True)
        return result

    def _write_sv(self, source: str) -> str:
        """Write SV source to temp file."""
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".sv")
        with os.fdopen(fd, "w") as f:
            f.write(source)
        return path

    def test_trace_fanin_format_dot_basic(self):
        """[金标准] trace fanin <signal> --format dot 必须输出合法 DOT 文件."""
        import tempfile
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
'''
        path = self._write_sv(source)
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = self._run_svq([
                "trace", "fanin", "top.a",
                "--file", path,
                "--format", "dot",
                "--output", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            with open(dot_path) as f:
                dot_content = f.read()
            self.assertIn("digraph", dot_content)
            self.assertIn("top.q", dot_content, "DOT 应含 source node 'top.q'")
            self.assertIn("top.a", dot_content, "DOT 应含 target node 'top.a'")
        finally:
            os.unlink(dot_path)
            os.unlink(path)

    def test_trace_fanin_format_dot_has_cycle_labels(self):
        """[金标准] trace fanin --format dot 边标 [+N cycle] (类似 chain)."""
        import tempfile
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
'''
        path = self._write_sv(source)
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = self._run_svq([
                "trace", "fanin", "top.b",
                "--file", path,
                "--format", "dot",
                "--output", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            with open(dot_path) as f:
                content = f.read()
            import re
            # 检查有 +N cycle 边标
            edge_cycles = re.findall(r'label="\+(\d+) cycle', content)
            self.assertGreater(
                len(edge_cycles), 0,
                f"trace fanin DOT 应含 +N cycle labels, 实际: 0 匹配"
            )
        finally:
            os.unlink(dot_path)
            os.unlink(path)

    def test_trace_fanin_format_dot_reg_uses_thicker_border(self):
        """[金标准] trace fanin --format dot REG 或 PORT 节点用粗框 (penwidth>=2)"""
        import tempfile
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) begin
        a <= q;
    end
endmodule
'''
        path = self._write_sv(source)
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = self._run_svq([
                "trace", "fanin", "top.a",
                "--file", path,
                "--format", "dot",
                "--output", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            with open(dot_path) as f:
                content = f.read()
            # 检查 driver 节点 (top.q) 用了粗框 - penwidth>=2
            import re
            # 查找 "top_q" 节点 里的 penwidth (节点定义, 在 [...] 内)
            node_match = re.search(
                r'"top_q"\s*\[[^]]*penwidth=(\d+)',
                content
            )
            self.assertIsNotNone(
                node_match,
                f"trace fanin DOT 中 top_q 节点没有定义"
            )
            pw = int(node_match.group(1))
            self.assertGreaterEqual(
                pw, 2,
                f"driver node penwidth 应 >= 2 (粗框), 实际: {pw}"
            )
        finally:
            os.unlink(dot_path)
            os.unlink(path)

    def test_trace_fanout_format_dot_basic(self):
        """[金标准] trace fanout --format dot 也能输出."""
        import tempfile
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= q;
        b <= a;
    end
endmodule
'''
        path = self._write_sv(source)
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False) as f:
            dot_path = f.name
        try:
            result = self._run_svq([
                "trace", "fanout", "top.q",
                "--file", path,
                "--format", "dot",
                "--output", dot_path,
            ])
            self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
            with open(dot_path) as f:
                content = f.read()
            self.assertIn("digraph", content)
            self.assertIn("top.q", content)
            self.assertIn("top.a", content, "DOT 应含 load 节点 top.a")
        finally:
            os.unlink(dot_path)
            os.unlink(path)

    def test_trace_fanin_format_default_is_text(self):
        """[金标准] 不加 --format 时默认输出是文本 (不破坏向后兼容)."""
        source = '''
module top(input clk, output logic [7:0] q);
    logic [7:0] a;
    always_ff @(posedge clk) begin
        a <= q;
    end
endmodule
'''
        path = self._write_sv(source)
        try:
            result = self._run_svq([
                "trace", "fanin", "top.a", "--file", path,
            ])
            self.assertEqual(result.returncode, 0)
            # Default output is text (不输出 DIGRAPH)
            self.assertNotIn("digraph", result.stdout)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
