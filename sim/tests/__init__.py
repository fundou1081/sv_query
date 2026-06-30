#==============================================================================
# sv_query 测试框架 v2.0
# 统一测试入口 + 测试计划管理
#==============================================================================

import sys
import os
import unittest

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

__all__ = [
    'run_tests',
    'run_unit_tests',
    'run_integration_tests',
    'run_regression_tests',
    'get_test_summary',
]

def run_tests(filter_pattern=None, verbose=True):
    """统一测试 runner"""
    loader = unittest.TestLoader()
    loader.pattern = filter_pattern or 'test_*.py'

    suite = unittest.TestSuite()
    for test_dir in ['tests/unit', 'tests/integration', 'tests/regression']:
        full_path = os.path.join(os.path.dirname(__file__), test_dir.replace('/', os.sep))
        if os.path.exists(full_path):
            s = loader.discover(full_path)
            suite.addTests(s)

    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)

    return result

def run_unit_tests():
    """单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(os.path.dirname(__file__), 'tests/unit'))
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

def run_integration_tests():
    """集成测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(os.path.dirname(__file__), 'tests/integration'))
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

def run_regression_tests():
    """回归测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(os.path.dirname(__file__), 'tests/regression'))
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

def get_test_summary():
    """获取测试摘要"""
    import glob

    base = os.path.dirname(__file__)
    summary = {'unit': 0, 'integration': 0, 'regression': 0}

    for test_type in ['unit', 'integration', 'regression']:
        path = os.path.join(base, test_type, 'test_*.py')
        files = glob.glob(path)
        summary[test_type] = len(files)

    return summary

if __name__ == '__main__':
    run_tests()
