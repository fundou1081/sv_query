"""
conftest.py — 共享 fixtures 给 type extraction tests.

工业项目 (OpenTitan, NaplesPU, PicoRV32) 在测试机上可能不存在.
用 pytest.skip 让 test 跳过 (而非 fail), 保持 CI 通过.

注意: 这个 conftest 在 sim/tests/unit/ 下, 给同目录的 test_* 共享.
"""
import os
import sys
from pathlib import Path

import pytest

# 让 tests 能 import sv_query 内部 (跟其它 unit test 一致)
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # sim/tests/unit/ → sim/tests/ → sim/ → <root>
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

# Import coverage_gen_demo helper
from coverage_gen_demo import (  # noqa: E402
    _parse_logic_type_str,
    parse_width_from_pyslang,
    parse_width_from_rtl,
)

# =============== 路径常量 ===============
PYSV_TYPE_FIXTURES = PROJECT_ROOT / "sim" / "tests" / "pyslang_type_fixtures"
TYPE_TAXONOMY_SV = PYSV_TYPE_FIXTURES / "type_taxonomy.sv"
INDUSTRIAL_FILELISTS = PYSV_TYPE_FIXTURES / "industrial_filelists"

# =============== Fixtures ===============
@pytest.fixture(scope="module")
def type_taxonomy_sv() -> Path:
    """Comprehensive type taxonomy fixture (25+ type scenarios)."""
    return TYPE_TAXONOMY_SV


@pytest.fixture(scope="module")
def parse_pyslang_width():
    """包装 parse_width_from_pyslang (默认 strict=False 适合非完美 RTL)."""
    def _parse(sig_name, file=None, filelist=None, module_name=None, include_dirs=None):
        return parse_width_from_pyslang(
            sig_name,
            file=file,
            filelist=filelist,
            module_name=module_name,
            include_dirs=include_dirs,
        )
    return _parse


@pytest.fixture(scope="module")
def parse_rtl_width():
    """包装 parse_width_from_rtl (regex fallback)."""
    def _parse(sig_name, paths):
        return parse_width_from_rtl(sig_name, paths)
    return _parse


@pytest.fixture(scope="module")
def parse_logic_type_str():
    return _parse_logic_type_str


# =============== Industrial project availability ===============
def _industrial_available(path: str) -> bool:
    """Check if industrial project file exists on this host."""
    return Path(path).exists() if path else False


@pytest.fixture(scope="class")
def opentitan_prim_max_tree_filelist() -> Path:
    """OpenTitan prim_max_tree filelist (skip if not available)."""
    p = INDUSTRIAL_FILELISTS / "openTitan_prim_max_tree.f"
    if not p.exists() or not _industrial_available("/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_max_tree.sv"):
        pytest.skip(f"OpenTitan not available at {p}")
    return p


@pytest.fixture(scope="class")
def naplespu_logger_filelist() -> Path:
    """NaplesPU npu_core_logger filelist (skip if not available)."""
    p = INDUSTRIAL_FILELISTS / "naplespu_logger.f"
    if not p.exists() or not _industrial_available("/Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv"):
        pytest.skip(f"NaplesPU not available at {p}")
    return p


@pytest.fixture(scope="class")
def picorv32_filelist() -> Path:
    """PicoRV32 filelist (skip if not available)."""
    p = INDUSTRIAL_FILELISTS / "picorv32.f"
    if not p.exists() or not _industrial_available("/Users/fundou/my_dv_proj/picorv32/picorv32.v"):
        pytest.skip(f"PicoRV32 not available at {p}")
    return p
