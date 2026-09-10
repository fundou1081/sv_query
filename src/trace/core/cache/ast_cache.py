# ==============================================================================
# ast_cache.py - AST 解析缓存
# ==============================================================================
"""
基于内容 hash 的 AST 解析缓存，避免重复解析未变化的源文件。

缓存机制：
1. 计算源文件内容的 SHA256 hash
2. 缓存文件：<cache_dir>/<hash>.json
3. 包含：图数据、SVA/Coverage 提取结果
4. 失效条件：源文件内容变化

缓存目录解析顺序 (iter_172 — 方豆 "缓存目录先更改, 更通用, 避免未来失败"):
1. 显式参数 `ASTCache(cache_dir=...)`
2. 环境变量 `SVQ_CACHE_DIR`
3. `$XDG_CACHE_HOME/svq` (Linux/CI 惯例)
4. `~/.svq/cache` (历史默认, 向后兼容)

**失败降级 (关键)**: 缓存只是**优化**, 任何不可写/不可读都不得让分析失败 —
目录创建或写入失败时本进程降级为**内存缓存**并打 warning (含修复提示),
**不抛异常、不影响 CLI 退出码**。旧行为 (写失败 → exit 1) 在只读 HOME /
容器 / 沙箱 (如 `~` 不可写) 下会让全部 CLI 命令假失败。

支持：
- 单文件缓存
- 多文件缓存（通过合并 hash）
- 内存缓存（进程内）
- 磁盘缓存（持久化）
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 环境变量名 (覆盖缓存目录)
ENV_CACHE_DIR = "SVQ_CACHE_DIR"


def resolve_cache_dir(explicit: str | os.PathLike | None = None) -> Path:
    """缓存目录解析 (顺序: 显式 > SVQ_CACHE_DIR > XDG_CACHE_HOME/svq > ~/.svq/cache)."""
    if explicit:
        return Path(explicit).expanduser()
    env_dir = os.environ.get(ENV_CACHE_DIR)
    if env_dir:
        return Path(env_dir).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "svq"
    return Path.home() / ".svq" / "cache"


# 历史常量 (向后兼容外部 import; 实际使用 resolve_cache_dir)
CACHE_DIR = resolve_cache_dir()

# 缓存版本
CACHE_VERSION = "1.0"


class ASTCache:
    """AST 解析缓存管理器

    不可写时自动降级为内存缓存 (见模块 docstring "失败降级")。
    """

    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else resolve_cache_dir()
        self.enabled = True  # 磁盘缓存可用性 (False = 仅内存)
        self._memory_cache: dict[str, Any] = {}  # 进程内缓存
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.enabled = False
            logger.warning(
                "缓存目录不可用 (%s: %s) — 本次运行降级为内存缓存 (不影响分析结果); "
                "可用环境变量 %s 指定可写目录",
                self.cache_dir, e, ENV_CACHE_DIR,
            )

    def compute_sources_hash(self, sources: dict[str, str]) -> str:
        """计算 sources 内容的一致性 hash（用于缓存 key）"""
        hasher = hashlib.sha256()
        for fname in sorted(sources.keys()):
            hasher.update(fname.encode())
            hasher.update(sources[fname].encode())
        return hasher.hexdigest()[:16]

    def _cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.json"

    def get_by_key(self, cache_key: str, force: bool = False) -> dict | None:
        """[Golden] 通过 cache_key 获取缓存数据

        Args:
            cache_key: 缓存 key（由 compute_sources_hash 生成）
            force: True=跳过缓存，False=尝试从缓存加载

        Returns:
            缓存的数据字典，或 None（无缓存或失效）
        """
        if force:
            return None

        # 检查内存缓存
        if cache_key in self._memory_cache:
            logger.info(f"Memory cache hit: {cache_key[:8]}...")
            return self._memory_cache[cache_key]

        if not self.enabled:
            return None  # 磁盘缓存不可用 → 仅内存 (已 warning, 不再刷屏)

        # 检查磁盘缓存
        cache_path = self._cache_path(cache_key)
        if not cache_path.exists():
            logger.debug(f"Cache miss: {cache_key[:8]}...")
            return None

        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)

            # 验证缓存版本
            if data.get("version") != CACHE_VERSION:
                logger.debug("Cache version mismatch, rebuilding...")
                return None

            # 验证 sources hash
            if data.get("sources_hash") != cache_key:
                logger.debug("Cache hash mismatch, rebuilding...")
                return None

            logger.info(f"Cache hit: {cache_key[:8]}... ({cache_path.stat().st_size} bytes)")

            # 加载到内存缓存
            self._memory_cache[cache_key] = data
            return data

        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    def put_by_key(self, cache_key: str, data: dict) -> None:
        """[Golden] 通过 cache_key 保存缓存

        写盘失败不致命 (iter_172): 降级为内存缓存 + warning, 磁盘缓存关闭
        (避免每条都刷屏), 分析结果不受影响。
        """
        # 构建缓存数据
        cache_data = {
            "version": CACHE_VERSION,
            "sources_hash": cache_key,
            "cached_at": datetime.now().isoformat(),
            "data": data,
        }

        # 保存到内存缓存 (始终)
        self._memory_cache[cache_key] = cache_data

        if not self.enabled:
            return

        # 保存到磁盘 (失败 → 降级)
        cache_path = self._cache_path(cache_key)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            self.enabled = False
            logger.warning(
                "缓存写入失败 (%s: %s) — 本次运行降级为内存缓存 (分析结果不受影响); "
                "可用环境变量 %s 指定可写目录",
                cache_path, e, ENV_CACHE_DIR,
            )
            return

        logger.info(f"Cache saved: {cache_key[:8]}... -> {cache_path}")

    def get(self, source_file: str, force: bool = False) -> dict | None:
        """[Legacy] 通过文件路径获取缓存（已废弃，仅保留兼容）"""
        # 这个方法不再使用，仅保留兼容
        return None

    def put(self, source_file: str, data: dict) -> str:
        """[Legacy] 通过文件路径保存缓存（已废弃，仅保留兼容）"""
        return ""

    def invalidate(self, cache_key: str | None = None) -> None:
        """[Golden] 清除缓存

        Args:
            cache_key: 指定 key 或 None（全部）
        """
        if cache_key:
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
            if not self.enabled:
                return
            cache_path = self._cache_path(cache_key)
            try:
                if cache_path.exists():
                    cache_path.unlink()
                    logger.info(f"Cache invalidated: {cache_key[:8]}...")
            except OSError as e:
                logger.warning("缓存清除失败 (%s): %s", cache_path, e)
        else:
            # 清除所有
            self._memory_cache.clear()
            if not self.enabled:
                return
            for p in self.cache_dir.glob("*.json"):
                try:
                    p.unlink()
                except OSError as e:
                    logger.warning("缓存清除失败 (%s): %s", p, e)
            logger.info("All cache cleared")

    def list_cache(self) -> list[dict]:
        """[Golden] 列出所有缓存条目 (不可读/损坏条目 → warning 并跳过)"""
        result = []
        if not self.enabled:
            return result
        for p in sorted(self.cache_dir.glob("*.json")):
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                result.append(
                    {
                        "key": p.stem,
                        "sources_hash": data.get("sources_hash", "")[:8],
                        "cached_at": data.get("cached_at", ""),
                        "size_bytes": p.stat().st_size,
                    }
                )
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("缓存条目不可读 (%s): %s", p, e)
                continue
        return result

    def cache_stats(self) -> dict[str, Any]:
        """获取缓存统计信息"""
        entries = self.list_cache()
        total_size = sum(e["size_bytes"] for e in entries)
        return {
            "total_entries": len(entries),
            "total_size_bytes": total_size,
            "cache_dir": str(self.cache_dir),
            "disk_cache_enabled": self.enabled,
            "memory_cache_entries": len(self._memory_cache),
        }


# 全局缓存实例
_global_cache: ASTCache | None = None


def get_cache() -> ASTCache:
    """获取全局缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = ASTCache()
    return _global_cache
