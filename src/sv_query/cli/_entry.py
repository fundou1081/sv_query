# ruff: noqa: E402
"""Console script entry point for the `sv_query` command (P165.2).

Packaging layout:
  - `sv_query.cli` is a subpackage (console entry `sv_query.cli._entry:main`);
  - the query engine is `sv_query.trace`.

The old top-level `trace` package was removed because it collided with
Python's stdlib `trace` module.
"""
from .main import app, run  # noqa: F401  (run = 统一入口, app 供兼容导入)


def main():
    """Console entry point for `sv_query` script (after `pip install -e .`).

    `sv_query --help` lists the current command surface; use
    `sv_query capabilities --json` for the authoritative 39 core + 6 exp set.

    [iter_191] 实际执行 `main.run()` — 统一把输入类错误格式化成一行提示 (rc=1),
    不再向用户抛原始 traceback。
    """
    run()
