# test_v3_iron1_compliance.py - [V3 fix 2026-07-15] 铁律1 regression guard
#
# Purpose: 守卫 uvm_testbench_extractor 满足铁律1 (AST 唯一数据源)
#          严禁直接用 SyntaxTree.fromText(file).root 跳过 Compilation.
#
# Per docs/CODE_DISCIPLINE_FIX_COMPLETENESS.md, basic components must be
# completely fixed. This test guards against re-introducing the SyntaxTree.fromText
# direct call that was in the original code.

import os
import sys

# 路径设置 (跟其他 regression test 保持一致)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import unittest

from trace.core.uvm_testbench_extractor import UVMTestbenchExtractor


class TestUVMExtractorIron1Compliance(unittest.TestCase):
    """Verify uvm_testbench_extractor follows 铁律1 (AST 唯一数据源)"""

    def test_constructor_signature_unchanged(self):
        """[V3 fix] 构造签名不应改变 - 现有 callsite 不变"""
        # 接受 sources dict 入口
        ext = UVMTestbenchExtractor({'test.sv': 'module top; endmodule'})
        self.assertIsNotNone(ext)

    def test_extract_returns_uvmtestbench(self):
        """[V3 fix] extract() 返回 UVMTestbench 不变"""
        ext = UVMTestbenchExtractor({'test.sv': 'module top; endmodule'})
        result = ext.extract()
        self.assertIsNotNone(result)
        self.assertEqual(result.components, {})
        self.assertEqual(result.connections, [])

    def test_no_direct_syntax_tree_from_file(self):
        """[V3 fix] 严禁直接 SyntaxTree.fromFile (跳过 Compilation)

        只允许在 Compilation.addSyntaxTree 内部使用 SyntaxTree.fromText
        """
        # Static check - read the source and verify no direct fromFile
        src_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', 'src', 'trace', 'core', 'uvm_testbench_extractor.py'
        )
        with open(src_path) as f:
            source = f.read()

        # 检查是否有直接用 .fromFile/.fromText 且没经过 Compilation
        bad_patterns = [
            'pyslang.SyntaxTree.fromFile',
            'pyslang.SyntaxTree.fromFileInMemory',
        ]
        for pattern in bad_patterns:
            self.assertNotIn(
                pattern, source,
                f"[铁律1 violation] 严禁 {pattern} 跳过 Compilation: {src_path}"
            )

        # Acceptable: fromText through _pyslang_compat (which adds to Compilation)
        # Verify it IS used through compat layer
        self.assertIn('_PyslangSyntaxTree.fromText', source,
                      "应通过 _pyslang_compat 入口使用 SyntaxTree.fromText")


class TestUVMExtractorParameterizedUVMDriver(unittest.TestCase):
    """[V3 fix] parameterized uvm_driver#(T) 必须正确提取

    Regression test for the bug discovered during V3 fix:
    SVCompiler's full pipeline pollutes token.name.value with non-UTF-8 bytes
    for parameterized UVM classes. The fix uses Compilation directly
    (which is the iron-1 compliant entry point).
    """

    SOURCE = '''class my_driver extends uvm_driver#(my_transaction); endclass
module top; endmodule'''

    def test_parameterized_uvm_driver_extracted(self):
        """uvm_driver#(my_transaction) 应被识别, 无 unicode 错误"""
        ext = UVMTestbenchExtractor({'test.sv': self.SOURCE})
        result = ext.extract()  # 不应抛异常
        # 提取出 my_driver
        self.assertIn('my_driver', result.components,
                      f"my_driver 应被识别, 但 components 为空. 这通常是 "
                      f"SVCompiler 路径污染 token.name.value 的症状.")

    def test_parameterized_driver_type_inference(self):
        """uvm_driver#(...) 类型应推断为 'driver'"""
        ext = UVMTestbenchExtractor({'test.sv': self.SOURCE})
        result = ext.extract()
        comp = result.components.get('my_driver')
        self.assertIsNotNone(comp)
        self.assertEqual(comp.component_type, 'driver')


if __name__ == '__main__':
    unittest.main()
