"""
cli/_paths.py — 项目路径锚点 (单一真相源)

[iter_232 P1b-1 2026-09-09] 起因: 把命令文件从 `src/cli/commands/` 搬到
`src/cli/exp/verif/` 后, 各文件里 `Path(__file__).parent.parent.parent.parent`
的**深度计算全部错位** (少了一层):
  - `sys.path.insert(0, ...)` 插错目录 (靠 run_cli/conftest 兜住, 属侥幸)
  - `coverage.py` 的 `Path(__file__).resolve().parents[3] / "tools"` 变成 `src/tools`
    → `import coverage_gen_demo` 直接 ImportError (实测 16 个测试红)

**规则**: `src/cli/**` 内**禁止**再用 `__file__` 做深度运算导路径, 一律从这里取。
由 `tools/check_cli_layers.py` 的 **R8** 机械强制 (本文件自身豁免) ——
这样下一次搬目录 (P1b-2: core/view) 不会重演同类事故。
"""
from __future__ import annotations

from pathlib import Path

#: `src/cli/` (本文件所在目录)
CLI_DIR: Path = Path(__file__).resolve().parent
#: `src/` (import `trace` / `cli` 的根)
SRC_DIR: Path = CLI_DIR.parent
#: 仓库根 (含 tools/ docs/ sim/)
PROJECT_ROOT: Path = SRC_DIR.parent
#: `tools/` (仓库内脚本, 如 coverage_gen_demo.py)
TOOLS_DIR: Path = PROJECT_ROOT / "tools"


def ensure_on_path(*dirs: Path) -> None:
    """把目录加入 sys.path (幂等, 只补缺失的)。"""
    import sys

    for d in dirs:
        s = str(d)
        if s not in sys.path:
            sys.path.insert(0, s)
