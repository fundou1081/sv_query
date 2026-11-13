# ruff: noqa: E402
"""Console script entry point for the `sv_query` command (P165.2).

Packaging layout:
  - `cli` is a top-level package (console entry `cli._entry:main`);
  - the query engine is `sv_query.trace`;
  - `src/` is still inserted on sys.path for legacy development imports
    (`from src.cli...`) and for editable checkouts.

The old top-level `trace` package was removed because it collided with
Python's stdlib `trace` module.
"""
import sys
from pathlib import Path

# P165.2: keep src/ on sys.path for editable checkouts and legacy src.cli
# imports. The installed query engine itself is top-level sv_query.trace.
from cli._paths import SRC_DIR as _SRC_DIR  # [iter_232] 路径锚点单一真相源

# 总是 insert (不 guard): 确保 editable checkout 的 src/ 优先解析.
sys.path.insert(0, str(_SRC_DIR))

from .main import app, run  # noqa: F401  (run = 统一入口, app 供兼容导入)


def main():
    """Console entry point for `sv_query` script (after `pip install -e .`).

    `sv_query --help` lists the current command surface; use
    `sv_query capabilities --json` for the authoritative 39 core + 6 exp set.

    [iter_191] 实际执行 `main.run()` — 统一把输入类错误格式化成一行提示 (rc=1),
    不再向用户抛原始 traceback。
    """
    run()
