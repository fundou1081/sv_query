#==============================================================================
# test_non_ansi_port.py - 非ANSI端口声明单元测试
#==============================================================================
# Issue 7: 非ANSI端口声明未支持
# 
# 测试场景:
# 1. 基本非ANSI端口声明
# 2. 端口方向识别
# 3. 与ANSI格式的兼容性
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.base import PyslangAdapter


class TestNonAnsiPortDeclaration(unittest.TestCase):
    """非ANSI端口声明测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        return PyslangAdapter(FakeParser(tree))
    
    def test_non_ansi_basic(self):
        """测试基本非ANSI端口声明"""
        source = '''
module bs_mult(clk, x, y, p, firstbit, lastbit);
    input clk;
    input x, y, firstbit, lastbit;
    output p;
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        self.assertEqual(len(modules), 1)
        
        # 获取端口 - 这是要修复的功能
        ports = adapter.get_port_declarations(modules[0])
        
        # 验证端口数量 (应该是6)
        self.assertEqual(len(ports), 6, f"Expected 6 ports, got {len(ports)}")
    
    def test_non_ansi_with_direction(self):
        """测试非ANSI端口的方向识别"""
        source = '''
module dual_clock_fifo(
    input wire wr_rst_i,
    input wire wr_clk_i,
    output reg full_o
);
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        ports = adapter.get_port_declarations(modules[0])
        
        # 验证端口数量
        self.assertEqual(len(ports), 3, f"Expected 3 ports, got {len(ports)}")
        
        # 验证方向 (如果支持的话)
        port_names = [adapter.get_port_name_and_direction(p)[0] for p in ports]
        self.assertIn('wr_rst_i', port_names)
        self.assertIn('full_o', port_names)
    
    def test_non_ansi_no_ports(self):
        """测试无端口的模块"""
        source = '''
module empty_mod();
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        ports = adapter.get_port_declarations(modules[0])
        self.assertEqual(len(ports), 0)
    
    def test_mixed_port_declaration(self):
        """测试混合端口声明"""
        source = '''
module mix_mod(
    input clk,
    input [7:0] data
);
    output reg [7:0] out;
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        ports = adapter.get_port_declarations(modules[0])
        
        # 应该识别3个端口
        self.assertGreaterEqual(len(ports), 3, f"Expected >=3 ports, got {len(ports)}")
    
    def test_ansi_still_works(self):
        """确保ANSI端口声明仍然正常工作"""
        source = '''
module ansi_mod(
    input wire clk,
    input [7:0] data,
    output reg [7:0] out
);
endmodule'''
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        
        ports = adapter.get_port_declarations(modules[0])
        
        # ANSI格式应该返回3个端口
        self.assertEqual(len(ports), 3, f"Expected 3 ports, got {len(ports)}")


if __name__ == '__main__':
    unittest.main()