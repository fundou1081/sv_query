#==============================================================================
# test_param_expression_resolution.py - 参数引用参数递归求值测试
#==============================================================================
# [迁移] 使用 SemanticAdapter 替代 PyslangAdapter
# extract_port_width() 返回 (msb, lsb) 元组，而非字典

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestParamExpressionResolution(unittest.TestCase):
    """参数引用参数递归求值测试"""
    
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
    # 场景 1: 简单参数引用参数 (B=A*2)
    #============================================================================
    def test_param_referencing_param_simple(self):
        """测试: B=A*2, A=4 -> B=8
        
        金标准: [B:0] -> msb=8
        """
        source = '''
module test #(parameter A = 4, B = A*2) (input wire [B:0] data);
endmodule
'''
        self._verify_rtl(source, "param_ref_simple")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        # extract_port_width 返回 (msb, lsb) 元组
        result = adapter.extract_port_width(ports[0])
        
        self.assertEqual(result[0], 8, f"msb 应为 8，实际为 {result[0]}")
    
    #============================================================================
    # 场景 2: 链式参数引用 (C=B*2, B=A+1, A=3 -> C=8)
    #============================================================================
    def test_chained_param_references(self):
        """测试: 链式参数引用 C=B*2, B=A+1, A=3 -> C=8
        
        金标准: [C:0] -> msb=8
        """
        source = '''
module test #(parameter A = 3, B = A+1, C = B*2) (input wire [C:0] data);
endmodule
'''
        self._verify_rtl(source, "chained_params")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        result = adapter.extract_port_width(ports[0])
        
        self.assertEqual(result[0], 8, f"msb 应为 8，实际为 {result[0]}")
    
    #============================================================================
    # 场景 3: 参数引用在除法中 (B=A/2, A=16 -> B=8)
    #============================================================================
    def test_param_referencing_divide(self):
        """测试: B=A/2, A=16 -> B=8
        
        金标准: [B:0] -> msb=8
        """
        source = '''
module test #(parameter A = 16, B = A/2) (input wire [B:0] data);
endmodule
'''
        self._verify_rtl(source, "param_ref_divide")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        result = adapter.extract_port_width(ports[0])
        
        self.assertEqual(result[0], 8, f"msb 应为 8，实际为 {result[0]}")
    
    #============================================================================
    # 场景 4: 参数引用在减法中 (B=A-1, A=16 -> B=15)
    #============================================================================
    def test_param_referencing_subtract(self):
        """测试: B=A-1, A=16 -> B=15
        
        金标准: [B:0] -> msb=15
        """
        source = '''
module test #(parameter A = 16, B = A-1) (input wire [B:0] data);
endmodule
'''
        self._verify_rtl(source, "param_ref_subtract")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        result = adapter.extract_port_width(ports[0])
        
        self.assertEqual(result[0], 15, f"msb 应为 15，实际为 {result[0]}")
    
    #============================================================================
    # 场景 5: 复杂表达式引用 (D=A+B*C, A=2, B=3, C=4 -> D=14)
    #============================================================================
    def test_param_referencing_complex_expr(self):
        """测试: D=A+B*C, A=2, B=3, C=4 -> D=14
        
        金标准: [D:0] -> msb=14
        """
        source = '''
module test #(parameter A = 2, B = 3, C = 4, D = A+B*C) (input wire [D:0] data);
endmodule
'''
        self._verify_rtl(source, "param_ref_complex")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        result = adapter.extract_port_width(ports[0])
        
        self.assertEqual(result[0], 14, f"msb 应为 14，实际为 {result[0]}")
    
    #============================================================================
    # 场景 6: 参数引用参数在位宽中使用 (端口使用引用参数的参数)
    #============================================================================
    def test_param_referencing_in_width(self):
        """测试: E=D/2, D=C*2, C=B+1, B=4 -> E=5
        
        金标准: [E:0] -> msb=5
        """
        source = '''
module test #(parameter B = 4, C = B+1, D = C*2, E = D/2) (input wire [E:0] data);
endmodule
'''
        self._verify_rtl(source, "param_ref_deep_chain")
        
        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        result = adapter.extract_port_width(ports[0])
        
        self.assertEqual(result[0], 5, f"msb 应为 5，实际为 {result[0]}")


if __name__ == '__main__':
    unittest.main()