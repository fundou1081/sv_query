#==============================================================================
# test_instance_name_extraction.py - 实例名称提取单元测试
#==============================================================================
# Issue 10: clacc反格式实例名称混淆
# 
# 测试场景:
# 1. 标准格式实例: module_name instance_name
# 2. clacc反格式: instance_name module_name
# 3. 带注释的实例名称
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.base import PyslangAdapter


class TestInstanceNameExtraction(unittest.TestCase):
    """实例名称提取测试"""
    
    def test_clacc_inverted_format(self):
        """测试 clacc 反格式实例名称提取"""
        source = '''
module pe();
    I0 dual_clock_fifo(.clk(clk), .rst(rst));
    I1 ifmap_spad(.clk(clk));
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        adapter = PyslangAdapter(parser)
        instances = adapter.get_module_instances(parser.trees)
        
        self.assertEqual(len(instances), 2)
        
        # 验证实例名称和模块类型
        name0 = adapter.get_instance_name(instances[0])
        type0 = adapter.get_instance_module_type(instances[0])
        self.assertEqual(name0, 'I0')
        self.assertEqual(type0, 'dual_clock_fifo')
        
        name1 = adapter.get_instance_name(instances[1])
        type1 = adapter.get_instance_module_type(instances[1])
        self.assertEqual(name1, 'I1')
        self.assertEqual(type1, 'ifmap_spad')
    
    def test_clacc_with_comment(self):
        """测试带注释的实例名称提取"""
        source = '''
module pe();
    /* psum */
    I2 dual_clock_fifo(.clk(clk));
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        adapter = PyslangAdapter(parser)
        instances = adapter.get_module_instances(parser.trees)
        
        self.assertEqual(len(instances), 1)
        
        name = adapter.get_instance_name(instances[0])
        type_name = adapter.get_instance_module_type(instances[0])
        
        # 注释不应该影响实例名称
        self.assertEqual(name, 'I2')
        self.assertEqual(type_name, 'dual_clock_fifo')
    
    def test_standard_format(self):
        """测试标准格式实例名称提取"""
        source = '''
module top();
    my_module inst1(.clk(clk));
    my_module inst2(.clk(clk));
endmodule'''
        
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        parser = FakeParser(tree)
        adapter = PyslangAdapter(parser)
        instances = adapter.get_module_instances(parser.trees)
        
        self.assertEqual(len(instances), 2)
        
        # 标准格式: type 在 node.type, name 在 decl.name
        name0 = adapter.get_instance_name(instances[0])
        type0 = adapter.get_instance_module_type(instances[0])
        self.assertEqual(name0, 'inst1')
        self.assertEqual(type0, 'my_module')


if __name__ == '__main__':
    unittest.main()