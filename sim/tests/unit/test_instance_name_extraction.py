#==============================================================================
# test_instance_name_extraction.py - 实例名称提取单元测试
#==============================================================================
# Issue 10: clacc反格式实例名称混淆
#
# 测试场景:
# 1. 标准格式实例: module_name instance_name
# 2. clacc反格式: instance_name module_name
# 3. 带注释的实例名称
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestInstanceNameExtraction(unittest.TestCase):
    """实例名称提取测试"""

    def test_clacc_inverted_format(self):
        """测试 clacc 反格式实例名称提取"""
        source = '''
module dual_clock_fifo(input clk, input rst);
endmodule

module ifmap_spad(input clk);
endmodule

module pe();
    dual_clock_fifo I0(.clk(clk), .rst(rst));
    ifmap_spad I1(.clk(clk));
endmodule'''

        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()

