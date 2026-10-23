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

    def compute_filelist_hash(self, filelist: str, include_dirs=()) -> str:
        """[iter_270] filelist 模式的内容 hash (filelist + 它引用的所有文件内容)。

        为什么不用 mtime: 判断"图是否还成立"必须看内容, mtime 在 checkout /
        复制 / touch 后会产生假失效或假命中。文件数通常几十~几百, 读取开销远小于
        一次图构建 (verilog-axi: 126 文件 ≈ 几十 ms vs 16~26s)。
        """
        fl = Path(filelist)
        if not fl.exists():
            raise FileNotFoundError(f"filelist 不存在: {filelist}")
        base = fl.parent
        hasher = hashlib.sha256()
        hasher.update(fl.name.encode())
        for raw in fl.read_text(errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith(("//", "#", "+incdir+", "+define+")):
                continue
            p = Path(line)
            p = p if p.is_absolute() else (base / p)
            if not p.is_file():
                continue
            hasher.update(str(p).encode())
            try:
                hasher.update(p.read_bytes())
            except OSError as e:
                logger.warning("缓存 key 计算跳过不可读文件 %s: %s", p, e)

        # [iter_270] 头文件也必须进 hash: `\`include` 的文件通常不在 filelist 里,
        # 只 hash filelist 会产生"改了头文件仍命中旧图"的静默错误。
        # 策略: 把 include 目录下所有 HDL 文件内容纳入 (目录通常几十~几百个文件,
        # 代价远小于一次图构建)。
        HDL_EXTS = {".sv", ".svh", ".v", ".vh", ".inc"}
        for inc in include_dirs or ():
            inc_dir = Path(inc)
            if not inc_dir.is_absolute():
                inc_dir = base / inc_dir
            if not inc_dir.is_dir():
                continue
            for hf in sorted(inc_dir.rglob("*")):
                if hf.suffix not in HDL_EXTS or not hf.is_file():
                    continue
                hasher.update(str(hf).encode())
                try:
                    hasher.update(hf.read_bytes())
                except OSError as e:
                    logger.warning("缓存 key 计算跳过不可读头文件 %s: %s", hf, e)
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
