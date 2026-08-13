# ruff: noqa: E402
"""
pytest configuration — test markers + auto symlink setup (V6.7)

三类测试 markers:
  golden:     纯 SV fixture，不依赖外部项目，golden 文件对比，快速
  opensource: 依赖真实开源项目 (picorv32, darkriscv, OpenTitan 等)
  slow:       大型设计编译，>30s 每个

运行方式:
  pytest -m golden               # 只跑 golden 测试 (快速，日常开发)
  pytest -m "not opensource"     # 跳过开源项目测试
  pytest -m "not slow"           # 跳过慢测试
"""

import sys
from pathlib import Path

# [FIX 2026-07-30] sys.path MUST be set at module-level (not inside
# pytest_configure hook) so it takes effect before test file collection.
# Python stdlib has a "trace" module that shadows src/trace/.
_PKG_ROOT = Path(__file__).resolve().parents[2]  # sv_query root
_src = str(_PKG_ROOT / "src")
_tools = str(_PKG_ROOT / "tools")
if _src not in sys.path:
    sys.path.insert(0, _src)
if _tools not in sys.path:
    sys.path.insert(0, _tools)

from datetime import datetime  # noqa: E402


def pytest_configure(config):
    """Register markers + auto-create /tmp filelist symlinks."""
    config._test_start_time = datetime.now()

    # markers
    config.addinivalue_line("markers", "golden: pure SV fixture, golden file comparison (fast)")
    config.addinivalue_line("markers", "opensource: depends on external open-source projects")
    config.addinivalue_line("markers", "slow: large design compilation (>30s per test)")
    config.addinivalue_line("markers", "usage: depends on external open-source projects (in sim/tests/usage/)")

    # Auto-create /tmp/*.f symlinks for test filelists
    fixtures_dir = Path(__file__).parent / "fixtures"
    tmp_links = {
        "/tmp/openofdm_tx.f": fixtures_dir / "openofdm_tx" / "filelist.f",
        "/tmp/verilog-axi.f": fixtures_dir / "verilog-axi" / "filelist.f",
        "/tmp/sched.f": fixtures_dir / "scheduler_minimal" / "filelist.f",
    }
    for tmp_path, src_path in tmp_links.items():
        tmp_p = Path(tmp_path)
        if not tmp_p.exists() and src_path.exists():
            try:
                tmp_p.symlink_to(src_path.resolve())
            except (OSError, FileExistsError):
                pass

    # Auto-create /tmp/cdc_test/*.sv symlinks for dataflow integration/usage tests.
    # 这些测试硬编码了 /tmp/cdc_test/<name>.sv 路径, 但真实 fixture 在
    # sim/tests/integration/dataflow_fixtures/ 下 (a7e4f4c fixture-based 重构时
    # 只建了 /tmp/*.f 软链, 漏了 /tmp/cdc_test/ 目录, 导致这批测试空跑失败).
    dataflow_fixtures_dir = Path(__file__).parent / "integration" / "dataflow_fixtures"
    cdc_test_dir = Path("/tmp/cdc_test")
    if dataflow_fixtures_dir.is_dir():
        cdc_test_dir.mkdir(parents=True, exist_ok=True)
        cdc_srcs = {
            "comprehensive.sv", "edge2.sv", "golden_mux5.sv",
            "golden_priority.sv", "nested_not2.sv", "sync_fifo.sv",
            "two_flop_sync.sv", "typo3.sv", "typo4.sv",
        }
        for name in cdc_srcs:
            src = dataflow_fixtures_dir / name
            dst = cdc_test_dir / name
            if src.exists() and not dst.exists():
                try:
                    dst.symlink_to(src.resolve())
                except (OSError, FileExistsError):
                    pass
