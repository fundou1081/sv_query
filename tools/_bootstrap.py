"""
tools/_bootstrap.py — [iter_234 P2] 仓库内脚本的统一路径引导 (单一真相源)

为什么需要: 脚本要 `import cli` / `import trace` (在 `<repo>/src` 下), 但
**guarded insert 是错的**:
    if str(SRC) not in sys.path:      # ← src 已由 editable install 的 .pth 放进 sys.path,
        sys.path.insert(0, str(SRC))  #    但排在 stdlib 之后 → guard 跳过插入
                                      #    → `import trace` 命中 **stdlib 的 trace.py**
                                      #      ("'trace' is not a package")
实测 (iter_234): `tools/fix_timescale.py` 因此长期无法运行 (用 `python3 -c` 直连
_PYTHONPATH 时才"看起来正常"), 由新加的 tools 级测试首次暴露。

正确做法: **无条件插到最前** (与 `src/cli/_entry.py` 的既有注释一致: "总是 insert 不 guard")。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
SRC_DIR: Path = REPO_ROOT / "src"


def ensure_src_first() -> None:
    """把 `<repo>/src` 无条件插到 sys.path[0] (先于 stdlib 与 .pth)。"""
    s = str(SRC_DIR)
    while s in sys.path:          # 先移除已有条目 (可能在 stdlib 之后)
        sys.path.remove(s)
    sys.path.insert(0, s)


ensure_src_first()
