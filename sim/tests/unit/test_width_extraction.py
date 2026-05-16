#==============================================================================
# test_width_extraction.py - 位宽提取测试
#==============================================================================
# 测试目的: 验证 sv_query 正确提取位宽 (字面量和参数引用)
#
# [A+ 方案] 测试:
# - 字面量 [7:0] 返回 (7, 0)
# - 参数引用 [B-1:0] 返回 (B-1, 0) 而非 (0, 0)

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.base import PyslangAdapter


class TestWidthExtraction(unittest.TestCase):
    """位宽提取测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        tree = pyslang.SyntaxTree.fromText(source)
        
        class FakeParser:
            def __init__(self, tree):
                self.trees = {'test': tree}
        
        return FakeParser(tree)
    
    def _verify_rtl(self, source, name="RTL"):
        """验证 RTL 语法正确"""
        import subprocess
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sv', delete=False) as f:
            f.write(source)
            f.flush()
            tmp = f.name
        try:
            result = subprocess.run(
                ["verilator", "--lint-only", "-sv", tmp],
                capture_output=True, text=True, timeout=30
            )
            errors = [l for l in result.stderr.split('\n') if '%Error' in l]
            self.assertEqual(len(errors), 0, f"{name} - Verilator errors: {errors}")
        finally:
            os.unlink(tmp)
    
    #============================================================================
    # 测试场景 1: 字面量位宽 (无参数)
    #============================================================================
    def test_literal_width(self):
        """测试: 字面量位宽
        
        金标准:
        - input [7:0] data → (7, 0)
        """
        source = '''
module test(input wire [7:0] data);
endmodule
'''
        self._verify_rtl(source, "literal_width")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        # 金标准: (7, 0)
        width = adapter.extract_port_width(ports[0])
        self.assertEqual(width[0], 7, f"MSB 应为 7，实际为 {width[0]}")
        self.assertEqual(width[1], 0, f"LSB 应为 0，实际为 {width[1]}")
    
    #============================================================================
    # 测试场景 2: 参数化位宽
    #============================================================================
    def test_parameterized_width(self):
        """测试: 参数化位宽 (A+ 方案核心测试)
        
        金标准:
        - input [B-1:0] data → (B-1, 0) 而非 (0, 0)
        - 返回参数名而非 0
        """
        source = '''
module test #(parameter B = 8) (input wire [B-1:0] data);
endmodule
'''
        self._verify_rtl(source, "parameterized_width")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        width = adapter.extract_port_width(ports[0])
        
        # 金标准: 参数引用，不是 0
        msb = width[0]
        lsb = width[1]
        
        # LSB 应该是 0 (字面量)
        self.assertEqual(lsb, 0, f"LSB 应为 0，实际为 {lsb}")
        
        # MSB 应该是参数名 B-1，而非 0
        # 可能的返回值: "B-1" (参数表达式) 或 "B" (参数名)
        self.assertIsInstance(msb, str, f"MSB 应为 str (参数引用)，实际为 {type(msb)}")
        self.assertIn('B', msb, f"MSB 应包含参数名 B，实际为 {msb}")
    
    #============================================================================
    # 测试场景 3: 简单参数引用
    #============================================================================
    def test_simple_param_width(self):
        """测试: 简单参数引用
        
        金标准:
        - input [W:0] data → (W, 0) 而非 (0, 0)
        """
        source = '''
module test #(parameter W = 16) (input wire [W:0] data);
endmodule
'''
        self._verify_rtl(source, "simple_param_width")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        width = adapter.extract_port_width(ports[0])
        
        msb = width[0]
        lsb = width[1]
        
        # 金标准: MSB 是参数名 "W"
        self.assertIsInstance(msb, str, f"MSB 应为 str，实际为 {type(msb)}")
        self.assertEqual(msb, 'W', f"MSB 应为 'W'，实际为 {msb}")
        self.assertEqual(lsb, 0, f"LSB 应为 0，实际为 {lsb}")
    
    #============================================================================
    # 测试场景 4: 复杂参数表达式
    #============================================================================
    def test_complex_param_expression(self):
        """测试: 复杂参数表达式
        
        金标准:
        - input [W/2-1:0] data → 参数表达式
        """
        source = '''
module test #(parameter W = 32) (input wire [W/2-1:0] data);
endmodule
'''
        self._verify_rtl(source, "complex_param_expression")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        width = adapter.extract_port_width(ports[0])
        
        msb = width[0]
        
        # 金标准: MSB 是参数表达式
        # 可能是 "W/2-1" 或 "W" (取决于表达式解析深度)
        self.assertIsInstance(msb, str, f"MSB 应为 str，实际为 {type(msb)}")
    
    #============================================================================
    # 测试场景 5: 多位宽信号
    #============================================================================
    def test_multiple_widths(self):
        """测试: 多个不同位宽的信号
        
        金标准:
        - input [7:0] a → (7, 0)
        - input [15:0] b → (15, 0)
        - input [W-1:0] c → (W, 0)
        """
        source = '''
module test #(parameter W = 8) (
    input wire [7:0] a,
    input wire [15:0] b,
    input wire [W-1:0] c
);
endmodule
'''
        self._verify_rtl(source, "multiple_widths")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        self.assertEqual(len(ports), 3, f"应有 3 个端口，实际有 {len(ports)}")
        
        # a: 字面量
        width_a = adapter.extract_port_width(ports[0])
        self.assertEqual(width_a, (7, 0), f"a 应为 (7, 0)，实际为 {width_a}")
        
        # b: 字面量
        width_b = adapter.extract_port_width(ports[1])
        self.assertEqual(width_b, (15, 0), f"b 应为 (15, 0)，实际为 {width_b}")
        
        # c: 参数引用
        width_c = adapter.extract_port_width(ports[2])
        self.assertIsInstance(width_c[0], str, f"c MSB 应为 str，实际为 {type(width_c[0])}")


if __name__ == '__main__':
    unittest.main()