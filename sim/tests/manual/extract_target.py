"""extract_target.py — 用 semantic AST 提取 SV fixture 的顶层 module instance

[Plan 2026-08-12] 用 pyslang semantic AST (topInstances) 而非 regex
原因:
- 避免 regex 漏处理 multiline / package / interface / binary garbage 等 edge cases
- 拿 validated InstanceSymbol, 不是裸字符串
- 跟 sv_query 内部用同一套 semantic AST 接口

设计:
- 核心函数 extract_target(file) -> str (顶层 module instance name)
- 顶层 wrapper 判定: 取 root.topInstances 的**最后一个** (SV 惯例: helper modules 先
  declare, top wrapper 最后 instantiate)
- CLI: 接受单文件或多文件, 每行返一个 target

用法:
    # Python API
    from sim.tests.manual.extract_target import extract_target
    target = extract_target(Path('fixture.sv'))

    # CLI
    python3 -m sim.tests.manual.extract_target fixture.sv [more.sv ...]

    # 单文件快捷
    python3 -m sim.tests.manual.extract_target < golden_mini_dir/*.sv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 让 script 可以独立运行 (`python3 sim/tests/manual/extract_target.py`)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / 'src'))

from trace.core.compiler import compile_sources  # noqa: E402
from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402

# pyslang binary garbage 兜底名 — 跳过这些, 不要返给 caller
_BAD_NAMES = frozenset({'_unknown_', '_inst_', '_bad_', 'unknown', ''})


def extract_target(fix: Path | str) -> str:
    """提取 SV 文件的顶层 module instance name (top wrapper).

    用 semantic AST (pyslang Compilation + getRoot + topInstances).
    返回 root.topInstances 列表的**最后一个** InstanceSymbol 的名字 —
    SV 惯例: helper modules 先声明, top wrapper 最后 instantiate.

    Args:
        fix: SV 文件路径 (Path 或 str)

    Returns:
        顶层 module instance name; 若无法提取, 返回 fix.stem 作为 fallback.

    Raises:
        FileNotFoundError: SV 文件不存在
        RuntimeError: pyslang 编译失败

    Examples:
        >>> target = extract_target('golden_dataflow_26_hier_levels.sv')
        >>> target  # 'golden_hier_top'
    """
    fix_path = Path(fix)
    if not fix_path.exists():
        raise FileNotFoundError(f"SV file not found: {fix_path}")

    source = fix_path.read_text()
    comp, root = compile_sources({str(fix_path): source})
    adapter = SemanticAdapter(root=root, compiler=comp)

    # 防御: 旧 pyslang / 异常 fixture 可能没 topInstances
    if not hasattr(adapter._root, 'topInstances'):
        return fix_path.stem

    names: list[str] = []
    for inst in adapter._root.topInstances:
        name = adapter.get_module_name(inst)
        if name not in _BAD_NAMES:
            names.append(name)

    return names[-1] if names else fix_path.stem


def _cli(argv: list[str] | None = None) -> int:
    """CLI entry: 接受一个或多个 SV 文件, 每行返一个 target"""
    parser = argparse.ArgumentParser(
        description='提取 SV fixture 的顶层 module instance (用 semantic AST)',
    )
    parser.add_argument(
        'files', nargs='+', type=Path,
        help='一个或多个 SV 文件路径',
    )
    parser.add_argument(
        '--check', action='store_true',
        help='校验模式: 返 exit 0 若全部成功提取, exit 1 若有失败',
    )
    args = parser.parse_args(argv)

    rc = 0
    for f in args.files:
        try:
            target = extract_target(f)
            print(f"{f}: {target}")
        except Exception as e:
            print(f"{f}: ERROR {e}", file=sys.stderr)
            rc = 1

    return rc if args.check else 0


if __name__ == '__main__':
    sys.exit(_cli())