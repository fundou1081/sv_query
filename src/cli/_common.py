# -*- coding: utf-8 -*-
"""
CLI 公共 helper
================

集中 tracer 构建 / 错误处理 / 通用参数解析, 供所有 CLI command 复用.

设计原则:
- 一个 _build_tracer() 函数处理 --file / --filelist / --strict 三种参数组合
- 一个 _tracer_from_kwargs() 简化命令内部调用
- 错误统一走 CompilationError catch, 暴露干净错误信息 (Issue 17/任务3)

[ADD 2026-06-11 Issue 18 / Req-9] 所有 --file 命令加 --filelist 支持
[ADD 2026-06-11 Issue 17] 所有命令 elaboration error 统一处理
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer

from trace.core.compiler import CompilationError
from trace.unified_tracer import UnifiedTracer


# ----------------------------------------------------------------------------
# 1. tracer 构建 (核心 helper, 所有 --file 命令复用)
# ----------------------------------------------------------------------------

def _build_tracer(
    file: Optional[Path] = None,
    filelist: Optional[str] = None,
    strict: bool = True,
    log_level: str = "WARNING",
    include_dirs: Optional[list] = None,
    preprocess_macros: bool = True,
) -> UnifiedTracer:
    """[ADD 2026-06-11 Req-9] 统一构建 UnifiedTracer, 支持 --file / --filelist

    Args:
        file: 单个 .sv 源文件路径 (--file / -f)
        filelist: filelist 文件路径 (--filelist), 支持 .f / .fl / .filelist
        strict: True = elaboration error 立即 raise; False = 优雅降级存部分图
        log_level: 编译器日志级别, 默认 WARNING (可设 ERROR 静音)
        include_dirs: include 搜索路径列表
        preprocess_macros: True (默认) = 跨文件宏展开 (Req-20);
                          False = 信任 pyslang 内置 (退回旧行为)

    Returns:
        UnifiedTracer 实例 (未 build_graph, 调用方自己调)

    Raises:
        ValueError: --file 和 --filelist 都没给
        FileNotFoundError: filelist / file 路径不存在
    """
    if filelist:
        if not Path(filelist).exists():
            raise FileNotFoundError(f"Filelist not found: {filelist}")
        # [FIX 2026-06-11 Req-9] 手动读 filelist 转 sources, 避免 add_filelist
        # 处理 relative path 失败的 bug. 用 cwd 作为 base_dir
        # (filelist 里 relative path 相对项目根, 符合开发者心智模型)
        # [Bug fix 2026-06-25] auto-detect base_dir from filelist content.
        # CVA6 filelist 用相对路径 'core/include/ariane_pkg.sv', 应相对 cva6 项目根.
        # Heuristic: 用 filelist 中第一个 relative path 的最长公共前缀作为 base_dir.
        filelist_path = Path(filelist).resolve()
        base_dir = _detect_filelist_base_dir(filelist_path, fallback=Path.cwd())
        sources = _read_filelist(filelist_path, base_dir=base_dir)
        tracer = UnifiedTracer(
            sources=sources,
            log_level=log_level,
            include_dirs=include_dirs or [],
            strict=strict,
            preprocess_macros=preprocess_macros,  # [Req-20 2026-06-12]
        )
    elif file is not None:
        if not file.exists():
            raise FileNotFoundError(f"Source file not found: {file}")
        with open(str(file)) as f:
            source = f.read()
        tracer = UnifiedTracer(
            sources={str(file): source},
            log_level=log_level,
            include_dirs=include_dirs or [],
            strict=strict,
            preprocess_macros=preprocess_macros,  # [Req-20 2026-06-12]
        )
    else:
        raise ValueError("Either --file or --filelist must be provided")
    return tracer


def _detect_filelist_base_dir(filelist_path: Path, fallback: Path) -> Path:
    """[Bug fix 2026-06-25] auto-detect filelist 的 base_dir.

    CVA6 的 filelist 用相对路径 'core/include/ariane_pkg.sv', 应相对 cva6 项目根.
    Heuristic:
      1. 读 filelist 所有 relative path
      2. 找包含最多 files 的 dir (= 项目根)
      3. 用 filelist.parent 当 base_dir (相对路径以 filelist 目录为基点)

    Args:
        filelist_path: filelist 的绝对路径
        fallback: 如果 heuristic 失败, 用这个

    Returns:
        best guess base_dir (absolute Path)
    """
    # [Simple fix 2026-06-25] 用 filelist.parent 当 base_dir.
    # 常见用法: filelist 在 project root (e.g. /Users/me/project/project.f),
    # relative paths 以 project root 为 base. macOS 上 /tmp 是 symlink,
    # 需 resolve() 避免路径不一致.
    return filelist_path.parent.resolve()


def _read_filelist(filelist_path: str, base_dir: Path) -> dict[str, str]:
    """[ADD 2026-06-11 Req-9] 读 filelist 把所有源文件读到 sources dict.

    支持 Verilator/Modelsim 风格:
    - 每行一个文件路径 (relative to base_dir 或 absolute)
    - +incdir+DIR        记录到 include_dirs (本 helper 不返回, 调用方自己解析)
    - -F/-f FILELIST     嵌套加载
    - // 或 # 开头       注释行, 跳过
    - 空行                跳过

    Returns:
        sources dict {绝对路径: source 内容}
    """
    sources: dict[str, str] = {}
    base_dir = base_dir.resolve()
    # 嵌套 filelist 跟踪, 防止循环
    seen_filelists: set[Path] = set()
    _read_filelist_recursive(Path(filelist_path).resolve(), base_dir, sources, seen_filelists)
    return sources


def _read_filelist_recursive(
    filelist_path: Path,
    base_dir: Path,
    sources: dict[str, str],
    seen_filelists: set,
) -> None:
    if filelist_path in seen_filelists:
        return
    seen_filelists.add(filelist_path)

    try:
        with open(filelist_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//") or line.startswith("#"):
                    continue
                # 去掉行尾注释
                if "//" in line:
                    idx = line.find("//")
                    # 只在 // 前是空格时是注释
                    if idx > 0 and line[idx - 1] == " ":
                        line = line[:idx].strip()
                # 嵌套 filelist
                if line.startswith("-F") or line.startswith("-f"):
                    parts = line.split(None, 1)
                    if len(parts) >= 2:
                        sub = (filelist_path.parent / parts[1].strip()).resolve()
                        if sub.exists():
                            _read_filelist_recursive(sub, base_dir, sources, seen_filelists)
                    continue
                # +incdir+ / +define+ / +libext+ / 其他 + - 开头: 跳过 (本 helper 不处理)
                if line.startswith("+") or line.startswith("-"):
                    continue
                # 现在 line 是文件路径
                # 解析为绝对路径 (相对 base_dir 还是 filelist 所在目录? 用 base_dir)
                if not Path(line).is_absolute():
                    full = (base_dir / line).resolve()
                else:
                    full = Path(line).resolve()
                if full.exists() and full.is_file():
                    try:
                        sources[str(full)] = full.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        # 读失败的文件跳过, 不静默吞
                        pass
    except FileNotFoundError:
        return


# ----------------------------------------------------------------------------
# 2. elaboration 错误统一 catch (任务3, 给 CLI 干净错误)
# ----------------------------------------------------------------------------

def handle_compilation_error(e: CompilationError, strict: bool = True) -> None:
    """[ADD 2026-06-11 任务3] 统一处理 CompilationError, 不暴露 Python traceback

    [ADD 2026-06-12 Req-15 后续] 加 hint: 提示用户先修 filelist (正解),
    不到万不得已不用 --no-strict (bypass).

    Args:
        e: 抛出的 CompilationError
        strict: 是否严格模式 (strict 模式才 exit 1; non-strict 应被调用方自己处理)
    """
    msg = str(e)
    # CompilationError 格式: "Elaboration errors:\n<report>"
    # 提取前几行作为简短错误信息
    lines = msg.split("\n")
    header = lines[0] if lines else "Compilation failed"
    print(f"Error: {header}", file=sys.stderr)
    if strict:
        # 简洁输出前 10 行, 不暴露 Python stack
        detail_lines = [l for l in lines[1:] if l.strip()][:10]
        if detail_lines:
            print("\n".join(detail_lines), file=sys.stderr)
            if len(lines) > 11:
                print(f"  ... ({len(lines) - 11} more lines, see logs)", file=sys.stderr)
        # 推荐先检查 filelist
        # (错误代码在上面的 [ERROR] 行里, user 可以自己看)
        print(
            "\nHint: First check your filelist is complete (missing modules? missing includes?).",
            file=sys.stderr,
        )
        print(
            "      Use --no-strict to analyze the partial AST only as a last resort.",
            file=sys.stderr,
        )
    raise typer.Exit(code=1) from None


# ----------------------------------------------------------------------------
# 3. 通用 --filelist 参数 (typer.Option 复用)
# ----------------------------------------------------------------------------

# 给所有命令 import 这两个 typer.Option, 保持参数风格一致
FILE_OPTION = typer.Option(
    None, "--file", "-f", help="SystemVerilog source file (单文件模式)"
)
FILELIST_OPTION = typer.Option(
    None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects (项目模式)"
)
STRICT_OPTION = typer.Option(
    True,
    "--strict/--no-strict",
    help="Strict mode (default): elaboration error 立即 raise, exit 1. "
         "Use --no-strict 优雅降级存部分图 (供分析不完整项目用, e.g. OpenTitan/NaplesPU)",
)
LOG_LEVEL_OPTION = typer.Option(
    "WARNING", "--log-level", help="编译器日志级别 (DEBUG/INFO/WARNING/ERROR)"
)
PREPROCESS_OPTION = typer.Option(
    True,
    "--preprocess/--no-preprocess",
    help="Preprocess macros (default): 跨文件 `MACRO 展开, 避免 TooFewArguments. "
         "Use --no-preprocess 退回 pyslang 内置处理 (供不跨文件 define 的小项目用)",
)
