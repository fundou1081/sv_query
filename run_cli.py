#!/usr/bin/env python3
"""
CLI wrapper - run with: python run_cli.py dataflow --help

After `pip install -e .`, can also run as: sv_query <command>
"""
import sys
from pathlib import Path

# 添加项目根目录到 sys.path (包含 src/)
_project_root = Path(__file__).parent
_src_dir = _project_root / "src"
sys.path.insert(0, str(_src_dir))

from src.cli.main import run


def main():
    """Console entry point for `sv_query` script (after pip install).

    [FIX 2026-07-02] pyproject.toml [project.scripts] 引用 run_cli:main,
    但之前 run_cli.py 只有顶层 app() 调用, 没 main() 函数. `sv_query` 报 ImportError.
    [iter_191] 改走 `src.cli.main.run` — 与 console script 共用**统一错误格式化**
    (输入错误不再甩 traceback)。
    """
    run()


if __name__ == "__main__":
    main()
