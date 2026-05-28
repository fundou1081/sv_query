# test_call_graph_uvm.py - UVM 行为模式识别测试
# [铁律13] 金标准测试
#
# Phase 2: 识别 UVM sequence/driver 行为模式
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.call_graph_builder import CallGraphBuilder
from trace.core.graph.call_graph_models import CallNode, CallGraph


def _build_call_graph(source, entry_class, entry_method):
    builder = CallGraphBuilder({'test.sv': source})
    return builder.build(entry_class, entry_method)


class TestSequencePattern(unittest.TestCase):
    """Sequence 行为模式识别"""

    def test_standard_uvm_sequence_body(self):
        """[金标准] 标准 UVM sequence body 流程

        task body();
            req = create("req");
            start_item(req);
            req.randomize() with { addr < 64; };
            finish_item(req);
        endtask

        期望识别:
          [SEQUENCE] body
            → create transaction: req
            → start_item
            → randomize (addr)
            → finish_item
        """
        source = '''class req_cls;
    rand bit [7:0] addr;
endclass
class my_seq;
    req_cls req;
    task create(string s); req = new(); endtask
    task start_item(req_cls r); endtask
    task finish_item(req_cls r); endtask
    task body();
        create("req");
        start_item(req);
        req.randomize() with { addr inside {[0:63]}; };
        finish_item(req);
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        # 应标记为 sequence 模式
        self.assertEqual(cg.root.pattern, 'sequence',
            "body 应被识别为 sequence 模式")

        # 应有 create, start_item, randomize, finish_item
        call_names = [c.callee for c in cg.root.children]
        self.assertIn('create', call_names)
        self.assertIn('start_item', call_names)
        self.assertIn('finish_item', call_names)
        self.assertEqual(len(cg.randomize_calls), 1)

    def test_sequence_with_loop(self):
        """[金标准] sequence 循环发送

        task body();
            repeat(10) begin
                req = create("req");
                start_item(req);
                req.randomize();
                finish_item(req);
            end
        endtask
        """
        source = '''class req_cls;
    rand bit [7:0] addr;
endclass
class my_seq;
    req_cls req;
    task create(string s); req = new(); endtask
    task start_item(req_cls r); endtask
    task finish_item(req_cls r); endtask
    task body();
        repeat(10) begin
            create("req");
            start_item(req);
            req.randomize();
            finish_item(req);
        end
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        # 应识别为 sequence 模式
        self.assertEqual(cg.root.pattern, 'sequence')

    def test_sequence_with_multiple_items(self):
        """[金标准] sequence 发送多个 transaction

        task body();
            req_a = create("req_a");
            start_item(req_a);
            req_a.randomize();
            finish_item(req_a);

            req_b = create("req_b");
            start_item(req_b);
            req_b.randomize();
            finish_item(req_b);
        endtask
        """
        source = '''class req_cls;
    rand bit [7:0] addr;
endclass
class my_seq;
    req_cls req_a;
    req_cls req_b;
    task create(string s); endtask
    task start_item(req_cls r); endtask
    task finish_item(req_cls r); endtask
    task body();
        create("req_a");
        start_item(req_a);
        req_a.randomize();
        finish_item(req_a);
        create("req_b");
        start_item(req_b);
        req_b.randomize();
        finish_item(req_b);
    endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_seq', 'body')

        self.assertEqual(cg.root.pattern, 'sequence')
        self.assertEqual(len(cg.randomize_calls), 2)


class TestDriverPattern(unittest.TestCase):
    """Driver 行为模式识别"""

    def test_standard_uvm_driver(self):
        """[金标准] 标准 UVM driver run_phase

        task run_phase(uvm_phase phase);
            forever begin
                seq_item_port.get_next_item(req);
                drive(req);
                seq_item_port.item_done();
            end
        endtask

        期望识别:
          [DRIVER] run_phase
            → get_next_item
            → drive
            → item_done
        """
        source = '''class req_cls;
    rand bit [7:0] addr;
