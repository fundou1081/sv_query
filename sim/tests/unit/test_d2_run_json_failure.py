"""D2 回归 — CLI 顶层 `run()` 的失败出口（P183.1）。

锁定四件事:

1. `--json` 下**未预期异常**必须输出结构化错误信封（`ok:false` + `error_code`），
   stdout 不为空，rc=1；未分类异常映射 `E_INTERNAL`。
2. 非 `--json` 时未预期异常保持既有开发期行为：原样上抛，由解释器打印 traceback。
3. `src/cli/main.py` 的 `__main__` 走 `run()`（否则直接执行脚本会绕过统一错误格式化）。
4. `snapshot compare --json` 遇损坏快照（未知/缺失 EdgeKind、坏 JSON）输出 JSON + rc=1，
   不输出 Rich traceback；同时证明 D1 的 “未知 EdgeKind 显式失败” 没有被回退成 DRIVER。

`SVQ_DEBUG=1` 时先输出 JSON 再 re-raise（保留 traceback），与既有输入错误出口一致。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
RUN_CLI = REPO / "run_cli.py"
MAIN_PY = SRC / "cli" / "main.py"
MISSING_SV = REPO / "sim" / "tests" / "fixtures" / "hostile_input" / "no_such_file.sv"


def _env(**extra: str) -> dict[str, str]:
    """子进程环境: 固定 PYTHONPATH=src, 默认清掉 SVQ_DEBUG, 再套用显式覆盖。"""
    env = dict(os.environ)
    prior = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + prior if prior else "")
    env.pop("SVQ_DEBUG", None)
    env.update(extra)
    return env


def _run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUN_CLI), *args],
        cwd=str(REPO), capture_output=True, text=True, timeout=180,
        env=env or _env(),
    )


def _run_py(code: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO), capture_output=True, text=True, timeout=180,
        env=env or _env(),
    )


def _assert_no_rich_traceback(result: subprocess.CompletedProcess) -> None:
    combined = (result.stderr or "") + (result.stdout or "")
    assert "Traceback (most recent call last)" not in combined, (
        f"不应输出 traceback:\nstdout={result.stdout[:500]}\nstderr={result.stderr[:500]}"
    )


# ---------------------------------------------------------------------------
# 1. run(): 未预期异常 + --json
# ---------------------------------------------------------------------------
def test_unexpected_exception_json_emits_e_internal(monkeypatch, capsys):
    """未预期异常在 --json 下 → E_INTERNAL JSON 信封 + rc=1，stdout 不为空。"""
    from cli import main as cli_main

    def boom() -> None:
        raise RuntimeError("injected boom")

    monkeypatch.setattr(cli_main, "app", boom)
    monkeypatch.setattr(sys, "argv", ["sv_query", "boom", "--json"])
    monkeypatch.delenv("SVQ_DEBUG", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        cli_main.run()

    assert excinfo.value.code == 1
    stdout = capsys.readouterr().out
    assert stdout.strip(), "--json 失败时 stdout 不得为空"
    payload = json.loads(stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_INTERNAL"
    assert payload["command"] == "boom"
    assert payload["error"]["type"] == "RuntimeError"
    assert "injected boom" in payload["error"]["message"]


def test_unexpected_exception_with_json_short_flag(monkeypatch, capsys):
    """`-j` 与 `--json` 等价（不能只认长选项）。"""
    from cli import main as cli_main

    def boom() -> None:
        raise ValueError("short flag")

    monkeypatch.setattr(cli_main, "app", boom)
    monkeypatch.setattr(sys, "argv", ["sv_query", "boom", "-j"])
    monkeypatch.delenv("SVQ_DEBUG", raising=False)

    with pytest.raises(SystemExit):
        cli_main.run()

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    # ValueError 由既有 code_for_exception 映射，不是 E_INTERNAL
    assert payload["error_code"] == "E_INVALID_INPUT"


# ---------------------------------------------------------------------------
# 2. 非 JSON: 保持 traceback（既有行为，不吞错）
# ---------------------------------------------------------------------------
def test_unexpected_exception_non_json_keeps_traceback():
    """非 --json 的未预期异常：上抛并打印 traceback，stdout 不产出 JSON。"""
    code = (
        "import sys\n"
        "from cli import main\n"
        "def boom():\n"
        "    raise RuntimeError('injected boom')\n"
        "main.app = boom\n"
        "sys.argv = ['sv_query', 'boom']\n"
        "main.run()\n"
    )
    result = _run_py(code)
    assert result.returncode == 1
    assert result.stdout == "", f"非 --json 不应产出 JSON: {result.stdout[:300]}"
    assert "Traceback (most recent call last)" in result.stderr
    assert "RuntimeError: injected boom" in result.stderr


def test_controlled_typer_exit_is_not_relabelled_internal(tmp_path):
    """命令内 `fail()` 的 typer.Exit 不能被当成未预期异常（避免双 JSON / 错码）。"""
    env = _env(SVQ_SNAPSHOT_DIR=str(tmp_path))
    result = _run_cli("paths", "a", "b", "--from-snapshot", "no_such_tag", "--json", env=env)
    assert result.returncode == 1
    _assert_no_rich_traceback(result)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload.get("error_code") != "E_INTERNAL"
    assert "E_INTERNAL" not in result.stdout


# ---------------------------------------------------------------------------
# 3. __main__ 走 run()
# ---------------------------------------------------------------------------
def test_main_module_entry_uses_run():
    """直接执行 `src/cli/main.py` 也必须走统一错误格式化。"""
    result = subprocess.run(
        [sys.executable, str(MAIN_PY), "stats", "-f", str(MISSING_SV), "--json"],
        cwd=str(REPO), capture_output=True, text=True, timeout=180, env=_env(),
    )
    assert result.returncode == 1
    _assert_no_rich_traceback(result)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_FILE_NOT_FOUND"
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# 4. snapshot compare --json 损坏快照
# ---------------------------------------------------------------------------
def _graph_dict(tag: str) -> dict:
    from sv_query.trace.core.graph.models import (
        EdgeKind, NodeKind, SignalGraph, TraceEdge, TraceNode,
    )

    graph = SignalGraph()
    graph.add_trace_node(TraceNode("top.a", "a", "top", NodeKind.SIGNAL, (0, 0)))
    graph.add_trace_node(TraceNode("top.b", "b", "top", NodeKind.REG, (0, 0)))
    graph.add_trace_edge(TraceEdge("top.a", "top.b", EdgeKind.DRIVER))
    return {"tag": tag, **graph.to_dict()}


def _write_snapshot(dir_path: Path, tag: str, corrupt: str | None = None) -> None:
    if corrupt == "malformed_json":
        (dir_path / f"{tag}.json").write_text("{not valid json", encoding="utf-8")
        return
    data = _graph_dict(tag)
    if corrupt == "unknown_kind":
        data["edges"][0]["kind"] = "FUTURE_CONTROL"
    elif corrupt == "missing_kind":
        del data["edges"][0]["kind"]
    (dir_path / f"{tag}.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("corrupt", ["unknown_kind", "missing_kind", "malformed_json"])
def test_snapshot_compare_corrupt_json_is_structured(tmp_path, corrupt):
    """损坏快照：JSON + rc=1，无 Rich traceback；D1 的显式失败仍生效。"""
    _write_snapshot(tmp_path, "good")
    _write_snapshot(tmp_path, "bad", corrupt)

    result = _run_cli(
        "snapshot", "compare", "good", "bad", "--json",
        env=_env(SVQ_SNAPSHOT_DIR=str(tmp_path)),
    )

    assert result.returncode == 1
    _assert_no_rich_traceback(result)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_INVALID_INPUT"
    assert payload["command"] == "snapshot compare"
    message = payload["error"]["message"]
    if corrupt == "unknown_kind":
        # D1 语义未回归：不静默回退 DRIVER
        assert "unknown EdgeKind" in message
        assert "FUTURE_CONTROL" in message
    elif corrupt == "missing_kind":
        assert "missing 'kind'" in message
    else:
        assert "invalid snapshot" in message


def test_snapshot_compare_valid_snapshots_still_json_ok(tmp_path):
    """真阴性：损坏处理不能把正常对比也变成 rc=1。"""
    _write_snapshot(tmp_path, "one")
    _write_snapshot(tmp_path, "two")
    result = _run_cli(
        "snapshot", "compare", "one", "two", "--json",
        env=_env(SVQ_SNAPSHOT_DIR=str(tmp_path)),
    )
    assert result.returncode == 0, result.stderr[:500]
    payload = json.loads(result.stdout)
    assert payload.get("identical") is True


# ---------------------------------------------------------------------------
# 5. SVQ_DEBUG=1 保留 traceback
# ---------------------------------------------------------------------------
def test_unexpected_exception_json_svq_debug_keeps_traceback():
    """SVQ_DEBUG=1: 仍先输出 JSON 信封，再 re-raise 供开发定位。"""
    code = (
        "import sys\n"
        "from cli import main\n"
        "def boom():\n"
        "    raise RuntimeError('injected boom')\n"
        "main.app = boom\n"
        "sys.argv = ['sv_query', 'boom', '--json']\n"
        "main.run()\n"
    )
    result = _run_py(code, env=_env(SVQ_DEBUG="1"))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error_code"] == "E_INTERNAL"
    assert "Traceback (most recent call last)" in result.stderr
    assert "RuntimeError: injected boom" in result.stderr
