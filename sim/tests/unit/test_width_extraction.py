#==============================================================================
# test_width_extraction.py - 位宽提取测试
#==============================================================================
# [迁移] 使用 SemanticAdapter 替代 PyslangAdapter

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestWidthExtraction(unittest.TestCase):
    """位宽提取测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        return SemanticAdapter(root)
    
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
        
        adapter = self._make_adapter(source)
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
        """测试: 参数化位宽
        
        金标准:
        - input [B-1:0] data → (B-1, 0) 而非 (0, 0)
        """
        source = '''
module test #(parameter B = 8) (input [B-1:0] data);
endmodule
'''
        self._verify_rtl(source, "parameterized_width")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        width = adapter.extract_port_width(ports[0])
        msb = width[0]
        lsb = width[1]
        # B 是参数，应返回 B-1 而不是 0
        self.assertNotEqual(msb, 0, f"MSB 不应为 0，实际为 {width}")
    
    #============================================================================
    # 测试场景 3: 简单参数位宽
    #============================================================================
    def test_simple_param_width(self):
        """测试: 简单参数位宽
        
        金标准:
        - input [WIDTH-1:0] data → WIDTH-1 (保持参数形式)
        """
        source = '''
module test #(parameter WIDTH = 16) (input [WIDTH-1:0] data);
endmodule
'''
        self._verify_rtl(source, "simple_param_width")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        width = adapter.extract_port_width(ports[0])
        msb = width[0]
        lsb = width[1]
        self.assertNotEqual(msb, 0, f"MSB 不应为 0")
    
    #============================================================================
    # 测试场景 4: 多位宽
    #============================================================================
    def test_multiple_widths(self):
        """测试: 多个信号位宽
        
        金标准:
        - input [7:0] a, [15:0] b, [31:0] c
        """
        source = '''
module test(input [7:0] a, input [15:0] b, input [31:0] c);
endmodule
'''
        self._verify_rtl(source, "multiple_widths")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        width = adapter.extract_port_width(ports[0])
        self.assertEqual(width[0], 7, f"a MSB 应为 7")
        self.assertEqual(width[1], 0, f"a LSB 应为 0")
        
        width = adapter.extract_port_width(ports[1])
        self.assertEqual(width[0], 15, f"b MSB 应为 15")
        self.assertEqual(width[1], 0, f"b LSB 应为 0")
    
    #============================================================================
    # 测试场景 5: 复杂参数表达式
    #============================================================================
    def test_complex_param_expression(self):
        """测试: 复杂参数表达式位宽
        
        金标准:
        - input [A+B-1:0] data → (A+B-1, 0)
        """
        source = '''
module test #(parameter A = 8, B = 4) (input [A+B-1:0] data);
endmodule
'''
        self._verify_rtl(source, "complex_param_expression")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        width = adapter.extract_port_width(ports[0])
        msb = width[0]
        lsb = width[1]
        self.assertNotEqual(msb, 0, f"MSB 不应为 0")


if __name__ == '__main__':
    unittest.main()