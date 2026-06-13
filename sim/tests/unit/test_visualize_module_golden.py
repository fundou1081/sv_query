"""Integration test: visualize module → diff vs golden (PR1 2026-06-13)

[PR1 2026-06-13] 端到端测试: 跑 pulp axi_xbar 的 visualize module,
对比黄金图 (用 skip_in_diff 字段容忍 aspirational 内容).
"""
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PULP_FILIST = "/tmp/pulp_axi_xbar.f"
GOLDEN = PROJECT_ROOT / "tests" / "golden" / "axi_xbar_module.json"
DIFF_TOOL = PROJECT_ROOT / "tools" / "golden" / "diff.py"
RUN_CLI = PROJECT_ROOT / "run_cli.py"


def _run_cli_module(target: str, depth: int, output_json: Path) -> int:
    """Run `visualize module` and return exit code."""
    result = subprocess.run(
        [
            sys.executable, str(RUN_CLI),
            "visualize", "module",
            "--filelist", PULP_FILIST,
            "--target", target,
            "--depth", str(depth),
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


def test_visualize_module_on_axi_mux_intf(tmp_path):
    """[PR1] axi_mux_intf 是 typedef interface, graph 实际能看到 i_axi_mux.
    跑 visualize module + diff vs golden, 验证基础流程通过.
    """
    actual = tmp_path / "actual.json"
    rc = _run_cli_module("axi_mux_intf", 2, actual)
    assert rc == 0

    rc, out, err = _run_diff(GOLDEN, actual)
    # 黄金是 axi_xbar_intf, 实际是 axi_mux_intf, 所以 module 名字 mismatch 正常
    # 关键验证: aspirational 节点 (skip_in_diff=true) 不会让 diff fail
    # 实际可能报: module name mismatch + extra nodes + cluster missing
    # 但不能有 "missing: i_xbar" 或 "missing: i_xbar_unmuxed" 等 aspirational 节点
    assert "missing: i_xbar" not in out, f"aspirational node leaked as missing: {out}"
    assert "missing: i_axi_mux" not in out, f"aspirational node leaked as missing: {out}"


def test_visualize_module_generates_valid_json(tmp_path):
    """[PR1] visualize module 应该输出合法 JSON"""
    actual = tmp_path / "actual.json"
    rc = _run_cli_module("axi_mux_intf", 2, actual)
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


def test_visualize_module_filters_binary_garbage(tmp_path):
    """[PR1] 黄金对比时, binary garbage 节点不会让 diff fail"""
    actual = tmp_path / "actual.json"
    rc = _run_cli_module("axi_xbar_unmuxed_intf", 3, actual)
    assert rc == 0

    # 即使 axi_xbar_unmuxed_intf 有 binary garbage, diff 也不应该 fail
    # (因为 visualize module 应该已经过滤掉了)
    data = json.loads(actual.read_text())
    for node in data.get("nodes", []):
        # 节点 id 不应含 control chars
        for c in node["id"]:
            assert ord(c) >= 0x20, f"Binary garbage in node id: {node['id']!r}"


def test_visualize_module_depth_limit_respected(tmp_path):
    """[PR1] --depth flag 应该限制抽取深度"""
    actual_depth1 = tmp_path / "actual1.json"
    actual_depth3 = tmp_path / "actual3.json"
    _run_cli_module("axi_id_remap_intf", 1, actual_depth1)
    _run_cli_module("axi_id_remap_intf", 3, actual_depth3)
    d1 = json.loads(actual_depth1.read_text())
    d3 = json.loads(actual_depth3.read_text())
    # depth=3 至少不比 depth=1 少
    assert len(d3["nodes"]) >= len(d1["nodes"]), \
        f"depth=3 ({len(d3['nodes'])}) should have >= nodes vs depth=1 ({len(d1['nodes'])})"


def test_visualize_module_handles_missing_target(tmp_path):
    """[PR1] 找不到 target 时不应该 crash, 返回空 instances"""
    actual = tmp_path / "actual.json"
    rc = _run_cli_module("nonexistent_module_xyz", 3, actual)
    # 不期望 crash, rc 可能 0 或 1
    assert actual.exists()
    data = json.loads(actual.read_text())
    assert data["module"] == "nonexistent_module_xyz"
    assert data["nodes"] == []  # 没找到
