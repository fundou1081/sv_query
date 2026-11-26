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

import gzip
import hashlib
import json
import logging
import os
import tempfile
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
CACHE_VERSION = "3.4"  # [P197.17] arithmetic shift IR ops

# [iter_271] 缓存文件: gzip 压缩 + 总量上限 (LRU 淘汰)
# 单工程图 JSON 可达 20MB, 压缩后通常 3~5MB。上限默认 1GB, 可用 SVQ_CACHE_MAX_MB 覆盖。
CACHE_SUFFIX = ".json.gz"
LEGACY_SUFFIX = ".json"
DEFAULT_MAX_CACHE_MB = 1024
ENV_CACHE_MAX_MB = "SVQ_CACHE_MAX_MB"

# [iter_287 / PLAN P3.2] 按工程过期: 单个工程最多保留 N 个版本 + 条目最长存活天数。
# 文件命名: <content_key>.p<project_key><CACHE_SUFFIX>, 无工程段 = 旧格式(仅参与全局 LRU)。
DEFAULT_MAX_ENTRIES_PER_PROJECT = 8
ENV_CACHE_MAX_ENTRIES_PER_PROJECT = "SVQ_CACHE_MAX_ENTRIES_PER_PROJECT"
DEFAULT_MAX_AGE_DAYS = 30
ENV_CACHE_MAX_AGE_DAYS = "SVQ_CACHE_MAX_AGE_DAYS"
PROJECT_INFIX = ".p"


class CacheKeyError(ValueError):
    """The cache key cannot be computed safely (explicit miss, never a skip)."""


_HDL_EXTS = {".sv", ".svh", ".v", ".vh", ".inc"}


