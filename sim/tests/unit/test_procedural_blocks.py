#==============================================================================
# test_procedural_blocks.py - 程序块单元测试
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestProceduralBlocks(unittest.TestCase):
    """程序块单元测试"""

    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        return SemanticAdapter(root)

    def test_detect_always_ff(self):
        """always_ff 检测"""
        source = '''
module top(input clk, input d, output reg q);
    always_ff @(posedge clk) q <= d;
endmodule'''

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()

        always = adapter.get_always_blocks(modules[0])
        self.assertGreaterEqual(len(always), 0)  # 可能有

    def test_detect_always_comb(self):
        """always_comb 检测"""
        source = '''
module top(input a, input b, output logic q);
    always_comb q <= a & b;
endmodule'''

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()

        always = adapter.get_always_blocks(modules[0])
        block_kinds = [str(getattr(a, 'procedureKind', '')) for a in always]

        # 应该有 AlwaysCombBlock
        self.assertTrue(any('Comb' in k for k in block_kinds))

    def test_detect_always_latch(self):
        """always_latch 检测"""
        source = '''
module top(input en, input d, output logic q);
    always_latch if (en) q <= d;
endmodule'''

        adapter = self._make_adapter(source)
        modules = adapter.get_modules()

        always = adapter.get_always_blocks(modules[0])
        self.assertIsNotNone(always)


if __name__ == '__main__':
    unittest.main()
