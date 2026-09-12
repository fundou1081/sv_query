"""
test_discipline_except_pass.py — [iter_190] AGENTS 纪律 2.5 的机械保障

背景: AGENTS.md v1.4 声称 "2026-08-29 已全仓清理, 全仓 `except: pass` 计数 = 0",
但 2026-09-08 实测 src/ 里有 **52 处** (25 处 `except Exception: pass`) —— 声明没有
机械保障, 于是又长回来了。`tools/check_except_pass.py` 把它变成可执行检查, 本测试
再把检查器本身接进测试集 (否则没人跑它)。

三层保证:
  1. 仓库当前状态 = 0 违规 (跑检查器, 断言退出码 0);
  2. 检查器**能检出**违规 (否则它是摆设) — 用临时目录构造 `except Exception: pass`;
  3. 检查器**不误报**允许形态 (收窄类型 + `...` + 注释)。
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
CHECKER = REPO / "tools" / "check_except_pass.py"

sys.path.insert(0, str(REPO / "tools"))
import check_except_pass as cep  # noqa: E402


def test_repo_has_no_except_pass():
    """仓库 src/ 必须 0 违规 (跑真实检查器, 不是 import 后自证)。"""
    r = subprocess.run([sys.executable, str(CHECKER)], capture_output=True, text=True)
    assert r.returncode == 0, (
        f"check_except_pass.py 报违规 (AGENTS 纪律 2.5):\n{r.stdout}\n{r.stderr}"
    )
    assert "计数 = 0" in r.stdout, r.stdout


def test_checker_detects_broad_except_pass(tmp_path):
    """检查器必须能检出宽类型 pass (自检: 否则等于没检查)。"""
    (tmp_path / "bad.py").write_text(
        "def f():\n"
        "    try:\n"
        "        return 1\n"
        "    except Exception:\n"
        "        pass\n",
        encoding="utf-8",
    )
    old = cep.SRC
    cep.SRC = tmp_path
    try:
        violations, _warnings = cep.scan()
    finally:
        cep.SRC = old
    assert violations, "检查器漏掉了 `except Exception: pass`"
    assert "宽类型" in violations[0][2]


def test_checker_detects_narrow_except_pass(tmp_path):
    """收窄类型但仍是 pass → 同样违规 (失败被静默吞掉)。"""
    (tmp_path / "bad2.py").write_text(
        "def f():\n"
        "    try:\n"
        "        return int('x')\n"
        "    except ValueError:\n"
        "        pass\n",
        encoding="utf-8",
    )
    old = cep.SRC
    cep.SRC = tmp_path
    try:
        violations, _warnings = cep.scan()
    finally:
        cep.SRC = old
    assert violations, "检查器漏掉了 `except ValueError: pass`"


def test_checker_accepts_logged_handler(tmp_path):
    """允许形态: 捕获 + 记录 (不 pass) → 无违规。"""
    (tmp_path / "ok.py").write_text(
        "import logging\n"
        "logger = logging.getLogger(__name__)\n\n"
        "def f():\n"
        "    try:\n"
        "        return int('x')\n"
        "    except ValueError as e:\n"
        "        logger.debug('非数字: %s', e)\n",
        encoding="utf-8",
    )
    old = cep.SRC
    cep.SRC = tmp_path
    try:
        violations, _warnings = cep.scan()
    finally:
        cep.SRC = old
    assert not violations, violations


def test_checker_warns_on_bare_ellipsis_without_comment(tmp_path):
    """收窄类型 + `...` 但无注释 → 警告级 (AGENTS 要求说明为何跳过合理)。"""
    (tmp_path / "warn.py").write_text(
        "def f():\n"
        "    try:\n"
        "        return int('x')\n"
        "    except ValueError:\n"
        "        ...\n",
        encoding="utf-8",
    )
    old = cep.SRC
    cep.SRC = tmp_path
    try:
        violations, warnings = cep.scan()
    finally:
        cep.SRC = old
    assert not violations
    assert warnings, "应给出'缺注释'警告"
