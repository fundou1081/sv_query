# test_no_data_models_legacy.py - 防止 legacy data_models.py 重新引入
#
# [V5 of docs/ARCHITECTURE_REVIEW_2026-07-15.md]
#
# src/trace/core/data_models.py (171 行, 13 classes) 自 2026-06-26 起完全未被 import.
# 所有需要的类 (SignalChain, ModuleConnections, StateTransition, ClockDomainResult) 已在
# graph/ 或 query/ subpackage 中重新定义. DriverCollector pattern 被 base.py 重写.

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))


class TestNoLegacyDataModels(unittest.TestCase):
    """[V5] data_models.py 必须不存在"""

    def test_legacy_data_models_file_does_not_exist(self):
        """src/trace/core/data_models.py 必须不存在"""
        path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', 'src', 'trace', 'core', 'data_models.py'
        )
        self.assertFalse(
            os.path.exists(path),
            f"[V5 violation] Legacy data_models.py reappeared at {path}. "
            f"All needed classes are in graph/ or query/ subpackage now."
        )

    def test_no_import_legacy_data_models(self):
        """任何生产代码或测试不应 import trace.core.data_models"""
        import subprocess
        result = subprocess.run(
            ['grep', '-rln',
             'trace\\.core\\.data_models\\|from trace.core.data_models '
             '|from .data_models\\|from \\.\\.data_models',
             'src/', 'tools/', 'sim/tests/cli/', 'sim/tests/regression/'],
            capture_output=True, text=True,
            cwd=os.path.join(os.path.dirname(__file__), '..', '..', '..'),
        )
        # Filter out __pycache__ and archive files
        violating = [
            line for line in result.stdout.split('\n')
            if line and '__pycache__' not in line and 'archive/' not in line
        ]
        self.assertEqual(
            violating, [],
            f"[V5 violation] Found references to deleted legacy data_models:\n"
            + '\n'.join(violating)
        )


if __name__ == '__main__':
    unittest.main()
