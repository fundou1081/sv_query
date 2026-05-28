# test_call_graph.py - 函数调用图金标准测试
# [铁律13] 金标准测试
# [铁律17] 强断言
#
# 目标: 从入口函数/任务出发，构建完整调用图
# 支持 fork/join 处理和 randomize 标记
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.call_graph_builder import CallGraphBuilder
from trace.core.graph.call_graph_models import CallNode, CallGraph


def _build_call_graph(source, entry_class, entry_method):
    """构建调用图"""
    builder = CallGraphBuilder({'test.sv': source})
    return builder.build(entry_class, entry_method)


class TestBasicCallGraph(unittest.TestCase):
    """基础调用图"""

    def test_simple_task_call(self):
        """[金标准] 简单 task 调用链

        class my_seq;
            task body();
                do_drive();
            endtask
            task do_drive();
            endtask
        endclass

        调用图:
          body
          └── do_drive
        """
        source = '''class my_seq;
    task body();
        do_drive();
    endtask
    task do_drive();
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        self.assertEqual(cg.entry_point, 'my_seq.body')
        self.assertEqual(len(cg.root.children), 1)
        self.assertEqual(cg.root.children[0].callee, 'do_drive')

    def test_nested_calls(self):
        """[金标准] 嵌套调用

        class my_seq;
            task body();
                level1();
            endtask
            task level1();
                level2();
            endtask
            task level2();
            endtask
        endclass

        调用图:
          body
          └── level1
              └── level2
        """
        source = '''class my_seq;
    task body();
        level1();
    endtask
    task level1();
        level2();
    endtask
    task level2();
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        self.assertEqual(cg.root.children[0].callee, 'level1')
        self.assertEqual(cg.root.children[0].children[0].callee, 'level2')

    def test_multiple_calls(self):
        """[金标准] 多个顺序调用

        class my_seq;
            task body();
                setup();
                execute();
                cleanup();
            endtask
        endclass

        调用图:
          body
          ├── setup
          ├── execute
          └── cleanup
        """
        source = '''class my_seq;
    task body();
        setup();
        execute();
        cleanup();
    endtask
    task setup(); endtask
    task execute(); endtask
    task cleanup(); endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        self.assertEqual(len(cg.root.children), 3)
        names = [c.callee for c in cg.root.children]
        self.assertEqual(names, ['setup', 'execute', 'cleanup'])


class TestForkHandling(unittest.TestCase):
    """Fork 处理"""

    def test_fork_join_none(self):
        """[金标准] fork/join_none

        task body();
            fork
                drive_a();
                drive_b();
            join_none
            do_next();
        endtask

        调用图:
          body
          ├── [FORK/join_none]
          │   ├── drive_a
          │   └── drive_b
          └── do_next
        """
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
        cg = _build_call_graph(source, 'my_seq', 'body')

        # fork 节点
        fork_node = cg.root.children[0]
        self.assertEqual(fork_node.kind, 'fork')
        self.assertEqual(fork_node.join_type, 'join_none')
        self.assertEqual(len(fork_node.children), 2)

        # fork 之后的调用
        self.assertEqual(cg.root.children[1].callee, 'do_next')

    def test_fork_join(self):
        """[金标准] fork/join (阻塞)"""
        source = '''class my_seq;
    task body();
        fork
            drive_a();
        join
        do_next();
    endtask
    task drive_a(); endtask
    task do_next(); endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        fork_node = cg.root.children[0]
        self.assertEqual(fork_node.kind, 'fork')
        self.assertEqual(fork_node.join_type, 'join')

    def test_fork_join_any(self):
        """[金标准] fork/join_any"""
        source = '''class my_seq;
    task body();
        fork
            drive_a();
            drive_b();
        join_any
        do_next();
    endtask
    task drive_a(); endtask
    task drive_b(); endtask
    task do_next(); endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        fork_node = cg.root.children[0]
        self.assertEqual(fork_node.join_type, 'join_any')

    def test_nested_fork(self):
        """[金标准] 嵌套 fork

        task body();
            fork
                fork
                    inner_a();
                join
                outer_b();
            join_none
        endtask

        调用图:
          body
          └── [FORK/join_none]
              ├── [FORK/join]
              │   └── inner_a
              └── outer_b
        """
        source = '''class my_seq;
    task body();
        fork
            fork
                inner_a();
            join
            outer_b();
        join_none
    endtask
    task inner_a(); endtask
    task outer_b(); endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        outer_fork = cg.root.children[0]
        self.assertEqual(outer_fork.kind, 'fork')
        self.assertEqual(outer_fork.join_type, 'join_none')

        inner_fork = outer_fork.children[0]
        self.assertEqual(inner_fork.kind, 'fork')
        self.assertEqual(inner_fork.join_type, 'join')

        self.assertEqual(outer_fork.children[1].callee, 'outer_b')


class TestRandomizeDetection(unittest.TestCase):
    """Randomize 检测"""

    def test_randomize_call(self):
        """[金标准] randomize() 调用检测

        task body();
            req.randomize();
        endtask

        调用图:
          body
          └── [RANDOMIZE] req.randomize
        """
        source = '''class my_seq;
    task body();
        req.randomize();
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        self.assertEqual(len(cg.randomize_calls), 1)
        r = cg.randomize_calls[0]
        self.assertIn('randomize', r.callee)

    def test_randomize_with_inline_constraint(self):
        """[金标准] randomize() with inline constraint

        task body();
            req.randomize() with { addr inside {[0:63]}; };
        endtask

        调用图:
          body
          └── [RANDOMIZE] req.randomize
              inline: addr inside {[0:63]}
        """
        source = '''class my_seq;
    rand bit [7:0] addr;
    task body();
        req.randomize() with { addr inside {[0:63]}; };
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        self.assertEqual(len(cg.randomize_calls), 1)
        r = cg.randomize_calls[0]
        self.assertTrue(len(r.inline_constraint) > 0,
            "应提取 inline constraint 文本")


class TestIntegration(unittest.TestCase):
    """集成测试: 完整 UVM sequence 调用图"""

    def test_uvm_sequence_body(self):
        """[金标准] UVM sequence body 完整流程

        task body();
            req = my_transaction::type_id::create("req");
            start_item(req);
            req.randomize() with { addr < 64; };
            finish_item(req);
        endtask

        调用图:
          body
          ├── create
          ├── start_item
          ├── [RANDOMIZE] req.randomize
          │   inline: addr < 64
          └── finish_item
        """
        source = '''class my_seq;
    task body();
        req = create("req");
        start_item(req);
        req.randomize() with { addr inside {[0:63]}; };
        finish_item(req);
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        # 应有 4 个调用
        self.assertEqual(len(cg.root.children), 4)

        # randomize 应被标记
        self.assertEqual(len(cg.randomize_calls), 1)

    def test_fork_with_randomize(self):
        """[金标准] fork 中包含 randomize

        task body();
            fork
                req_a.randomize();
                req_b.randomize();
            join_none
        endtask

        调用图:
          body
          └── [FORK/join_none]
              ├── [RANDOMIZE] req_a.randomize
              └── [RANDOMIZE] req_b.randomize
        """
        source = '''class my_seq;
    task body();
        fork
            req_a.randomize();
            req_b.randomize();
        join_none
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        fork_node = cg.root.children[0]
        self.assertEqual(fork_node.kind, 'fork')
        self.assertEqual(len(cg.randomize_calls), 2)


if __name__ == '__main__':
    unittest.main()
