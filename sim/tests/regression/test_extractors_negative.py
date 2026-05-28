# test_extractors_negative.py - 提取器负面测试
# [铁律18] 负面测试
#
# 测试边界条件：空输入、无效入口、非 UVM 代码、编译错误
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.covergroup_extractor import CovergroupExtractor
from trace.core.call_graph_builder import CallGraphBuilder
from trace.core.uvm_testbench_extractor import UVMTestbenchExtractor


# =========================================================================
# CovergroupExtractor 负面测试
# =========================================================================

class TestCovergroupExtractorNegative(unittest.TestCase):

    def test_empty_source(self):
        """[负面] 空源码返回空列表"""
        extractor = CovergroupExtractor({'test.sv': ''})
        result = extractor.extract()
        self.assertEqual(len(result), 0)

    def test_no_covergroup(self):
        """[负面] 无 covergroup 时返回空列表"""
        source = '''module top(input clk, logic [7:0] data);
    always_ff @(posedge clk) data <= data + 1;
endmodule'''
        extractor = CovergroupExtractor({'test.sv': source})
        result = extractor.extract()
        self.assertEqual(len(result), 0)

    def test_module_only_no_class(self):
        """[负面] 只有 module 没有 covergroup"""
        source = '''module top(input clk);
    logic [7:0] counter;
    always_ff @(posedge clk) counter <= counter + 1;
endmodule'''
        extractor = CovergroupExtractor({'test.sv': source})
        result = extractor.extract()
        self.assertEqual(len(result), 0)

    def test_syntax_error_graceful(self):
        """[负面] 语法错误不应崩溃"""
        source = '''module top(
    // 故意的语法错误
    logic [7:0] data
endmodule'''
        extractor = CovergroupExtractor({'test.sv': source})
        # 不应抛出异常
        result = extractor.extract()
        self.assertIsInstance(result, list)

    def test_multiple_files_one_empty(self):
        """[负面] 多文件其中一个为空"""
        extractor = CovergroupExtractor({
            'empty.sv': '',
            'valid.sv': '''module top; endmodule'''
        })
        result = extractor.extract()
        self.assertIsInstance(result, list)


# =========================================================================
# CallGraphBuilder 负面测试
# =========================================================================

class TestCallGraphBuilderNegative(unittest.TestCase):

    def test_invalid_entry_class(self):
        """[负面] 不存在的类名应返回错误"""
        source = '''class my_seq;
    task body();
        do_something();
    endtask
endclass
module top; endmodule'''
        builder = CallGraphBuilder({'test.sv': source})
        cg = builder.build('nonexistent_class', 'body')
        self.assertGreater(len(cg.errors), 0, "不存在的类应有错误信息")

    def test_invalid_entry_method(self):
        """[负面] 不存在的方法名"""
        source = '''class my_seq;
    task body();
        do_something();
    endtask
endclass
module top; endmodule'''
        builder = CallGraphBuilder({'test.sv': source})
        cg = builder.build('my_seq', 'nonexistent_method')
        self.assertIsNotNone(cg)

    def test_empty_class(self):
        """[负面] 空 class"""
        source = '''class empty_class;
endclass
module top; endmodule'''
        builder = CallGraphBuilder({'test.sv': source})
        cg = builder.build('empty_class', 'body')
        self.assertIsNotNone(cg)

    def test_no_classes(self):
        """[负面] 没有 class 定义"""
        source = '''module top;
    logic [7:0] data;
endmodule'''
        builder = CallGraphBuilder({'test.sv': source})
        cg = builder.build('top', 'data')
        self.assertIsNotNone(cg)

    def test_syntax_error_graceful(self):
        """[负面] 语法错误不应崩溃"""
        source = '''class my_seq;
    task body(
        // 故意的语法错误
    endtask
endclass'''
        builder = CallGraphBuilder({'test.sv': source})
        cg = builder.build('my_seq', 'body')
        self.assertIsInstance(cg.errors, list)


# =========================================================================
# UVMTestbenchExtractor 负面测试
# =========================================================================

class TestUVMTestbenchExtractorNegative(unittest.TestCase):

    def test_empty_source(self):
        """[负面] 空源码返回空结构"""
        extractor = UVMTestbenchExtractor({'test.sv': ''})
        tb = extractor.extract()
        self.assertEqual(len(tb.components), 0)
        self.assertEqual(len(tb.connections), 0)

    def test_non_uvm_code(self):
        """[负面] 非 UVM 代码返回空结构"""
        source = '''module top(input clk, logic [7:0] data);
    logic [7:0] counter;
    always_ff @(posedge clk) counter <= data + 1;
endmodule'''
        extractor = UVMTestbenchExtractor({'test.sv': source})
        tb = extractor.extract()
        self.assertEqual(len(tb.components), 0)

    def test_plain_class_no_uvm(self):
        """[负面] 普通 class（非 UVM 组件）"""
        source = '''class my_data;
    int value;
    function new(int v);
        value = v;
    endfunction
endclass
module top; endmodule'''
        extractor = UVMTestbenchExtractor({'test.sv': source})
        tb = extractor.extract()
        # my_data 不是 uvm 组件，不应被识别为组件
        self.assertEqual(len(tb.components), 0)

    def test_syntax_error_graceful(self):
        """[负面] 语法错误不应崩溃"""
        source = '''class my_env extends uvm_env;
    function void build_phase(
        // 故意的语法错误
    endfunction
endclass'''
        extractor = UVMTestbenchExtractor({'test.sv': source})
        tb = extractor.extract()
        self.assertIsInstance(tb.components, dict)

    def test_multiple_files_one_empty(self):
        """[负面] 多文件其中一个为空"""
        extractor = UVMTestbenchExtractor({
            'empty.sv': '',
            'valid.sv': '''module top; endmodule'''
        })
        tb = extractor.extract()
        self.assertIsInstance(tb.components, dict)

    def test_dot_output_empty(self):
        """[负面] 空图的 DOT 输出"""
        extractor = UVMTestbenchExtractor({'test.sv': ''})
        tb = extractor.extract()
        dot = tb.to_dot()
        self.assertIn('digraph', dot)

    def test_mermaid_output_empty(self):
        """[负面] 空图的 Mermaid 输出"""
        extractor = UVMTestbenchExtractor({'test.sv': ''})
        tb = extractor.extract()
        mermaid = tb.to_mermaid()
        self.assertIn('graph TD', mermaid)


if __name__ == '__main__':
    unittest.main()
