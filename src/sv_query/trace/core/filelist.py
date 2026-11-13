"""
filelist.py — filelist 的**唯一**解析实现 [iter_193]

背景: 过去有两套加载器, 相对路径规则不同 → 同一份 filelist 两侧结果不一致
(iter_190 记录 "tracer 侧按 filelist 目录 / CLI 侧按 base_dir", iter_192 只做到
"CLI 侧多候选解析" 让结果一致, 代码仍是两份)。

本模块把它变成**一次解析 + 结构化结果**:
    parse_filelist(path) -> FilelistSpec{files, include_dirs, defines, missing}

两个消费方 (都只剩薄封装):
  - `SVCompiler.add_filelist`  → 应用 include_dirs / 把 files 读入编译
  - `cli._common._read_filelist` → 把 files 读成 sources dict

支持的语法 (Verilator/Modelsim 风格, 与原实现一致):
  - 每行一个文件路径 (相对/绝对)
  - `+incdir+DIR`        include 搜索路径
  - `+define+VAR=VAL`    宏定义; **按出现顺序**影响后续行的 `${VAR}` 展开
  - `+libext+EXT`        库扩展名 (占位, 忽略)
  - `-f FILE` / `-F FILE` 嵌套 filelist (支持循环保护)
  - `${VAR}` / `$VAR`    环境变量展开; `~` 展开为主目录
  - 空行 / `//` / `#` 注释行

相对路径解析: 依次尝试
  ① filelist 所在目录 (tracer 侧原规则)
  ② base_dirs 里每个基准 (CLI 侧传 cwd/项目根)
都不中 → 记入 `missing` 并告警 (**不静默跳过**; AGENTS 纪律 2.5 的延伸)。
嵌套 `-f` 的相对路径同样走这套候选 (原 tracer 侧只按 cwd, CLI 侧只按 filelist 目录
—— 也是分歧点, 一并统一)。
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FilelistSpec:
    """一次 filelist 解析的结构化结果。"""

    files: list[str] = field(default_factory=list)         # 解析后的绝对路径 (按出现顺序)
    include_dirs: list[str] = field(default_factory=list)  # +incdir+ (绝对路径)
    defines: dict[str, str] = field(default_factory=dict)  # +define+
    missing: list[str] = field(default_factory=list)       # 缺失/不可解析条目 (原文, 供告警)
    filelists: list[str] = field(default_factory=list)     # 参与的 filelist (含嵌套, 供调试)

    def warn_missing(self, source: str) -> None:
        """缺失条目汇总告警 (两个消费方共用同一措辞)。"""
        if not self.missing:
            return
        head = ", ".join(self.missing[:5])
        more = f" (共 {len(self.missing)} 个)" if len(self.missing) > 5 else ""
        logger.warning("filelist %s 有 %d 个条目未加载: %s%s",
                       source, len(self.missing), head, more)


def _expand_env(text: str, env: dict[str, str]) -> str:
    """展开 ${VAR} 与 $VAR (与 SVCompiler._expand_env 行为一致)。"""
    import re

    def _braced(m: "re.Match[str]") -> str:
        return env.get(m.group(1), m.group(0))

    def _simple(m: "re.Match[str]") -> str:
        return env.get(m.group(1), m.group(0))

    text = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", _braced, text)
    return re.sub(r"\$([A-Za-z_][A-Za-z0-9_]*)", _simple, text)


def _resolve(raw: str, candidates: list[Path]) -> Path | None:
    """按候选基准解析路径, 返回第一个存在的文件 (否则 None)。"""
    p = Path(raw)
    if p.is_absolute():
        return p.resolve() if (p.exists() and p.is_file()) else None
    for base in candidates:
        cand = (base / raw).resolve()
        if cand.exists() and cand.is_file():
            return cand
    return None


def _strip_comment(line: str) -> str:
    """去掉行尾注释 (只在 `//` 前是空格时视为注释, 避免误切路径)。"""
    if "//" in line:
        idx = line.find("//")
        if idx > 0 and line[idx - 1] == " ":
            return line[:idx].strip()
    return line.strip()


def parse_filelist(
    filelist_path: str,
    *,
    base_dirs: list[Path] | None = None,
    env: dict[str, str] | None = None,
    already_loaded: set | None = None,
) -> FilelistSpec:
    """解析 filelist (含嵌套), 返回结构化结果。

    Args:
        filelist_path: .f / .fl / .filelist 路径
        base_dirs: 相对路径的额外候选基准 (按顺序; filelist 所在目录永远优先)
        env: 额外环境变量 (与 os.environ 合并; `+define+` 会按顺序覆盖它)
        already_loaded: 已加载 filelist 集合 (调用方可跨次复用做循环保护)

    Raises:
        FileNotFoundError: filelist 本身不存在 (调用方需要明确报错, 不是静默空结果)
    """
    spec = FilelistSpec()
    if base_dirs is None:
        base_dirs = []
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    seen = already_loaded if already_loaded is not None else set()
    _parse_one(Path(filelist_path), spec, list(base_dirs), full_env, seen)
    return spec


def _parse_one(
    filelist_path: Path,
    spec: FilelistSpec,
    base_dirs: list[Path],
    env: dict[str, str],
    seen: set,
) -> None:
    path = filelist_path.resolve()
    if str(path) in seen:
        return  # 防止循环引用
    seen.add(str(path))
    spec.filelists.append(str(path))

    if not path.is_file():
        raise FileNotFoundError(f"Filelist not found: {path}")

    candidates = [path.parent, *base_dirs]

    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = _strip_comment(raw)
            if not line or line.startswith("//") or line.startswith("#"):
                continue
            line = _expand_env(os.path.expanduser(line), env)

            # +incdir+DIR
            if line.startswith("+incdir+"):
                d = line[len("+incdir+"):].strip()
                resolved = _resolve_dir(d, candidates)
                if resolved is None:
                    logger.warning("filelist %s: +incdir+ 目录不存在, 跳过 %s", path, d)
                    spec.missing.append(f"+incdir+{d}")
                elif resolved not in spec.include_dirs:
                    spec.include_dirs.append(resolved)
                continue

            # +define+VAR=VAL (按顺序影响后续行的 ${VAR} 展开)
            if line.startswith("+define+"):
                d = line[len("+define+"):].strip()
                if "=" in d:
                    k, v = d.split("=", 1)
                    env[k.strip()] = v.strip()
                    spec.defines[k.strip()] = v.strip()
                else:
                    env[d] = "1"
                    spec.defines[d] = "1"
                continue

            # +libext+EXT 等占位: 跳过
            if line.startswith("+libext+"):
                continue

            # -f/-F FILELIST (嵌套)
            if line.startswith("-F") or line.startswith("-f"):
                parts = line.split(None, 1)
                if len(parts) < 2:
                    logger.warning("filelist %s: 无法解析嵌套引用行 %r", path, line)
                    spec.missing.append(line)
                    continue
                sub = _resolve(parts[1].strip(), candidates)
                if sub is None:
                    logger.warning("filelist %s: 嵌套 filelist 不存在, 跳过 %s", path, parts[1].strip())
                    spec.missing.append(f"-f {parts[1].strip()}")
                else:
                    # 嵌套沿用当前 env (父级 +define+ 对子级可见, 与原实现一致)
                    _parse_one(sub, spec, base_dirs, env, seen)
                continue

            # 其他 + / - 开头: 跳过
            if line.startswith("+") or line.startswith("-"):
                continue

            resolved = _resolve(line, candidates)
            if resolved is None:
                logger.warning("filelist %s: 文件不存在, 跳过 %s (候选基准: %s)",
                               path, line, ", ".join(str(c) for c in candidates))
                spec.missing.append(line)
                continue
            if str(resolved) not in spec.files:
                spec.files.append(str(resolved))


def _resolve_dir(raw: str, candidates: list[Path]) -> str | None:
    """解析目录 (用于 +incdir+): 支持逗号分隔的多目录。"""
    out: list[str] = []
    for one in raw.split(","):
        one = one.strip()
        if not one:
            continue
        p = Path(one)
        if p.is_absolute():
            if p.is_dir():
                out.append(str(p.resolve()))
            continue
        for base in candidates:
            cand = (base / one).resolve()
            if cand.is_dir():
                out.append(str(cand))
                break
    return ",".join(out) if out else None
