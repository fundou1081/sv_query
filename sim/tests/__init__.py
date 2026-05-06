#==============================================================================
# sv_query 测试框架
# 统一测试入口 + 测试计划管理
#==============================================================================
# [铁律7] 金标准测试
# [铁律8] 文档与代码同步
#==============================================================================

import sys
import os

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

__all__ = ['run_tests', 'run_unit_tests', 'run_integration_tests', 'run_regression_tests']

def run_tests(filter_pattern=None, verbose=True):
    """统一测试runner"""
    import unittest
    
    loader = unittest.TestLoader()
    loader.pattern = filter_pattern or 'test_*.py'
    
    # 加载所有测试
    suite = unittest.TestSuite()
    
    # 单元测试
    unit_suite = loader.discover('tests/unit', pattern='test_*.py')
    suite.addTests(unit_suite)
    
    # 集成测试
    int_suite = loader.discover('tests/integration', pattern='test_*.py')
    suite.addTests(int_suite)
    
    # 回归测试
    reg_suite = loader.discover('tests/regression', pattern='test_*.py')
    suite.addTests(reg_suite)
    
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)
    
    return result

def run_unit_tests(pattern=None):
    """单元测试: 每个工具独立测试"""
    import unittest
    
    loader = unittest.TestLoader()
    loader.pattern = pattern or 'test_*.py'
    
    suite = loader.discover('tests/unit')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result

def run_integration_tests(pattern=None):
    """集成测试: 多模块交互"""
    import unittest
    
    loader = unittest.TestLoader()
    suite = loader.discover('tests/integration')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result

def run_regression_tests(pattern=None):
    """回归测试: 已知问题验证"""
    import unittest
    
    loader = unittest.TestLoader()
    suite = loader.discover('tests/regression')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result

if __name__ == '__main__':
    run_tests()
