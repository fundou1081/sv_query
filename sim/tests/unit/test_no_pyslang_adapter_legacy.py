# test_no_pyslang_adapter_legacy.py - 防止 legacy pyslang_adapter.py 重新引入
#
# [V2 of architecture review 2026-07-15] 158 lines of dead code:
# - src/trace/core/pyslang_adapter.py 自 2026-06-02 起就完全未被 import
# - 实际使用的是 src/trace/core/base.py:79 PyslangAdapter (primary)
# - 任何文件都不应 import trace.core.pyslang_adapter (如果需要, 改用 trace.core.base.PyslangAdapter)

import os
import sys
import unittest
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))


class TestNoLegacyPyslangAdapter(unittest.TestCase):
    """防止 re-introduction"""

    def test_legacy_pyslang_adapter_file_does_not_exist(self):
        """src/trace/core/pyslang_adapter.py 必须不存在"""
        path = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', 'src', 'trace', 'core', 'pyslang_adapter.py'
        )
        self.assertFalse(
            os.path.exists(path),
            f"[V2 violation] Legacy pyslang_adapter.py reappeared at {path}. "
            f"Use trace.core.base.PyslangAdapter instead."
        )

    def test_no_import_legacy_pyslang_adapter(self):
        """生产代码 (src/) 不应 import trace.core.pyslang_adapter

        注: 这个测试本文件 self-test 是 OK 的, 因为它必须 reference 这个名字才能检查.
        但我们排除 (1) 自己, (2) __pycache__/ 字节码缓存, (3) docs/archive/.
        """
        repo_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
        # 只检查 src/ + tools/ + sim/tests/cli + sim/tests/regression
        # (sim/tests/unit/test_no_pyslang_adapter_legacy.py 是本测试, 排除)
        dirs = ['src/', 'tools/', 'sim/tests/cli/', 'sim/tests/regression/']
        for d in dirs:
            full_d = os.path.join(repo_root, d)
            if not os.path.isdir(full_d):
                continue
            result = subprocess.run(
                ['grep', '-rln',
                 'from \\.pyslang_adapter\\|from trace.core.pyslang_adapter '
                 '|trace\\.core\\.pyslang_adapter',
                 d],
                capture_output=True, text=True, cwd=repo_root,
            )
            violating = [
                line for line in result.stdout.split('\n')
                if line and '__pycache__' not in line
            ]
            self.assertEqual(
                violating, [],
                f"[V2 violation] Found references to deleted legacy pyslang_adapter "
                f"in {d}:\n" + '\n'.join(violating)
            )


if __name__ == '__main__':
    unittest.main()
