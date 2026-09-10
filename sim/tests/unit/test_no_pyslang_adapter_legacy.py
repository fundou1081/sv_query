# test_no_pyslang_adapter_legacy.py - 防止 legacy adapter 层重新引入
#
# [V2 of architecture review 2026-07-15] 删除 src/trace/core/pyslang_adapter.py (158 行死代码)
# [iter_174 2026-09-08] 移出 src/trace/core/base.py (2,341 行 legacy 层:
#   ASTWalker + PyslangAdapter + 3 Collector) → legacy/base_pyslang_adapter.py
#   依据: 该层在 src/ **从未被实例化**, 运行时唯一 adapter = SemanticAdapter;
#   8 处类型注解已改指 SemanticAdapter, 相关测试已移植/退役。
#   方豆: "用移出代替删除, 这样可以恢复" (方案见 architecture/semantic_adapter_split_plan.md)。
# 本文件现守卫两件事: ① pyslang_adapter.py 不复活 ② core/base.py 不复活

import os
import subprocess
import sys
import unittest

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


class TestNoLegacyBaseLayer(unittest.TestCase):
    """[iter_174] core/base.py legacy 层不得回到 src/ (已移出 → legacy/)"""

    def test_core_base_moved_out(self):
        path = os.path.join(
            os.path.dirname(__file__), '..', '..', '..',
            'src', 'trace', 'core', 'base.py'
        )
        self.assertFalse(
            os.path.exists(path),
            f"[iter_174 violation] legacy adapter 层 base.py 重新出现在 {path}. "
            f"运行时唯一 adapter = SemanticAdapter; 历史实现见 legacy/base_pyslang_adapter.py"
        )

    def test_no_src_import_of_legacy_base(self):
        """src/ 不得 import trace.core.base (legacy 层)"""
        repo_root = os.path.join(os.path.dirname(__file__), '..', '..', '..')
        result = subprocess.run(
            ['grep', '-rln', 'from \.base import\|from trace\.core\.base import', 'src/'],
            capture_output=True, text=True, cwd=repo_root,
        )
        violating = [l for l in result.stdout.split('\n') if l and '__pycache__' not in l]
        self.assertEqual(violating, [],
                         "[iter_174 violation] src/ 仍在 import legacy base 层:\n" + '\n'.join(violating))


if __name__ == '__main__':
    unittest.main()
