#==============================================================================
# test_semantic_adapter.py - SemanticAdapter 单元测试
#==============================================================================
# [迁移] 从 test_pyslang_adapter.py 迁移到 SemanticAdapter
# 新 API 使用源文本 + Semantic AST，不再使用 SyntaxTree

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestSemanticAdapter(unittest.TestCase):
    """SemanticAdapter 单元测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        compiler = SVCompiler({'test.sv': source})
        root = compiler.get_root()
        return SemanticAdapter(root)
    
    def test_get_modules(self):
        """获取模块列表"""
        source = '''
module top();
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        self.assertEqual(len(modules), 1)
        self.assertEqual(adapter.get_module_name(modules[0]), 'top')
    
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
        """获取端口名列表"""
        source = '''
module top(input a, output b);
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        ports = adapter.get_port_names(modules[0])
        self.assertEqual(len(ports), 2)
        self.assertIn('a', ports)
        self.assertIn('b', ports)
    
    def test_get_assignments(self):
        """获取连续赋值语句"""
        source = '''
module top(input a, output b);
    assign b = a;
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        assigns = adapter.get_assignments(modules[0])
        self.assertEqual(len(assigns), 1)
    
    def test_get_always_blocks(self):
        """获取 always 块"""
        source = '''
module top(input clk, output reg q);
    always @(posedge clk) begin
        q <= 1'b0;
    end
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        always = adapter.get_always_blocks(modules[0])
        self.assertGreaterEqual(len(always), 1)


if __name__ == '__main__':
    unittest.main()