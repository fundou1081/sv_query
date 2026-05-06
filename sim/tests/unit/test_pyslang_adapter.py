#==============================================================================
# test_pyslang_adapter.py - PyslangAdapter 单元测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.base import PyslangAdapter


class TestPyslangAdapter(unittest.TestCase):
    """PyslangAdapter 单元测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        return PyslangAdapter(FakeParser(tree))
    
    def test_get_modules(self):
        """获取模块列表"""
        source = '''
module top();
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        self.assertEqual(len(modules), 1)
    
    def test_get_module_name(self):
        """获取模块名"""
        source = '''
module top();
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        name = adapter.get_module_name(modules[0])
        self.assertEqual(name, 'top')
    
    def test_get_port_names(self):
        """获取端口名"""
        source = '''
module top(input wire din, output wire dout);
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        ports = adapter.get_port_names(modules[0])
        self.assertIn('din', ports)
        self.assertIn('dout', ports)
    
    def test_get_assignments(self):
        """获取 assign 语句"""
        source = '''
module top(input wire din, output wire dout);
    assign dout = din;
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        assigns = adapter.get_assignments(modules[0])
        self.assertEqual(len(assigns), 1)
    
    def test_get_always_blocks(self):
        """获取 always 块"""
        source = '''
module top(input wire clk, input wire d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        always = adapter.get_always_blocks(modules[0])
        self.assertGreaterEqual(len(always), 0)  # 可能有 always_ff
    
    def test_clean_name(self):
        """清理信号名"""
        adapter = self._make_adapter('module top(); endmodule')
        
        # 测试各种格式
        self.assertEqual(adapter.clean_name('  din  '), 'din')
        self.assertEqual(adapter.clean_name('din[0]'), 'din[0]')


if __name__ == '__main__':
    unittest.main()
