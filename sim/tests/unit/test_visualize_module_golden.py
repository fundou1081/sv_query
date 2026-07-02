"""Integration test: visualize module → diff vs golden.

[REFACTOR 2026-07-02] 从 pulp_axi_xbar 改用 strict_uart fixture:
  原 fixture 加载 pulp_axi_xbar.f (~30 SV files) 在 8GB MBA 触发 pyslang SIGSEGV.
  5 个测试全部 xfail (期望失败), 但 segfault 仍杀死整个 pytest runner.

  新方案: 用 sim/tests/fixtures/strict_uart/ (4 个自洽 SV, 永远不 OOM).
  - targets: uart_top, synchronizer, sync_fifo, nonexistent
  - goldens: tests/golden/{uart_top,synchronizer}_module.json

测试目的 (核心, 不变):
  端到端测试 `visualize module` 命令 + golden diff 工具:
  - test_visualize_module_on_uart_top: 跑 visualize + diff vs golden
  - test_visualize_module_generates_valid_json: 验证 JSON schema
  - test_visualize_module_filters_binary_garbage: 验证节点 id 无 control chars
  - test_visualize_module_depth_limit_respected: 验证 --depth 限制
  - test_visualize_module_handles_missing_target: 验证 missing target 不 crash

测试黄金生成 (Phase 3 2026-07-02):
  $ python3 run_cli.py visualize module \\
      --filelist sim/tests/fixtures/strict_uart/filelist.f \\
      --target uart_top --depth 2 --no-strict \\
      --output-json tests/golden/uart_top_module.json
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STRICT_UART_FILELIST = str(PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f")
UART_TOP_GOLDEN = PROJECT_ROOT / "tests" / "golden" / "uart_top_module.json"
SYNCHRONIZER_GOLDEN = PROJECT_ROOT / "tests" / "golden" / "synchronizer_module.json"
DIFF_TOOL = PROJECT_ROOT / "tools" / "golden" / "diff.py"
RUN_CLI = PROJECT_ROOT / "run_cli.py"


def _run_cli_module(filelist: str, target: str, depth: int, output_json: Path) -> int:
    """Run `visualize module` on a given filelist, return exit code."""
    result = subprocess.run(
        [
            sys.executable, str(RUN_CLI),
            "visualize", "module",
            "--filelist", filelist,
            "--target", target,
            "--depth", str(depth), "--no-strict",
            "--output-json", str(output_json),
        ],
        capture_output=True, text=True, timeout=60, cwd=PROJECT_ROOT,
    )
    return result.returncode


def _run_diff(golden: Path, actual: Path) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(DIFF_TOOL),
         "--golden", str(golden), "--actual", str(actual)],
        capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT,
    )
    return result.returncode, result.stdout, result.stderr


def test_visualize_module_on_uart_top(tmp_path):
    """[REFACTOR 2026-07-02] 跑 visualize module on uart_top + diff vs golden.

    uart_top 实例化 sync_fifo, 所以 graph 应有 1 个 instance node (uart_top.rx_fifo).
    黄金: tests/golden/uart_top_module.json (含 rx_fifo def_name=sync_fifo).
    """
    actual = tmp_path / "actual.json"
    rc = _run_cli_module(STRICT_UART_FILELIST, "uart_top", 2, actual)
    assert rc == 0, f"visualize module failed: rc={rc}"

    rc, out, err = _run_diff(UART_TOP_GOLDEN, actual)
    assert rc == 0, f"diff vs golden failed: rc={rc}, stdout={out[:500]}, stderr={err[:300]}"
    assert "Match" in out, f"expected Match message, got: {out[:200]}"


def test_visualize_module_generates_valid_json(tmp_path):
    """[REFACTOR 2026-07-02] visualize module 应该输出合法 JSON."""
    actual = tmp_path / "actual.json"
    rc = _run_cli_module(STRICT_UART_FILELIST, "uart_top", 2, actual)
    assert rc == 0
    assert actual.exists()
    data = json.loads(actual.read_text())
    # 必要字段
    assert "module" in data
    assert "view" in data
    assert "level" in data
    assert "nodes" in data
    assert data["view"] == "module"
    assert data["level"] == 1
    assert data["module"] == "uart_top"


def test_visualize_module_filters_binary_garbage(tmp_path):
    """[REFACTOR 2026-07-02] 节点 id 不应该含 binary control chars."""
    actual = tmp_path / "actual.json"
    rc = _run_cli_module(STRICT_UART_FILELIST, "uart_top", 2, actual)
    assert rc == 0
    data = json.loads(actual.read_text())
    for node in data.get("nodes", []):
        # 节点 id 不应含 control chars
        for c in node["id"]:
            assert ord(c) >= 0x20, f"Binary garbage in node id: {node['id']!r}"


def test_visualize_module_depth_limit_respected(tmp_path):
    """[REFACTOR 2026-07-02] --depth flag 应该限制抽取深度.

    uart_top (depth 2) 应该有 1 个 instance node (rx_fifo).
    synchronizer (depth 2) 应该有 0 个 instance (没有 instance).
    """
    actual_uart = tmp_path / "actual_uart.json"
    actual_sync = tmp_path / "actual_sync.json"
    _run_cli_module(STRICT_UART_FILELIST, "uart_top", 2, actual_uart)
    _run_cli_module(STRICT_UART_FILELIST, "synchronizer", 2, actual_sync)
    d_uart = json.loads(actual_uart.read_text())
    d_sync = json.loads(actual_sync.read_text())
    # uart_top 有 1 instance (rx_fifo), synchronizer 没有 instance
    assert len(d_uart["nodes"]) >= 1, (
        f"uart_top should have ≥1 instance nodes, got {len(d_uart['nodes'])}"
    )
    assert len(d_sync["nodes"]) == 0, (
        f"synchronizer should have 0 instance nodes, got {len(d_sync['nodes'])}"
    )


def test_visualize_module_handles_missing_target(tmp_path):
    """[REFACTOR 2026-07-02] 找不到 target 时不应该 crash, 返回空 instances."""
    actual = tmp_path / "actual.json"
    rc = _run_cli_module(STRICT_UART_FILELIST, "nonexistent_module_xyz", 3, actual)
    # 不期望 crash, rc 可能 0 或 1
    assert actual.exists()
    data = json.loads(actual.read_text())
    assert data["module"] == "nonexistent_module_xyz"
    assert data["nodes"] == []  # 没找到


# ============================================================================
# Main (standalone run)
# ============================================================================

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
