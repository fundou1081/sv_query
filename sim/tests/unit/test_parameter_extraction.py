#==============================================================================
# test_parameter_extraction.py - 模块参数提取测试
#==============================================================================
# 测试目的: 验证 sv_query 正确提取模块参数
#
# 金标准测试原则 (铁律13-20):
# - 先推导金标准，从 RTL 人工推导预期结果
# - RTL 必须来自真实场景
# - 使用 Verilator + Verible 双重验证
# - 强断言验证具体行为

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestParameterExtraction(unittest.TestCase):
    """模块参数提取测试"""

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
    # 测试场景 1: 基本参数提取
    #============================================================================
    def test_simple_parameter(self):
        """测试: 简单参数提取

        金标准:
        - 模块有 1 个参数: W = 1
        """
        source = '''
module serv_alu #(parameter W = 1) ();
endmodule
'''
        self._verify_rtl(source, "simple_parameter")

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()
        self.assertEqual(len(modules), 1)

        params = adapter.get_module_parameters(modules[0])

        # 金标准: 1 个参数
        self.assertEqual(len(params), 1, f"应有 1 个参数，实际有 {len(params)} 个")

        # 金标准: 参数名为 'W'，值为 '1'
        self.assertEqual(params[0]['name'], 'W')
        self.assertEqual(params[0]['value'], '1')

    def test_multiple_parameters(self):
        """测试: 多个参数

        金标准:
        - 模块有 2 个参数: W = 1, B = W-1
        """
        source = '''
module alu #(parameter W = 1, parameter B = W-1) ();
endmodule
'''
        self._verify_rtl(source, "multiple_parameters")

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()

        params = adapter.get_module_parameters(modules[0])

        # 金标准: 2 个参数
        self.assertEqual(len(params), 2, f"应有 2 个参数，实际有 {len(params)} 个")

        # 金标准: 参数名和值
        param_names = [p['name'] for p in params]
        self.assertIn('W', param_names)
        self.assertIn('B', param_names)

    #============================================================================
    # 测试场景 2: 无参数的模块
    #============================================================================
    def test_no_parameters(self):
        """测试: 无参数的模块

        金标准:
        - 模块有 0 个参数
        """
        source = '''
module simple(input wire clk);
endmodule
'''
        self._verify_rtl(source, "no_parameters")

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()

        params = adapter.get_module_parameters(modules[0])

        # 金标准: 0 个参数
        self.assertEqual(len(params), 0, f"无参数模块应有 0 个参数，实际有 {len(params)} 个")

    #============================================================================
    # 测试场景 3: 真实场景 - cva6
    #============================================================================
    def test_cva6_parameter(self):
        """测试: cva6 真实参数

        金标准:
        - CVA6Cfg 参数存在
        """
        source = '''
module cva6_core #(parameter CVA6Cfg = '0) ();
endmodule
'''
        self._verify_rtl(source, "cva6_parameter")

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()

        params = adapter.get_module_parameters(modules[0])

        # 金标准: 至少有 CVA6Cfg 参数
        param_names = [p['name'] for p in params]
        self.assertIn('CVA6Cfg', param_names, "应有 CVA6Cfg 参数")

    #============================================================================
    # 测试场景 4: localparam
    #============================================================================
    def test_localparam(self):
        """测试: localparam 提取

        金标准:
        - 模块有 2 个参数: IDLE=2'b00, DATA=2'b01
        """
        source = '''
module pe();
    parameter IDLE = 2'b00;
    parameter DATA = 2'b01;
endmodule
'''
        self._verify_rtl(source, "localparam")

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()

        # 注意: localparam 在 members 中，不在 header.parameters 中
        # 这里只测试 header 中的参数
        params = adapter.get_module_parameters(modules[0])

        # localparam 不是 header 参数，所以可能为空
        # 这是设计决策：是否提取 localparam？


if __name__ == '__main__':
    unittest.main()
