#==============================================================================
# test_expression_evaluation.py - 方案 C 表达式求值测试
#==============================================================================
# 测试目的: 验证 sv_query 能够对参数化位宽进行表达式求值
#
# 方案 C 功能:
# - 从模块参数构建 param_map
# - 对参数化位宽表达式进行求值
# - 返回 (原始表达式, 求值结果) 的元组
#
# 金标准测试原则:
# - 先推导金标准，从 RTL 人工推导预期结果
# - RTL 必须来自真实场景
# - 使用 Verilator 验证语法正确

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.base import PyslangAdapter


class TestExpressionEvaluation(unittest.TestCase):
    """方案 C 表达式求值测试"""
    
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
    # 测试场景 1: 简单参数 (无表达式)
    #============================================================================
    def test_simple_param_no_expression(self):
        """测试: 简单参数引用 (无表达式)
        
        金标准:
        - 参数 W=16, 位宽 [W:0]
        - 求值结果: (W, 0) -> (16, 0)
        """
        source = '''
module test #(parameter W = 16) (input wire [W:0] data);
endmodule
'''
        self._verify_rtl(source, "simple_param_no_expression")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        params = adapter.get_module_parameters(modules[0])
        ports = adapter.get_port_declarations(modules[0])
        
        # 构建 param_map
        param_map = {}
        for p in params:
            try:
                param_map[p['name']] = int(p['value'])
            except ValueError:
                pass  # 忽略无法解析的参数值
        
        self.assertEqual(param_map.get('W'), 16, f"W 应为 16，实际为 {param_map.get('W')}")
        
        # 提取位宽 (带求值)
        result = adapter.extract_port_width_with_eval(ports[0], param_map)
        
        # 金标准: msb 求值为 16
        self.assertEqual(result['msb_eval'], 16, f"msb_eval 应为 16，实际为 {result['msb_eval']}")
        self.assertEqual(result['lsb_eval'], 0, f"lsb_eval 应为 0，实际为 {result['lsb_eval']}")
    
    #============================================================================
    # 测试场景 2: 减法表达式 (B-1)
    #============================================================================
    def test_subtract_expression(self):
        """测试: 减法表达式
        
        金标准:
        - 参数 B=8, 位宽 [B-1:0]
        - 求值结果: (B-1, 0) -> (7, 0)
        """
        source = '''
module test #(parameter B = 8) (input wire [B-1:0] data);
endmodule
'''
        self._verify_rtl(source, "subtract_expression")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        params = adapter.get_module_parameters(modules[0])
        ports = adapter.get_port_declarations(modules[0])
        
        # 构建 param_map
        param_map = {}
        for p in params:
            try:
                param_map[p['name']] = int(p['value'])
            except ValueError:
                pass
        
        result = adapter.extract_port_width_with_eval(ports[0], param_map)
        
        # 金标准: B-1 = 8-1 = 7
        self.assertEqual(result['msb_eval'], 7, f"msb_eval 应为 7，实际为 {result['msb_eval']}")
        self.assertEqual(result['msb_raw'], 'B-1', f"msb_raw 应为 'B-1'，实际为 {result['msb_raw']}")
    
    #============================================================================
    # 测试场景 3: 除法表达式 (W/2)
    #============================================================================
    def test_divide_expression(self):
        """测试: 除法表达式
        
        金标准:
        - 参数 W=32, 位宽 [W/2-1:0]
        - 求值结果: (W/2-1, 0) -> (15, 0)
        """
        source = '''
module test #(parameter W = 32) (input wire [W/2-1:0] data);
endmodule
'''
        self._verify_rtl(source, "divide_expression")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        params = adapter.get_module_parameters(modules[0])
        ports = adapter.get_port_declarations(modules[0])
        
        # 构建 param_map
        param_map = {}
        for p in params:
            try:
                param_map[p['name']] = int(p['value'])
            except ValueError:
                pass
        
        result = adapter.extract_port_width_with_eval(ports[0], param_map)
        
        # 金标准: W/2-1 = 32/2-1 = 15
        self.assertEqual(result['msb_eval'], 15, f"msb_eval 应为 15，实际为 {result['msb_eval']}")
        self.assertEqual(result['msb_raw'], 'W/2-1', f"msb_raw 应为 'W/2-1'，实际为 {result['msb_raw']}")
    
    #============================================================================
    # 测试场景 4: 字面量 (无参数)
    #============================================================================
    def test_literal_only(self):
        """测试: 字面量位宽 (无参数)
        
        金标准:
        - 位宽 [7:0]，无参数
        - 求值结果: (7, 0)
        """
        source = '''
module test(input wire [7:0] data);
endmodule
'''
        self._verify_rtl(source, "literal_only")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        # 无参数
        param_map = {}
        
        result = adapter.extract_port_width_with_eval(ports[0], param_map)
        
        # 金标准: 字面量 7
        self.assertEqual(result['msb_eval'], 7, f"msb_eval 应为 7，实际为 {result['msb_eval']}")
        self.assertEqual(result['msb_raw'], None, f"msb_raw 应为 None，实际为 {result['msb_raw']}")
    
    #============================================================================
    # 测试场景 5: 参数未在 param_map 中提供时
    #============================================================================
    def test_missing_param_in_map(self):
        """测试: 参数在模块中定义但未传入 param_map 时返回 None
        
        金标准:
        - 参数 W=16 在模块中定义
        - 但 param_map 为空 (未提供)
        - 求值结果: msb_eval = None (无法求值，因为 param_map 中没有 W)
        """
        source = '''
module test #(parameter W = 16) (input wire [W:0] data);
endmodule
'''
        self._verify_rtl(source, "missing_param_in_map")
        
        parser = self._make_adapter(source)
        adapter = PyslangAdapter(parser)
        
        modules = adapter.get_modules()
        ports = adapter.get_port_declarations(modules[0])
        
        # 空 param_map (W 未传入)
        param_map = {}
        
        result = adapter.extract_port_width_with_eval(ports[0], param_map)
        
        # 金标准: 无法求值，msb_eval 为 None
        self.assertIsNone(result['msb_eval'], f"msb_eval 应为 None，实际为 {result['msb_eval']}")
        self.assertEqual(result['msb_raw'], 'W', f"msb_raw 应为 'W'，实际为 {result['msb_raw']}")
        self.assertTrue(result['msb_is_param'], f"msb_is_param 应为 True")


if __name__ == '__main__':
    unittest.main()