"""
test_cli_hostile_input.py — [iter_191] 敌意输入只许"干净报错", 不许崩进程/甩 traceback

背景: iter_189 修掉了 `addSyntaxTree` 原生 SIGTRAP (垃圾输入曾直接打死进程),
iter_190 清算了 `except: pass` (静默失败), iter_191 统一了 CLI 顶层错误格式化
(输入错误以前甩原始 traceback)。

本测试把这三件事锁在一起, 用一张**敌意输入矩阵** × 多个子命令验证三条不变量:
  1. **绝不因信号死亡** (rc < 0 或 133/134/138/139 都算崩);
  2. **绝不向用户打印原始 traceback** (`Traceback (most recent call last)`);
  3. 非法输入 → 非 0 退出码 (不能"看起来成功")。

矩阵里也包含**合法但极端**的输入 (空文件/仅注释/CRLF/BOM), 它们必须成功 — 防止把
守卫写成"一律拒绝"。
"""
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "sim" / "tests" / "fixtures" / "hostile_input"   # 与项目 fixture 约定一致
SIGNAL_CODES = {133, 134, 138, 139}

# 敌意输入 (非法): 期望 rc != 0, 且不崩 / 不甩 traceback
BAD_INPUTS = {
    "filelist 当源码 (路径被当 SV)": ["-f", str(FIXTURES / "filelist_as_sv.sv")],
    "非 SV 文本": ["-f", str(FIXTURES / "not_verilog.txt")],
    "二进制文件": ["-f", str(FIXTURES / "binary.sv")],
    "UTF-16 编码": ["-f", str(FIXTURES / "utf16.sv")],
    "目录当文件": ["-f", str(FIXTURES / "a_dir.sv")],
    "文件不存在": ["-f", str(FIXTURES / "no_such_file.sv")],
    "filelist 不存在": ["--filelist", str(FIXTURES / "no_such.f")],
}

# 合法但极端: 期望 rc == 0 (守卫不能误伤)
GOOD_INPUTS = {
    "空文件": ["-f", str(FIXTURES / "empty.sv")],
    "仅注释": ["-f", str(FIXTURES / "only_comment.sv")],
    "仅 define": ["-f", str(FIXTURES / "only_define.sv")],
    "裸 endmodule": ["-f", str(FIXTURES / "only_endmodule.sv")],
    "CRLF + BOM": ["-f", str(FIXTURES / "bom_crlf.sv")],
    "正常 module": ["-f", str(FIXTURES / "normal.sv")],
}

COMMANDS = {
    "visualize graph": ["visualize", "graph"],
    "visualize module": ["visualize", "module"],
    "stats": ["stats"],
}


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(REPO / "run_cli.py"), *args],
        capture_output=True, text=True, timeout=300, cwd=REPO,
    )


def _assert_clean(result: subprocess.CompletedProcess, label: str) -> None:
    assert result.returncode not in SIGNAL_CODES and result.returncode >= 0, (
        f"{label}: 进程被信号打死 (rc={result.returncode}) — 禁止崩溃\n"
        f"stdout tail: {result.stdout[-400:]}\nstderr tail: {result.stderr[-400:]}"
    )
    combined = (result.stderr or "") + (result.stdout or "")
    assert "Traceback (most recent call last)" not in combined, (
        f"{label}: 向用户打印了原始 traceback — 应走 CLI 顶层错误格式化\n"
        f"{combined[-600:]}"
    )


@pytest.mark.parametrize("cmd_name,cmd", sorted(COMMANDS.items()))
@pytest.mark.parametrize("case_name,args", sorted(BAD_INPUTS.items()))
def test_bad_input_fails_cleanly(cmd_name, cmd, case_name, args):
    """非法输入: 非 0 退出 + 不崩 + 无 traceback。"""
    result = _run([*cmd, *args])
    _assert_clean(result, f"{cmd_name} / {case_name}")
    assert result.returncode != 0, (
        f"{cmd_name} / {case_name}: 非法输入却返回 0 (看起来成功 = 静默失败)\n"
        f"stdout: {result.stdout[-400:]}"
    )


@pytest.mark.parametrize("cmd_name,cmd", sorted(COMMANDS.items()))
@pytest.mark.parametrize("case_name,args", sorted(GOOD_INPUTS.items()))
def test_extreme_but_valid_input_succeeds(cmd_name, cmd, case_name, args):
    """合法但极端的输入: 必须成功 (守卫不能误伤 / 不能一律拒绝)。"""
    result = _run([*cmd, *args])
    _assert_clean(result, f"{cmd_name} / {case_name}")
    assert result.returncode == 0, (
        f"{cmd_name} / {case_name}: 合法输入被拒 (rc={result.returncode})\n"
        f"stderr: {result.stderr[-400:]}"
    )


def test_svq_debug_env_restores_traceback():
    """`SVQ_DEBUG=1` 时必须恢复完整 traceback (开发者要能定位)。"""
    import os

    env = dict(os.environ, SVQ_DEBUG="1")
    result = subprocess.run(
        [sys.executable, str(REPO / "run_cli.py"), "visualize", "graph",
         "-f", str(FIXTURES / "no_such_file.sv")],
        capture_output=True, text=True, timeout=300, cwd=REPO, env=env,
    )
    combined = (result.stderr or "") + (result.stdout or "")
    assert "Traceback (most recent call last)" in combined, (
        "SVQ_DEBUG=1 应保留 traceback 供开发定位"
    )
