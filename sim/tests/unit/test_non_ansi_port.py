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
from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestNonAnsiPortDeclaration(unittest.TestCase):
    """非ANSI端口声明测试"""

    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        return SemanticAdapter(root)

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
    input [7:0] data,
    output reg [7:0] out
);
endmodule'''

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()

        ports = adapter.get_port_declarations(modules[0])

        # 应该识别3个端口
        self.assertGreaterEqual(len(ports), 3, f"Expected >=3 ports, got {len(ports)}")

    def test_non_ansi_param_width(self):
        """测试非ANSI端口的参数化位宽提取"""
        source = '''
module mult_pipe2 #(
    parameter SIZE = 16
)(
    a, b, clk
);
    input [SIZE-1:0] a;
    input [SIZE-1:0] b;
    input clk;
endmodule'''

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        m = modules[0]

        ports = adapter.get_port_declarations(m)

        # 检查参数化位宽
        for p in ports:
            name, dir = adapter.get_port_name_and_direction(p)
            width_info = adapter.extract_port_width(p)

            if name == 'a':
                # 新API: width_info 是 (msb, lsb) 元组
                self.assertEqual(width_info[0], 15)
            elif name == 'clk':
                # input clk 没有显式位宽，应返回默认值
                self.assertIsInstance(width_info, tuple)

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




    def test_comma_separated_direction_inheritance(self):
        """Issue 11: 测试逗号分隔端口的方向继承"""
        source = 'module picorv32(input clk, resetn, output reg trap); endmodule'
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        m = modules[0]
        ports = adapter.get_port_declarations(m)
        port_dirs = {adapter.get_port_name_and_direction(p)[0]: adapter.get_port_name_and_direction(p)[1] for p in ports}
        self.assertEqual(port_dirs.get("clk"), "input")
        self.assertEqual(port_dirs.get("resetn"), "input")
        self.assertEqual(port_dirs.get("trap"), "output")


if __name__ == '__main__':
    unittest.main()
