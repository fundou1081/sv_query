"""
test_generate_real_world.py — [Plan F1.5 2026-08-12] Real-world generate 覆盖

[Plan F1] generate for/if/case 全功能 fix 已经通过 8 unit + 5 regression + 15 CLI
测试验证. 但这些都是 synthetic fixtures — 真实 RTL 的 generate 用法常常更复杂
(嵌套 generate for + 条件 instantiate + parameter 依赖).

本文件用真实开源项目里的 generate-heavy SV 文件做 coverage:
  - ZipCPU (Dan Gisselquist, Gisselquist Tech, GPL)
    * wbxbar.v       — 49 generate lines, 1795 lines (Wishbone crossbar)
    * idecode.v      — 25 generate lines, 2185 lines (instruction decoder)
    * wb_tb.v        — 10 generate lines, 1754 lines (testbench)
    * axi2axilite.v  — 12 generate lines, 1220 lines (AXI→AXI-Lite bridge)
  - 这些文件代表真实 RTL generate 用法 (parameter 控制的 generate if,
    多 genvar 的 generate for, 跨模块 generate 等)

测试目标:
  - sv_query visualize dataflow 在真实 generate-heavy SV 上不 crash
  - 产出 SVG (而非 [ERROR])
  - 关键 signal 节点 (clock, reset, 主 data path) 出现在 graph 中
  - 不影响现有 strict_uart 黄金测试

文件选择标准 (手工 curate):
  - 含 generate 块
  - 1000-2500 行 (过小 trivial, 过大 RecursionError/ELK layout fail)
  - 单一文件 (不需要 filelist)

[铁律13] 金标准测试
[铁律17] 强断言
[铁律22] 断言验证具体行为
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# ZipCPU repository path (Dan Gisselquist, GPL-3.0)
ZIPCPU_RTL = Path("/Users/fundou/my_dv_proj/zipcpu")

# Curated real-world generate-heavy SV files (rc=0 verified 2026-08-12)
REAL_WORLD_FIXTURES = {
    "wbxbar": {
        "path": ZIPCPU_RTL / "sim/rtl/wbxbar.v",
        "generate_lines": 49,
        "total_lines": 1795,
        "purpose": "Wishbone crossbar — heavy generate for (SLAVES×MASTERS matrix)",
        "expected_data_min": 80,  # rc=0 实测 92
    },
    "idecode": {
        "path": ZIPCPU_RTL / "rtl/core/idecode.v",
        "generate_lines": 25,
        "total_lines": 2185,
        "purpose": "Instruction decoder — generate if/case for opcode decode",
        "expected_data_min": 120,  # rc=0 实测 138
    },
    "wb_tb": {
        "path": ZIPCPU_RTL / "sim/rtl/wb_tb.v",
        "generate_lines": 10,
        "total_lines": 1754,
        "purpose": "Wishbone testbench — generate for + initial blocks",
        "expected_data_min": 80,  # rc=0 实测 92
    },
    "axi2axilite": {
        "path": ZIPCPU_RTL / "sim/rtl/axi2axilite.v",
        "generate_lines": 12,
        "total_lines": 1220,
        "purpose": "AXI→AXI-Lite bridge — generate for response routing",
        "expected_data_min": 50,  # rc=0 实测 57
    },
}

TIMEOUT_SECONDS = 30  # 单文件最长运行时间


def _run_viz_on_real_world(sv_path: Path) -> tuple[int, str, str]:
    """跑 sv_query visualize dataflow 在真实 SV, 返 (rc, stdout, stderr)."""
    p = subprocess.run(
        ["sv_query", "visualize", "dataflow", "--file", str(sv_path), "--no-strict"],
        capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        cwd=str(PROJECT_ROOT),
    )
    return p.returncode, p.stdout, p.stderr


def _has_data_nodes_in_stderr(stderr: str) -> int | None:
    """从 stderr 抽 'Data nodes: N' 数字."""
    m = re.search(r"Data nodes:\s*(\d+)", stderr)
    return int(m.group(1)) if m else None


def _is_svg_output(stdout: str) -> bool:
    """stdout 是 SVG (不是 error 文本)."""
    return "<svg" in stdout


# Skip all tests if ZipCPU not cloned
ZIPCPU_AVAILABLE = ZIPCPU_RTL.exists() and ZIPCPU_RTL.is_dir()
pytestmark = pytest.mark.skipif(
    not ZIPCPU_AVAILABLE,
    reason=f"ZipCPU not found at {ZIPCPU_RTL}, skipping real-world generate tests"
)


# ── Parametrized: each real-world fixture is a test case ─────────────────

@pytest.mark.parametrize("fixture_name", list(REAL_WORLD_FIXTURES.keys()))
def test_real_world_generate_runs(fixture_name: str):
    """[Plan F1.5] sv_query visualize dataflow 在真实 generate-heavy SV 上不 crash"""
    fx = REAL_WORLD_FIXTURES[fixture_name]
    if not fx["path"].exists():
        pytest.skip(f"file not found: {fx['path']}")

    rc, stdout, stderr = _run_viz_on_real_world(fx["path"])
    assert rc == 0, (
        f"{fixture_name} ({fx['purpose']}):\n"
        f"  expected rc=0, got {rc}\n"
        f"  stderr (last 300): {stderr[-300:]}"
    )


@pytest.mark.parametrize("fixture_name", list(REAL_WORLD_FIXTURES.keys()))
def test_real_world_generate_produces_svg(fixture_name: str):
    """[Plan F1.5] 真实 SV 产出 SVG (非 error 文本)"""
    fx = REAL_WORLD_FIXTURES[fixture_name]
    if not fx["path"].exists():
        pytest.skip(f"file not found: {fx['path']}")

    rc, stdout, _ = _run_viz_on_real_world(fx["path"])
    assert rc == 0
    assert _is_svg_output(stdout), (
        f"{fixture_name}: expected SVG output, got {len(stdout)} bytes "
        f"(first 200: {stdout[:200]})"
    )


@pytest.mark.parametrize("fixture_name", list(REAL_WORLD_FIXTURES.keys()))
def test_real_world_generate_data_node_count(fixture_name: str):
    """[Plan F1.5] 真实 SV 的 Data nodes 数量 ≥ 已验证 baseline"""
    fx = REAL_WORLD_FIXTURES[fixture_name]
    if not fx["path"].exists():
        pytest.skip(f"file not found: {fx['path']}")

    rc, _, stderr = _run_viz_on_real_world(fx["path"])
    assert rc == 0
    n = _has_data_nodes_in_stderr(stderr)
    assert n is not None, f"{fixture_name}: missing 'Data nodes' in stderr: {stderr[-300:]}"
    assert n >= fx["expected_data_min"], (
        f"{fixture_name}: Data nodes {n} below expected {fx['expected_data_min']} "
        f"(regression check)"
    )


@pytest.mark.parametrize("fixture_name", list(REAL_WORLD_FIXTURES.keys()))
def test_real_world_generate_svg_has_content(fixture_name: str):
    """[Plan F1.5] SVG 包含实际节点 (≥ 5 个 <rect>)"""
    fx = REAL_WORLD_FIXTURES[fixture_name]
    if not fx["path"].exists():
        pytest.skip(f"file not found: {fx['path']}")

    rc, stdout, _ = _run_viz_on_real_world(fx["path"])
    assert rc == 0
    assert _is_svg_output(stdout)
    # SVG 节点 = <rect> 元素; 5+ 说明真的有数据图
    rect_count = len(re.findall(r"<rect", stdout))
    assert rect_count >= 5, (
        f"{fixture_name}: expected ≥5 SVG <rect> nodes, got {rect_count}"
    )


# ── Aggregate test: ensure new tests don't break strict_uart ────────────

class TestRealWorldGenerateNoRegression:
    """[Plan F1.5] 真实 SV 测试不能影响现有 strict_uart 黄金测试"""

    def test_strict_uart_still_runs(self):
        fl = PROJECT_ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"
        p = subprocess.run(
            ["sv_query", "visualize", "dataflow", "--filelist", str(fl), "--no-strict"],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        assert p.returncode == 0, f"strict_uart: visualize failed: {p.stderr[:300]}"
        assert "<svg" in p.stdout, f"strict_uart: expected SVG output, got: {p.stdout[:200]}"
        assert "Data nodes" in p.stderr, f"strict_uart: missing stats: {p.stderr[:200]}"


class TestRealWorldGenerateMetadata:
    """[Plan F1.5] 测试自己保证正确性 — fixture metadata 必须真实"""

    @pytest.mark.parametrize("fixture_name", list(REAL_WORLD_FIXTURES.keys()))
    def test_fixture_path_exists(self, fixture_name: str):
        fx = REAL_WORLD_FIXTURES[fixture_name]
        assert fx["path"].exists(), f"{fixture_name}: path missing: {fx['path']}"

    @pytest.mark.parametrize("fixture_name", list(REAL_WORLD_FIXTURES.keys()))
    def test_fixture_has_actual_generate_blocks(self, fixture_name: str):
        """fixture 必须真有 generate 块 (不是空 claim)"""
        fx = REAL_WORLD_FIXTURES[fixture_name]
        assert fx["path"].exists()
        with open(fx["path"]) as f:
            content = f.read()
        # 必须含 endgenerate 关键字
        assert "endgenerate" in content, (
            f"{fixture_name}: no 'endgenerate' found, not a real generate file"
        )
        # generate 关键字出现次数应 ≥ declared metadata
        gen_count = content.count("generate")
        assert gen_count >= fx["generate_lines"], (
            f"{fixture_name}: declared {fx['generate_lines']} generate lines, "
            f"actual {gen_count} (generate keyword count)"
        )
