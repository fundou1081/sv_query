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

import typer

from trace.core.compiler import CompilationError
from trace.unified_tracer import UnifiedTracer
import logging

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# 1. tracer 构建 (核心 helper, 所有 --file 命令复用)
# ----------------------------------------------------------------------------

def _build_tracer(
    file: Path | None = None,
    filelist: str | None = None,
    strict: bool = True,
    log_level: str = "WARNING",
    include_dirs: list | None = None,
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
    # [Bug fix 2026-07-09 CLI-SIGTRAP] Auto-detect: if `file` ends in filelist
    # extension (.f / .fl / .filelist), 用户用 -f flag 传 filelist 时 typer 会
    # 把值塞进 `file` (--file) 而非 filelist, 然后 pyslang 解析 filelist 作为
    # Verilog source 会崩溃 (SIGTRAP / exit 133).
    # Fix: 检测 `file` 后缀, 若是 filelist, 转走 filelist 路径.
    _FILELIST_EXTS = (".f", ".fl", ".filelist")
    _resolved_filelist = filelist
    _resolved_file = file
    if _resolved_file is not None and str(_resolved_file).lower().endswith(_FILELIST_EXTS):
        # promote file to filelist
        _resolved_filelist = str(_resolved_file)
        _resolved_file = None

    if _resolved_filelist:
        if not Path(_resolved_filelist).exists():
            raise FileNotFoundError(f"Filelist not found: {_resolved_filelist}")
        # [FIX 2026-06-11 Req-9] 手动读 filelist 转 sources, 避免 add_filelist
        # 处理 relative path 失败的 bug. 用 cwd 作为 base_dir
        # (filelist 里 relative path 相对项目根, 符合开发者心智模型)
        # [Bug fix 2026-06-25] auto-detect base_dir from filelist content.
        # CVA6 filelist 用相对路径 'core/include/ariane_pkg.sv', 应相对 cva6 项目根.
        # Heuristic: 用 filelist 中第一个 relative path 的最长公共前缀作为 base_dir.
        filelist_path = Path(_resolved_filelist).resolve()
        base_dir = _detect_filelist_base_dir(filelist_path, fallback=Path.cwd())
        sources = _read_filelist(filelist_path, base_dir=base_dir)
        tracer = UnifiedTracer(
            sources=sources,
            log_level=log_level,
            include_dirs=include_dirs or [],
            strict=strict,
            preprocess_macros=preprocess_macros,  # [Req-20 2026-06-12]
        )
    elif _resolved_file is not None:
        if not _resolved_file.exists():
            raise FileNotFoundError(f"Source file not found: {_resolved_file}")
        with open(str(_resolved_file)) as f:
            source = f.read()
        tracer = UnifiedTracer(
            sources={str(_resolved_file): source},
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
    """读 filelist 把所有源文件读成 sources dict (供 SVA/coverage 等需要内容的命令)。

    [iter_193] 解析统一走 `trace.core.filelist.parse_filelist` — 与编译入口
    (`SVCompiler.add_filelist`) **同一份实现**, 因此:
      - 相对路径候选规则一致 (filelist 所在目录 → base_dir), 不再出现
        "两侧结果不同 / 对存在的文件误报缺失" (iter_190/192 的问题);
      - 缺失条目由解析器统一告警 (不静默跳过);
      - filelist 本身不存在 → FileNotFoundError("Filelist not found: ...")。

    Returns:
        {绝对路径: 文件内容}; 读单个文件失败时告警并跳过该文件。
    """
    from trace.core.filelist import parse_filelist

    # [iter_194] 候选基准 = 调用方给的 base_dir **再加上 cwd**:
    # 仓库内 industrial_filelists 用的是"仓库根相对"路径, 而调用方给的 base_dir 可能
    # 就是 filelist 目录本身 → 只有 filelist 目录一个候选时会误判缺失 (实测
    # test_naplespu_4_level_chained_include 因此失败)。tracer 侧的第二基准固定是
    # cwd, 这里补齐以保证两侧候选集合一致。
    base_dirs = [base_dir]
    if Path.cwd() != Path(base_dir).resolve():
        base_dirs.append(Path.cwd())
    spec = parse_filelist(filelist_path, base_dirs=base_dirs)
    sources: dict[str, str] = {}
    for f in spec.files:
        try:
            sources[f] = Path(f).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("filelist 条目读取失败, 跳过: %s (%s)", f, e)
    spec.warn_missing(filelist_path)
    # 注: 这里**不**因"零文件"硬失败 — 本函数只是 CLI 侧辅助加载器 (供需要 sources
    # dict 的命令用), 真正编译入口是 tracer; 两者解析规则现已一致, 但调用方语义不同。
    # [iter_194] 一个文件都没解析出来 → 明确报错。解析规则已与 tracer 侧统一
    # (iter_193), 所以"空"就是真的空; 过去只告警 → 命令继续跑并输出空图 (rc=0),
    # 用户以为成功。这是"输入无效", 必须可见且非 0。
    if not sources:
        raise CompilationError(
            f"filelist {filelist_path} 没有解析到任何源文件 "
            f"({len(spec.missing)} 个条目缺失/不可解析) — 请检查路径与基准目录"
        )
    return sources


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
        detail_lines = [line for line in lines[1:] if line.strip()][:10]
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
