#==============================================================================
# test_connection_tracing.py - 连接追踪测试
#==============================================================================
# 测试目的: 验证 sv_query 正确提取实例端口连接
#
# 金标准测试原则 (铁律13-20):
# - 先推导金标准，从 RTL 人工推导预期结果
# - RTL 必须来自真实场景
# - 使用 Verilator 验证语法正确
# - 强断言验证具体行为

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


class TestConnectionTracing(unittest.TestCase):
    """连接追踪测试"""
    
    def _make_adapter(self, source):
        """辅助: 创建 adapter"""
        comp = SVCompiler({'test.sv': source})
        root = comp.get_root()
        
