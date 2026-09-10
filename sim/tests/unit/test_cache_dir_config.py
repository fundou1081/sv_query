# test_cache_dir_config.py - 缓存目录可配置 + 不可写降级 (iter_172)
# 方豆: "缓存目录先更改, 更通用, 避免未来失败"
#
# 背景: 旧行为 = CACHE_DIR 硬编码 ~/.svq/cache + mkdir/写盘无保护 →
# 只读 HOME / 容器 / 沙箱 下 CLI 直接 exit 1 ("Operation not permitted"),
# 29 个 CLI/integration 测试假失败 (2026-09-08 实测)。
# 修复: ① 目录解析 显式 > SVQ_CACHE_DIR > XDG_CACHE_HOME/svq > ~/.svq/cache
#       ② 不可写 → 降级内存缓存 + warning (缓存是优化, 不致命)
import logging
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from trace.core.cache.ast_cache import (  # noqa: E402
    ENV_CACHE_DIR,
    ASTCache,
    resolve_cache_dir,
)


class TestCacheDirResolution(unittest.TestCase):
    """目录解析顺序: 显式 > SVQ_CACHE_DIR > XDG_CACHE_HOME > ~/.svq/cache"""

    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in (ENV_CACHE_DIR, "XDG_CACHE_HOME")}
        for k in (ENV_CACHE_DIR, "XDG_CACHE_HOME"):
            os.environ.pop(k, None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self._restore_env)

    def _restore_env(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_is_home_svq_cache(self):
        self.assertEqual(resolve_cache_dir(), Path.home() / ".svq" / "cache")

    def test_env_override(self):
        os.environ[ENV_CACHE_DIR] = self.tmp.name
        self.assertEqual(resolve_cache_dir(), Path(self.tmp.name))
        c = ASTCache()
        self.assertEqual(c.cache_dir, Path(self.tmp.name))
        self.assertTrue(c.enabled)

    def test_xdg_cache_home(self):
        os.environ["XDG_CACHE_HOME"] = self.tmp.name
        self.assertEqual(resolve_cache_dir(), Path(self.tmp.name) / "svq")

    def test_env_beats_xdg(self):
        os.environ["XDG_CACHE_HOME"] = self.tmp.name
        os.environ[ENV_CACHE_DIR] = str(Path(self.tmp.name) / "explicit")
        self.assertEqual(resolve_cache_dir(), Path(self.tmp.name) / "explicit")

    def test_explicit_arg_beats_env(self):
        os.environ[ENV_CACHE_DIR] = self.tmp.name
        explicit = Path(self.tmp.name) / "arg"
        self.assertEqual(resolve_cache_dir(str(explicit)), explicit)
        self.assertEqual(ASTCache(cache_dir=str(explicit)).cache_dir, explicit)


class TestCacheGracefulDegradation(unittest.TestCase):
    """不可写 → 降级内存缓存, 不抛异常 (旧行为 = exit 1)"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ro_parent = self.root / "readonly"
        self.ro_parent.mkdir()
        os.chmod(self.ro_parent, stat.S_IRUSR | stat.S_IXUSR)  # r-x: 不可建子目录
        self.unwritable = self.ro_parent / "cache"

        def _restore():
            # 先恢复权限再删 tmp (顺序不能反: 只读目录无法直接删除)
            try:
                os.chmod(self.ro_parent, stat.S_IRWXU)
            except FileNotFoundError:
                pass
            self.tmp.cleanup()

        self.addCleanup(_restore)

    def test_construction_does_not_raise_and_disables_disk(self):
        with self.assertLogs("trace.core.cache.ast_cache", level="WARNING") as cm:
            c = ASTCache(cache_dir=str(self.unwritable))
        self.assertFalse(c.enabled, "不可写目录 → 磁盘缓存应关闭")
        self.assertTrue(any(ENV_CACHE_DIR in m for m in cm.output),
                        "warning 应给出 SVQ_CACHE_DIR 修复提示")

    def test_put_get_degrade_to_memory(self):
        c = ASTCache(cache_dir=str(self.unwritable))
        # 写盘不可能, 但 put 不抛 + 内存可读回
        c.put_by_key("abc123", {"graph_data": {"nodes": 1}})
        self.assertFalse(c.enabled)
        data = c.get_by_key("abc123")
        self.assertIsNotNone(data, "内存缓存应命中")
        self.assertEqual(data["data"]["graph_data"]["nodes"], 1)

    def test_write_failure_warns_once_then_memory_only(self):
        """运行中变不可写 (目录被删/权限变更) → warning 一次, 不刷屏"""
        c = ASTCache(cache_dir=str(self.unwritable))
        self.assertFalse(c.enabled)  # 构造即降级
        with self.assertNoLogs("trace.core.cache.ast_cache", level="WARNING"):
            c.put_by_key("k1", {"x": 1})
            c.put_by_key("k2", {"x": 2})  # 降级后不重复 warning

    def test_reads_and_admin_ops_do_not_raise(self):
        c = ASTCache(cache_dir=str(self.unwritable))
        self.assertIsNone(c.get_by_key("nope"))
        self.assertEqual(c.list_cache(), [])
        c.invalidate()          # 全部清除
        c.invalidate("nope")    # 指定 key
        stats = c.cache_stats()
        self.assertFalse(stats["disk_cache_enabled"])
        self.assertEqual(stats["cache_dir"], str(self.unwritable))

    def test_writable_dir_still_roundtrips(self):
        """正常路径不回归: 可写目录写盘 + 新实例可读回"""
        c = ASTCache(cache_dir=str(self.root / "ok"))
        self.assertTrue(c.enabled)
        c.put_by_key("key1", {"v": 42})
        self.assertTrue((self.root / "ok" / "key1.json").exists())
        fresh = ASTCache(cache_dir=str(self.root / "ok"))
        self.assertEqual(fresh.get_by_key("key1")["data"]["v"], 42)


class TestCliUnwritableCacheStillSucceeds(unittest.TestCase):
    """端到端: 缓存目录不可写时 CLI 必须 rc=0 (旧行为 = exit 1)"""

    def test_trace_with_unwritable_cache_dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        ro = Path(tmp.name) / "ro"
        ro.mkdir()
        os.chmod(ro, stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(os.chmod, ro, stat.S_IRWXU)
        fixture = _REPO_ROOT / "sim" / "tests" / "regression" / "test_data_path.sv"
        env = dict(os.environ)
        env[ENV_CACHE_DIR] = str(ro / "cache")  # 不可创建
        r = subprocess.run(
            [sys.executable, str(_REPO_ROOT / "run_cli.py"),
             "trace", "fanin", "-f", str(fixture), "data_path.dout", "--human"],
            capture_output=True, text=True, env=env, timeout=180,
        )
        self.assertEqual(r.returncode, 0,
                         f"缓存不可写不应导致 CLI 失败; stderr={r.stderr[:400]}")
        self.assertIn("data_path.dout", r.stdout)


if __name__ == "__main__":
    unittest.main()
