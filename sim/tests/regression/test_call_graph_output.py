# test_call_graph_output.py - 调用图输出格式测试
# [铁律13] 金标准测试
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.call_graph_builder import CallGraphBuilder


def _build(source, cls, method):
    builder = CallGraphBuilder({'test.sv': source})
    return builder.build(cls, method)


class TestMermaidOutput(unittest.TestCase):
    """Mermaid 格式输出"""

    def test_basic_mermaid(self):
        """[金标准] 基础调用图 → Mermaid

        task body();
            setup();
            execute();
        endtask

        期望: graph TD + 节点 + 连接
        """
        source = '''class my_seq;
    task body();
        setup();
        execute();
    endtask
    task setup(); endtask
    task execute(); endtask
endclass
module top; endmodule'''
        cg = _build(source, 'my_seq', 'body')
        mermaid = cg.to_mermaid()

        self.assertTrue(mermaid.startswith('graph TD'), "应以 graph TD 开头")
        self.assertIn('-->', mermaid, "应包含连接箭头")
        self.assertIn('setup', mermaid, "应包含 setup 节点")
        self.assertIn('execute', mermaid, "应包含 execute 节点")

    def test_fork_mermaid(self):
        """[金标准] fork → Mermaid"""
        source = '''class my_seq;
    task body();
        fork
            drive_a();
            drive_b();
        join_none
        do_next();
    endtask
    task drive_a(); endtask
    task drive_b(); endtask
    task do_next(); endtask
endclass
module top; endmodule'''
        cg = _build(source, 'my_seq', 'body')
        mermaid = cg.to_mermaid()

        self.assertIn('FORK', mermaid, "应包含 FORK 节点")
        self.assertIn('join_none', mermaid, "应包含 join_none")

    def test_randomize_mermaid(self):
        """[金标准] randomize → Mermaid"""
        source = '''class my_seq;
    task body();
        req.randomize() with { addr inside {[0:63]}; };
    endtask
endclass
module top; endmodule'''
        cg = _build(source, 'my_seq', 'body')
        mermaid = cg.to_mermaid()

        self.assertIn('RANDOMIZE', mermaid, "应包含 RANDOMIZE 节点")


class TestDotOutput(unittest.TestCase):
    """Graphviz DOT 格式输出"""

    def test_basic_dot(self):
        """[金标准] 基础调用图 → DOT"""
        source = '''class my_seq;
    task body();
        setup();
        execute();
    endtask
    task setup(); endtask
    task execute(); endtask
endclass
module top; endmodule'''
        cg = _build(source, 'my_seq', 'body')
        dot = cg.to_dot()

        self.assertTrue(dot.startswith('digraph'), "应以 digraph 开头")
        self.assertIn('->', dot, "应包含连接箭头")
        self.assertIn('setup', dot)
        self.assertIn('execute', dot)

    def test_fork_dot(self):
        """[金标准] fork → DOT"""
        source = '''class my_seq;
    task body();
        fork
            drive_a();
        join_none
    endtask
    task drive_a(); endtask
endclass
module top; endmodule'''
        cg = _build(source, 'my_seq', 'body')
        dot = cg.to_dot()

        self.assertIn('FORK', dot)
        self.assertIn('diamond', dot, "fork 节点应为菱形")

    def test_uvm_sequence_dot(self):
        """[金标准] UVM sequence 完整流程 → DOT"""
        source = '''class my_seq;
    task body();
        req = create("req");
        start_item(req);
        req.randomize() with { addr inside {[0:63]}; };
        finish_item(req);
    endtask
endclass
module top; endmodule'''
        cg = _build(source, 'my_seq', 'body')
        dot = cg.to_dot()

        self.assertIn('SEQUENCE', dot, "应标记 sequence 模式")
        self.assertIn('RANDOMIZE', dot)
        self.assertIn('green', dot, "randomize 节点应为绿色")


if __name__ == '__main__':
    unittest.main()
