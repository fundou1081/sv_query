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

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestExpressionEvaluation(unittest.TestCase):
    """方案 C 表达式求值测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        