endclass
class my_driver;
    req_cls req;
    task get_next_item(output req_cls r); r = new(); endtask
    task item_done(); endtask
    task run_phase();
        forever begin
            get_next_item(req);
            drive(req);
            item_done();
        end
    endtask
    task drive(req_cls c); endtask
endclass
module top; endmodule'''
        cg = _build_call_graph(source, 'my_driver', 'run_phase')

        self.assertEqual(cg.root.pattern, 'driver')

        # 应有 get_next_item, drive, item_done
        call_names = [c.callee for c in cg.root.children]
        self.assertIn('get_next_item', call_names)
        self.assertIn('item_done', call_names)


class TestPatternDetection(unittest.TestCase):
    """模式自动检测"""

    def test_auto_detect_sequence(self):
        """[金标准] 自动检测 sequence 模式 (无需指定)"""
        source = '''class req_cls;
    rand bit [7:0] addr;
endclass
class my_seq;
    req_cls req;
    task create(string s); req = new(); endtask
    task start_item(req_cls r); endtask
    task finish_item(req_cls r); endtask
    task body();
        create("req");
        start_item(req);
        req.randomize();
        finish_item(req);
    endtask
endclass
module top; endmodule'''
        builder = CallGraphBuilder({'test.sv': source})
        cg = builder.build('my_seq', 'body')

        self.assertEqual(cg.root.pattern, 'sequence')

    def test_auto_detect_driver(self):
        """[金标准] 自动检测 driver 模式"""
        source = '''class req_cls;
    rand bit [7:0] addr;
endclass
class my_driver;
    req_cls req;
    task get_next_item(output req_cls r); r = new(); endtask
    task item_done(); endtask
    task run_phase();
        forever begin
            get_next_item(req);
            drive(req);
            item_done();
        end
    endtask
    task drive(req_cls c); endtask
endclass
module top; endmodule'''
        builder = CallGraphBuilder({'test.sv': source})
        cg = builder.build('my_driver', 'run_phase')

        self.assertEqual(cg.root.pattern, 'driver')

    def test_generic_task_no_pattern(self):
        """[负面] 普通 task 不标记模式"""
        source = '''class util;
    task do_work();
        compute();
        store();
    endtask
    task compute(); endtask
    task store(); endtask
endclass
module top; endmodule'''
        builder = CallGraphBuilder({'test.sv': source})
        cg = builder.build('util', 'do_work')

        self.assertEqual(cg.root.pattern, 'generic')


class TestSequenceDriverIntegration(unittest.TestCase):
    """Sequence + Driver 集成"""

    def test_sequence_driver_call_chain(self):
        """[金标准] sequence → driver 完整调用链

        sequence::body
        ├── create
        ├── start_item
        ├── randomize
        └── finish_item
            └── driver::run_phase (via sequencer)
                ├── get_next_item
                ├── drive
                └── item_done
        """
        source = '''class req_cls;
    rand bit [7:0] addr;
endclass
class my_seq;
    req_cls req;
    task create(string s); req = new(); endtask
    task start_item(req_cls r); endtask
    task finish_item(req_cls r); endtask
    task body();
        create("req");
        start_item(req);
        req.randomize() with { addr inside {[0:63]}; };
        finish_item(req);
    endtask
endclass

class my_driver;
    req_cls req;
    task get_next_item(output req_cls r); r = new(); endtask
    task item_done(); endtask
    task run_phase();
        forever begin
            get_next_item(req);
            drive(req);
            item_done();
        end
    endtask
    task drive(req_cls c); endtask
endclass
module top; endmodule'''
        builder = CallGraphBuilder({'test.sv': source})

        # 构建 sequence 调用图
        seq_cg = builder.build('my_seq', 'body')
        self.assertEqual(seq_cg.root.pattern, 'sequence')
        self.assertEqual(len(seq_cg.randomize_calls), 1)

        # 构建 driver 调用图
        drv_cg = builder.build('my_driver', 'run_phase')
        self.assertEqual(drv_cg.root.pattern, 'driver')


if __name__ == '__main__':
    unittest.main()
