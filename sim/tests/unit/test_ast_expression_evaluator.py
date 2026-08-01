#==============================================================================
# test_ast_expression_evaluator.py - 理想方案 AST 递归求值器测试
#==============================================================================
# 测试目的: 验证基于 AST SyntaxKind 的递归表达式求值器
#
# Step 1: 先写测试用例 (项目纪律)
# - 简单参数
# - 二元表达式 (+, -, *, /, %)
# - 括号表达式
# - 参数引用参数
# - 一元表达式

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler


class TestASTExpressionEvaluator(unittest.TestCase):
    """AST 递归求值器测试"""

    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        comp = SVCompiler({'test.sv': source})
        comp.get_root()

