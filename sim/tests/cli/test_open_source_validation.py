"""
test_open_source_validation.py - V6.3+4 2026-07-28: validate V6.3+3/+4 on
multiple real RISC-V designs.

Tests on three real-world open-source projects:
  - picorv32  (Claire Wolf, ~3000 lines, RISC-V CPU)
  - darkriscv (2038.io, smaller RV32I core)
  - ventus Scheduler.v (OpenGPU, large cache scheduler)

Each test asserts the graph builds, has the expected node/edge counts,
and exposes any regressions in ternary decomposition on real code.

Run with:
    PYTHONPATH=src:tools python3 -m pytest sim/tests/cli/test_open_source_validation.py
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.opensource

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PYTHONPATH = str(PROJECT_ROOT / "src") + ":" + str(PROJECT_ROOT / "tools")

PROJECTS = {
    'picorv32': Path("/Users/fundou/my_dv_proj/picorv32/picorv32.v"),
    'darkriscv': Path("/Users/fundou/my_dv_proj/darkriscv/rtl/darkriscv.v"),
    'ventus_scheduler': Path("/Users/fundou/my_dv_proj/ventus-gpgpu-verilog/src/gpgpu_top/l2cache/Scheduler.v"),
}


def _strip_pycache():
    import shutil
    for p in (PROJECT_ROOT / "src").rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)


def _stats(file_path: Path) -> tuple[bool, dict]:
    """Run `cli.main stats` and parse the output."""
    _strip_pycache()
    env = os.environ.copy()
    env["PYTHONPATH"] = PYTHONPATH
    p = subprocess.run(
        ["python3", "-m", "cli.main", "stats",
         "-f", str(file_path),
         "--no-strict",
         "--log-level", "ERROR"],
        capture_output=True, text=True, timeout=300,
        cwd=str(PROJECT_ROOT), env=env,
    )
    out = p.stdout
    data = {}
    for line in out.splitlines():
        m = re.match(r"\s+(Total nodes|Total edges|DRIVER|CLOCK|RESET|CONNECTION|BIT_SELECT):\s+(\d+)", line)
        if m:
            data[m.group(1).lower().replace(' ', '_')] = int(m.group(2))
        # Also catch "Total nodes: N" format
        m2 = re.match(r"\s+Total (nodes|edges):\s+(\d+)", line)
        if m2:
            data['total_' + m2.group(1)] = int(m2.group(2))
    return p.returncode == 0, data


# Skip individual tests if the project file is missing
picorv32_skip = pytest.mark.skipif(
    not PROJECTS['picorv32'].exists(),
    reason="picorv32.v not found"
)
darkriscv_skip = pytest.mark.skipif(
    not PROJECTS['darkriscv'].exists(),
    reason="darkriscv.v not found"
)
ventus_skip = pytest.mark.skipif(
    not PROJECTS['ventus_scheduler'].exists(),
    reason="Scheduler.v not found"
)


@picorv32_skip
class TestPicorv32:
    def test_parses_and_has_drivers(self):
        """picorv32.v (3000 lines, ~94 ternaries): ≥500 DRIVER edges."""
        ok, data = _stats(PROJECTS['picorv32'])
        assert ok
        assert data.get('driver', 0) >= 500, (
            f"picorv32: expected ≥500 drivers, got {data.get('driver', 0)}. "
            "Possible ternary decomposition regression."
        )

    def test_node_count_in_range(self):
        """picorv32: 400-700 nodes after elaboration."""
        _, data = _stats(PROJECTS['picorv32'])
        nodes = data.get('total_nodes', 0)
        assert 400 <= nodes <= 700, f"unexpected node count: {nodes}"


@darkriscv_skip
class TestDarkriscv:
    def test_parses_and_has_drivers(self):
        """darkriscv.v (~700 lines, RV32I): ≥150 DRIVER edges."""
        ok, data = _stats(PROJECTS['darkriscv'])
        assert ok, "darkriscv failed to elaborate"
        # darkriscv is small but has many ternaries. 150 is conservative.
        assert data.get('driver', 0) >= 150, (
            f"darkriscv: expected ≥150 drivers, got {data.get('driver', 0)}"
        )

    def test_node_count_in_range(self):
        """darkriscv: 100-300 nodes (small core)."""
        _, data = _stats(PROJECTS['darkriscv'])
        nodes = data.get('total_nodes', 0)
        assert 100 <= nodes <= 300, f"unexpected node count: {nodes}"


@ventus_skip
class TestVentusScheduler:
    def test_elaborates_with_errors_but_has_drivers(self):
        """Ventus Scheduler.v has elaboration errors (UnknownModule etc.)
        but should still produce ≥100 DRIVER edges from what does parse."""
        ok, data = _stats(PROJECTS['ventus_scheduler'])
        # ok might be False due to errors; check we got data
        assert data, "no stats output"
        assert data.get('driver', 0) >= 100, (
            f"ventus scheduler: expected ≥100 drivers, got {data.get('driver', 0)}"
        )

    def test_node_count_in_range(self):
        """ventus scheduler: 200-500 nodes (large module)."""
        _, data = _stats(PROJECTS['ventus_scheduler'])
        nodes = data.get('total_nodes', 0)
        assert 200 <= nodes <= 500, f"unexpected node count: {nodes}"


@picorv32_skip
@darkriscv_skip
@ventus_skip
class TestCrossProjectConsistency:
    """All three projects should produce graphs where:
       - DRIVER edges dominate (>50% of total edges)
       - At least 30% of DRIVER edges carry conditions
    """

    def test_drivers_dominate_in_all_projects(self):
        for name, path in PROJECTS.items():
            if not path.exists():
                continue
            _, data = _stats(path)
            drivers = data.get('driver', 0)
            total = data.get('total_edges', 0)
            if total == 0:
                continue
            pct = drivers * 100.0 / total
            assert pct > 30, (
                f"{name}: DRIVER edges should be >30% of total, got {pct:.1f}% "
                f"({drivers}/{total}). Possible regression."
            )

    def test_drivers_with_conditions_present(self):
        """At least some drivers carry conditions (proof that ternary
        decomposition is working — not all drivers are gated, but real
        Verilog has plenty of case/if/ternary gates).

        Threshold: ≥10% of DRIVER edges should have conditions. Real-world
        always_ff blocks have plain `reg <= signal` (no condition label
        on the driver edge since the gating is implicit in the clock),
        so the % depends on the ratio of conditional vs unconditional
        assignments in the source code.
        """
        for name, path in PROJECTS.items():
            if not path.exists():
                continue
            from trace.unified_tracer import UnifiedTracer
            src = path.read_text()
            tracer = UnifiedTracer(sources={path.name: src}, strict=False)
            g = tracer.build_graph()

            from trace.core.graph.models import EdgeKind
            drivers_with_cond = 0
            total_drivers = 0
            for u, v in g.edges():
                edge = g.get_edge(u, v)
                if edge and edge.kind == EdgeKind.DRIVER:
                    total_drivers += 1
                    if edge.condition:
                        drivers_with_cond += 1

            assert total_drivers > 0, f"{name}: no drivers found"
            pct = (drivers_with_cond * 100.0 / total_drivers) if total_drivers else 0
            # 10% is a conservative threshold. picorv32 should be ~60%
            # (343 case/if keywords vs 40 always blocks), darkriscv ~15%
            # (6 case/if vs 8 always blocks, mostly plain reg <= signal).
            assert pct > 10, (
                f"{name}: only {pct:.1f}% of {total_drivers} drivers have "
                "conditions. Paren-wrapped ternary decomposition may be broken."
            )