def _read_for_key(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CacheKeyError(f"cache key input unreadable: {path}: {exc}") from exc


def _hash_file(hasher, path: Path) -> None:
    hasher.update(str(path.resolve()).encode())
    hasher.update(_read_for_key(path))


def _hash_header_dirs(hasher, dirs, base: Path) -> None:
    for raw in dirs:
        for one in str(raw).split(","):
            one = one.strip()
            if not one:
                continue
            inc = Path(one)
            if not inc.is_absolute():
                inc = base / inc
            if not inc.is_dir():
                raise CacheKeyError(f"cache key include dir missing: {inc}")
            for hf in sorted(inc.rglob("*")):
                if hf.suffix in _HDL_EXTS and hf.is_file():
                    _hash_file(hasher, hf)


class ASTCache:

    """AST 解析缓存管理器

    不可写时自动降级为内存缓存 (见模块 docstring "失败降级")。
    """

    def __init__(self, cache_dir: str = None):
        self.cache_dir = Path(cache_dir) if cache_dir else resolve_cache_dir()
        self._managed = False
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

    def compute_sources_hash(self, sources: dict[str, str], include_dirs=()) -> str:
        """Hash source text plus all HDL headers under explicit include dirs."""
        hasher = hashlib.sha256()
        for fname in sorted(sources.keys()):
            hasher.update(str(Path(fname).resolve()).encode())
            hasher.update(sources[fname].encode())
        _hash_header_dirs(hasher, include_dirs, Path.cwd())
        return hasher.hexdigest()[:16]

    def compute_filelist_hash(self, filelist: str, include_dirs=()) -> str:
        """Hash the resolved build closure: filelists, sources, defines, headers.

        This deliberately reuses the production filelist parser instead of a
        second ad-hoc reader. Missing/unreadable closure members raise
        CacheKeyError; a cache key must never be computed from a partial closure.
        """
        from ..filelist import parse_filelist

        fl = Path(filelist)
        if not fl.exists():
            raise FileNotFoundError(f"filelist 不存在: {filelist}")
        spec = parse_filelist(str(fl), base_dirs=[Path.cwd()])
        if spec.missing:
            raise CacheKeyError(
                "cache key filelist closure incomplete: " + ", ".join(spec.missing[:5]))

        hasher = hashlib.sha256()
        for fl_path in spec.filelists:
            _hash_file(hasher, Path(fl_path))
        for source in sorted(spec.files):
            _hash_file(hasher, Path(source))
        for key, value in sorted(spec.defines.items()):
            hasher.update(f"define:{key}={value}".encode())
        includes = list(spec.include_dirs)
        includes.extend(str(d) for d in include_dirs or ())
        _hash_header_dirs(hasher, includes, fl.parent)
        return hasher.hexdigest()[:16]

    def compute_project_key(
        self,
        sources: dict[str, str] | None = None,
        filelist: str | None = None,
        include_dirs=(),
    ) -> str | None:
        """[iter_287] **工程身份** hash：只看路径（不看内容）。

        用途: 缓存按工程分组淘汰（单工程最多保留 N 个版本 / 超龄过期），
        避免一个改得很勤的大工程把其它工程的缓存挤出总量 LRU。
        """
        hasher = hashlib.sha256()
        try:
            if sources:
                for fname in sorted(sources):
                    hasher.update(str(Path(fname).resolve()).encode())
            elif filelist:
                fl = Path(filelist)
                if not fl.exists():
                    return None
                hasher.update(str(fl.resolve()).encode())
                base = fl.parent
                for raw in fl.read_text(errors="replace").splitlines():
                    line = raw.strip()
                    if not line or line.startswith(("//", "#", "+incdir+", "+define+")):
                        continue
                    p = Path(line)
                    p = p if p.is_absolute() else (base / p)
                    hasher.update(str(p.resolve()).encode())
                for inc in include_dirs or ():
                    inc_dir = Path(inc)
                    if not inc_dir.is_absolute():
                        inc_dir = base / inc_dir
                    hasher.update(str(inc_dir.resolve()).encode())
            else:
                return None
        except OSError as e:
            logger.debug("工程 key 计算失败: %s", e)
            return None
        return hasher.hexdigest()[:8]

    def _cache_path(self, cache_key: str, project_key: str | None = None) -> Path:
        """缓存文件路径；带工程段时 `<content>.p<project>.json.gz`（iter_287）。"""
        if project_key:
            return self.cache_dir / f"{cache_key}{PROJECT_INFIX}{project_key}{CACHE_SUFFIX}"
        return self.cache_dir / f"{cache_key}{CACHE_SUFFIX}"

    @staticmethod
    def _split_cache_name(path: Path) -> tuple[str, str | None]:
        """文件名 → (content_key, project_key|None)。旧格式无工程段。"""
        name = path.name
        for suffix in (CACHE_SUFFIX, LEGACY_SUFFIX):
            if name.endswith(suffix):
                stem = name[: -len(suffix)]
                break
        else:
            return name, None
        if PROJECT_INFIX in stem:
            content, _sep, project = stem.rpartition(PROJECT_INFIX)
            return content, project or None
        return stem, None

    def _legacy_cache_path(self, cache_key: str) -> Path:
        """旧格式 (未压缩) 路径 — 仅用于向后兼容读取与清理。"""
        return self.cache_dir / f"{cache_key}{LEGACY_SUFFIX}"

    def _max_cache_bytes(self) -> int:
        """缓存总量上限 (字节)。SVQ_CACHE_MAX_MB 可覆盖; 0/负数 = 不限制。"""
        raw = os.environ.get(ENV_CACHE_MAX_MB)
        if raw is None or not str(raw).strip():
            mb = DEFAULT_MAX_CACHE_MB
        else:
            try:
                mb = int(str(raw).strip())
            except ValueError:
                logger.warning("SVQ_CACHE_MAX_MB 不是整数 (%r), 用默认 %d", raw, DEFAULT_MAX_CACHE_MB)
                mb = DEFAULT_MAX_CACHE_MB
        return max(0, mb) * 1024 * 1024

    def _max_entries_per_project(self) -> int:
        """单工程保留版本数上限；0 = 不限制。"""
        raw = os.environ.get(ENV_CACHE_MAX_ENTRIES_PER_PROJECT)
        if raw is None or not str(raw).strip():
            return DEFAULT_MAX_ENTRIES_PER_PROJECT
        try:
            return max(0, int(str(raw).strip()))
        except ValueError:
            logger.warning("SVQ_CACHE_MAX_ENTRIES_PER_PROJECT 不是整数 (%r), 用默认 %d",
                           raw, DEFAULT_MAX_ENTRIES_PER_PROJECT)
            return DEFAULT_MAX_ENTRIES_PER_PROJECT

    def _max_age_seconds(self) -> int:
        """条目最长存活时间；0 = 不限制。"""
        raw = os.environ.get(ENV_CACHE_MAX_AGE_DAYS)
        if raw is None or not str(raw).strip():
            days = DEFAULT_MAX_AGE_DAYS
        else:
            try:
                days = max(0, int(str(raw).strip()))
            except ValueError:
                logger.warning("SVQ_CACHE_MAX_AGE_DAYS 不是整数 (%r), 用默认 %d",
                               raw, DEFAULT_MAX_AGE_DAYS)
                days = DEFAULT_MAX_AGE_DAYS
        return days * 86400

    def _cache_entries(self) -> list[dict]:
        """扫描缓存目录，返回 [{path, mtime, size, content, project}]（跳过不可读）。"""
        import time as _time

        now = _time.time()
        entries = []
        for p in list(self.cache_dir.glob(f"*{CACHE_SUFFIX}")) + \
                 list(self.cache_dir.glob(f"*{LEGACY_SUFFIX}")):
            try:
                st = p.stat()
            except OSError:
                continue
            content, project = self._split_cache_name(p)
            entries.append({
                "path": p, "mtime": st.st_mtime, "size": st.st_size,
                "age": now - st.st_mtime, "content": content, "project": project,
            })
        return entries

    def _remove(self, entry: dict) -> bool:
        try:
            entry["path"].unlink()
            return True
        except OSError as e:
            logger.warning("缓存淘汰失败 (%s): %s", entry["path"], e)
            return False

    def _enforce_size_limit(self) -> None:
        """[iter_287] 三级淘汰：① 单工程条目数 ② 条目年龄 ③ 全局总量 LRU。"""
        entries = self._cache_entries()
        removed = 0

        # ① 单工程最多 N 个版本（保留最新 N 个；旧格式无工程段不参与）
        per_project = self._max_entries_per_project()
        if per_project > 0:
            groups: dict[str, list[dict]] = {}
            for e in entries:
                if e["project"]:
                    groups.setdefault(e["project"], []).append(e)
            for project, items in groups.items():
                if len(items) <= per_project:
                    continue
                items.sort(key=lambda x: x["mtime"], reverse=True)
                for e in items[per_project:]:
                    if self._remove(e):
                        entries.remove(e)
                        removed += 1
                logger.info("工程 %s 版本超限，已淘汰 %d 个旧版本",
                            project, max(0, len(items) - per_project))

        # ② 年龄过期（所有条目，含旧格式）
        max_age = self._max_age_seconds()
        if max_age > 0:
            for e in list(entries):
                if e["age"] > max_age:
                    if self._remove(e):
                        entries.remove(e)
                        removed += 1

        # ③ 全局总量上限（mtime LRU）
        limit = self._max_cache_bytes()
        if limit > 0:
            total = sum(e["size"] for e in entries)
            if total > limit:
                for e in sorted(entries, key=lambda x: x["mtime"]):
                    if total <= limit:
                        break
                    if self._remove(e):
                        total -= e["size"]
                        removed += 1

        if removed:
            logger.info("缓存淘汰完成: 删除 %d 个条目", removed)

    def get_by_key(self, cache_key: str, force: bool = False,
                   project_key: str | None = None) -> dict | None:
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

        # 检查磁盘缓存 (优先带工程段的新格式, 再旧格式)
        candidates = []
        if project_key:
            candidates.append(self._cache_path(cache_key, project_key))
        candidates.append(self._cache_path(cache_key))
        candidates.append(self._legacy_cache_path(cache_key))
        cache_path = next((p for p in candidates if p.exists()), None)
        if cache_path is None:
            logger.debug(f"Cache miss: {cache_key[:8]}...")
            return None

        try:
            if cache_path.suffix == ".gz":
                with gzip.open(cache_path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
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

        except (OSError, json.JSONDecodeError, EOFError, UnicodeDecodeError) as e:
            logger.warning(f"Failed to load cache: {e}")
            return None

    def put_by_key(self, cache_key: str, data: dict, project_key: str | None = None) -> None:
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
        cache_path = self._cache_path(cache_key, project_key)
        tmp_path: str | None = None
        try:
            # Atomic write: a crash/concurrent writer must never leave a
            # half-written gzip at the final path.
            fd, tmp_path = tempfile.mkstemp(
                dir=str(cache_path.parent), prefix=f".{cache_path.name}.", suffix=".tmp")
            os.close(fd)
            with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False)
            os.replace(tmp_path, cache_path)
            tmp_path = None
        except OSError as e:
            if tmp_path:
                try:
                    Path(tmp_path).unlink()
                except OSError as cleanup_err:
                    logger.debug("cache temp cleanup failed: %s", cleanup_err)
            self.enabled = False
            logger.warning(
                "缓存写入失败 (%s: %s) — 本次运行降级为内存缓存 (分析结果不受影响); "
                "可用环境变量 %s 指定可写目录",
                cache_path, e, ENV_CACHE_DIR,
            )
            return
        except BaseException:
            if tmp_path:
                try:
                    Path(tmp_path).unlink()
                except OSError as cleanup_err:
                    logger.debug("cache temp cleanup failed: %s", cleanup_err)
            raise

        logger.info(f"Cache saved: {cache_key[:8]}... -> {cache_path}")
        # [iter_271] 写盘后检查总量上限, 按 mtime LRU 淘汰旧条目
        self._enforce_size_limit()

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
            paths = {self._cache_path(cache_key), self._legacy_cache_path(cache_key)}
            paths.update(self.cache_dir.glob(f"{cache_key}{PROJECT_INFIX}*{CACHE_SUFFIX}"))
            for cache_path in sorted(paths):
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
            for p in list(self.cache_dir.glob(f"*{CACHE_SUFFIX}")) + list(self.cache_dir.glob(f"*{LEGACY_SUFFIX}")):
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
        candidates = sorted(self.cache_dir.glob(f"*{CACHE_SUFFIX}")) + \
                     sorted(self.cache_dir.glob(f"*{LEGACY_SUFFIX}"))
        for p in candidates:
            try:
                if p.suffix == ".gz":
                    with gzip.open(p, "rt", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    with open(p, encoding="utf-8") as f:
                        data = json.load(f)
                result.append(
                    {
                        "key": p.name.replace(CACHE_SUFFIX, "").replace(LEGACY_SUFFIX, ""),
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


_global_cache_env: str | None = None


def get_cache() -> ASTCache:
    """获取全局缓存实例；cache-dir 环境变化会重建实例。"""
    global _global_cache, _global_cache_env
    env = os.environ.get(ENV_CACHE_DIR, "")
    if _global_cache is None or (
            getattr(_global_cache, "_managed", False) and _global_cache_env != env):
        _global_cache = ASTCache()
        _global_cache._managed = True
        _global_cache_env = env
    return _global_cache
