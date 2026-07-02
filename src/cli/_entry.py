"""
src/cli/_entry.py - Console script entry point for `sv_query` command.

[ADD 2026-07-02] 这个文件让 `pip install -e .` 真的能用:

  试过的 5 种配置都失败:
  1) [tool.setuptools] + package_dir: 报错 (package_dir 字段被 setuptools>=64 禁)
  2) packages.find where=["src"] include=["trace*", "cli*", "applications*"]:
     - 装为 top-level, 跟 Python stdlib `trace` 模块冲突
     - 'import trace' 拿到 stdlib trace, 报 'trace is not a package'
  3) packages.find include=["src", "src.*"]:
     - 装 src 为 top-level, 但 import path 跟 `from src.X` 一致
     - .pth 还是加 src/ 到 sys.path, 跟装为 top-level 冲突
  4) [project.scripts] sv_query = "run_cli:main":
     - run_cli.py 在仓库根, py-modules 装不出
  5) [project.scripts] sv_query = "src.cli.main:app":
     - src 装为 top-level 后, 代码用 from src.X import Y 可以
     - 但 `from src.cli.main import app` 还是 fail (src.cli.main 的解析路径问题)

  最终方案 (此文件):
  - cli 包内创建 _entry.py
  - [project.scripts] sv_query = "cli._entry:main"
  - 入口脚本把仓库根目录 (含 src/) 加到 sys.path, 然后 import
  - 跟 run_cli.py 一样的 sys.path.insert 模式
  - run_cli.py 保留仓库根, 给开发用 `python run_cli.py ...` (不依赖 install)
"""
import sys
from pathlib import Path

# 加 src/ 到 sys.path (优先级最高), 让 `from src.X.Y import Z` 能解析.
# 这是绕过 setuptools 装包命名冲突的最稳方式: 不靠 .pth, 自己控制 sys.path.
# 跟 run_cli.py 顶部的逻辑一致 (run_cli.py 也用 sys.path.insert).
#
# 为什么不是加项目根? 如果加项目根 (/Users/fundou/my_dv_proj/sv_query), Python
# 找 'import trace' 时会在项目根找 trace.py/trace/, 找不到, 然后 fallback 到
# stdlib 'trace' (at site-packages). 冲突.
# 如果加 src/ (/Users/fundou/my_dv_proj/sv_query/src), Python 找 'import trace'
# 会在 src/ 下找到 src/trace/ (含 __init__.py), 优先于 stdlib. 正确.
_THIS_FILE = Path(__file__).resolve()
_SRC_DIR = _THIS_FILE.parent.parent  # src/cli/_entry.py -> src/

# 总是 insert (不 guard): 确保 src/ 在 sys.path[0], 优先于 .pth + stdlib
sys.path.insert(0, str(_SRC_DIR))

from .main import app


def main():
    """Console entry point for `sv_query` script (after `pip install -e .`).

    `sv_query --help` 列出所有 19 个子命令:
    stats, search, trace, diff, snapshot, dataflow, controlflow, risk,
    sva, timing, cdc, coverage, verify, backpressure, handshake,
    protocol, regression, benchmark, arch
    """
    app()
