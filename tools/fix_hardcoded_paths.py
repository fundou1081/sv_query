"""fix_hardcoded_paths.py — [P158.12.2] 测试硬编码路径批量修复

策略（pitfalls F-2 / R-022 预防措施）:
  1. 仓库内路径 → Path(__file__).resolve().parents[3] 推导（换机器可跑）;
  2. 外部 openrtl corpus → SVQ_OPENRTL_ROOT 环境变量
     （默认 ~/my_dv_proj/openrtl，本机行为不变）;
  3. 外部 corpus 缺失 → 显式 skip（不假失败），reason 写明环境变量。

每个替换都断言原文存在; 全部完成后 ast 校验语法 + 残留检查。
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

ROOT = Path(".").resolve()

OPENRTL_DEF = (
    "# [P158.12] 外部 corpus 根: 环境变量可覆盖, 缺失时显式 skip (不假失败)\n"
    'OPENRTL_ROOT = Path(os.environ.get("SVQ_OPENRTL_ROOT",\n'
    '                                str(Path.home() / "my_dv_proj" / "openrtl")))'
)

_edits_by_file: dict[str, list[tuple[str, str]]] = {}


def add(f: str, old: str, new: str) -> None:
    pairs = _edits_by_file.setdefault(f, [])
    if (old, new) not in pairs:
        pairs.append((old, new))


# ---------------------------------------------------------------- A. 仓库根推导
for f in [
    "sim/tests/unit/test_fix_widths.py",
    "sim/tests/unit/test_fix_imports.py",
    "sim/tests/unit/test_trace_include_flags.py",
    "sim/tests/unit/test_snapshot_compare_flags.py",
    "sim/tests/unit/test_dataflow_error_hint.py",
    "sim/tests/unit/test_controlflow_mutex.py",
    "sim/tests/unit/test_fix_timescale.py",
    "sim/tests/unit/test_fix_report.py",
    "sim/tests/unit/test_sv_preprocessor.py",
    "sim/tests/unit/test_cli_filelist_parity.py",
    "sim/tests/usage/test_naplespu_filelist.py",
    "sim/tests/usage/test_strict_default_filelist.py",
]:
    add(f, 'Path("/Users/fundou/my_dv_proj/sv_query")',
        "Path(__file__).resolve().parents[3]")
add("sim/tests/usage/test_strict_default_filelist.py",
    'Path("/Users/fundou/my_dv_proj/sv_query").resolve()',
    "Path(__file__).resolve().parents[3]")
add("sim/tests/integration/test_dataflow_else_if_comprehensive.py",
    'PROJ = "/Users/fundou/my_dv_proj/sv_query"',
    'PROJ = str(Path(__file__).resolve().parents[3])')
add("sim/tests/integration/test_dataflow_golden.py",
    'PROJ = "/Users/fundou/my_dv_proj/sv_query"',
    'PROJ = str(Path(__file__).resolve().parents[3])')
add("sim/tests/integration/test_dataflow_else_if_typo.py",
    'PRJ_ROOT = Path("/Users/fundou/my_dv_proj/sv_query")',
    "PRJ_ROOT = Path(__file__).resolve().parents[3]")
add("sim/tests/cli/test_no_swap_reclaim.py",
    'REPO = "/Users/fundou/my_dv_proj/sv_query"',
    'REPO = str(Path(__file__).resolve().parents[3])')
add("sim/tests/poc/test_portconn_native_poc.py",
    'sys.path.insert(0, "/Users/fundou/my_dv_proj/sv_query/src")',
    'sys.path.insert(0, os.path.join(os.path.dirname(__file__),\n'
    '                                "..", "..", "..", "src"))')

# ---------------------------------------------------------------- B. run_cli 内联
add("sim/tests/unit/test_stats_filelist.py",
    "import os\nfrom pathlib import Path\n",
    "import os\nfrom pathlib import Path\n\n"
    'RUN_CLI = str(Path(__file__).resolve().parents[3] / "run_cli.py")  # [P158.12]\n')
add("sim/tests/unit/test_stats_filelist.py",
    '"/Users/fundou/my_dv_proj/sv_query/run_cli.py"',
    "RUN_CLI")

# ---------------------------------------------------------------- C. 仓库内杂项
add("sim/tests/usage/test_dataflow_latency_open_source.py",
    'STRICT_UART_FILELIST = "/Users/fundou/my_dv_proj/sv_query/sim/tests/fixtures/strict_uart/filelist.f"',
    'STRICT_UART_FILELIST = str(Path(__file__).resolve().parents[3]\n'
    '    / "sim/tests/fixtures/strict_uart/filelist.f")')
add("sim/tests/cli/test_cli_f_flag_filelist_routing.py",
    'PICORV32_F = "/Users/fundou/my_dv_proj/sv_query/sim/tests/pyslang_type_fixtures/industrial_filelists/picorv32.f"',
    'PICORV32_F = str(Path(__file__).resolve().parents[3]\n'
    '    / "sim/tests/pyslang_type_fixtures/industrial_filelists/picorv32.f")')

# ---------------------------------------------------------------- D. openrtl 外部
# 常量定义式替换
add("sim/tests/poc/test_portconn_native_poc.py",
    'PROJECT_ROOT = "/Users/fundou/my_dv_proj/openrtl"  # [openrtl 2026-09-02] 开源 RTL 统一移入 openrtl',
    OPENRTL_DEF)
add("sim/tests/unit/test_trace_include_flags.py",
    'SYNC_SV = "/Users/fundou/my_dv_proj/openrtl/NaplesPU/NaplesPU/src/deploy/uart/synchronizer.sv"',
    'SYNC_SV = str(OPENRTL_ROOT / "NaplesPU/NaplesPU/src/deploy/uart/synchronizer.sv")')
add("sim/tests/unit/test_controlflow_mutex.py",
    'SYNC_SV = "/Users/fundou/my_dv_proj/openrtl/NaplesPU/NaplesPU/src/deploy/uart/synchronizer.sv"',
    'SYNC_SV = str(OPENRTL_ROOT / "NaplesPU/NaplesPU/src/deploy/uart/synchronizer.sv")')
add("sim/tests/integration/test_benchmark_picorv32.py",
    'PICO_FILE = "/Users/fundou/my_dv_proj/openrtl/picorv32/picorv32.v"',
    'PICO_FILE = str(OPENRTL_ROOT / "picorv32/picorv32.v")')
add("sim/tests/usage/test_dataflow_controlflow_open_source.py",
    'PICO_FILE = Path("/Users/fundou/my_dv_proj/openrtl/picorv32/picorv32.v")',
    'PICO_FILE = OPENRTL_ROOT / "picorv32/picorv32.v"')
add("sim/tests/cli/test_ventus_viz_validation.py",
    'VENTUS = Path("/Users/fundou/my_dv_proj/openrtl/ventus-gpgpu-verilog")',
    'VENTUS = OPENRTL_ROOT / "ventus-gpgpu-verilog"')
add("sim/tests/regression/test_generate_real_world.py",
    'ZIPCPU_RTL = Path("/Users/fundou/my_dv_proj/openrtl/zipcpu/rtl")',
    'ZIPCPU_RTL = Path(os.environ.get("SVQ_OPENRTL_ROOT",\n'
    '                       str(Path.home() / "my_dv_proj" / "openrtl"))) / "zipcpu/rtl"')
add("sim/tests/usage/test_dataflow_latency_open_source.py",
    'PRIM_ARBITER = "/Users/fundou/my_dv_proj/openrtl/opentitan/hw/ip/prim/rtl/prim_arbiter_tree.sv"',
    'PRIM_ARBITER = str(OPENRTL_ROOT / "opentitan/hw/ip/prim/rtl/prim_arbiter_tree.sv")')
add("sim/tests/usage/test_dataflow_latency_open_source.py",
    'CVA6_FILELIST = "/Users/fundou/my_dv_proj/openrtl/cva6/Flist.ariane"',
    'CVA6_FILELIST = str(OPENRTL_ROOT / "cva6/Flist.ariane")')
add("sim/tests/usage/test_dataflow_latency_open_source.py",
    'DARKRISCV = "/Users/fundou/my_dv_proj/openrtl/darkriscv/rtl/darkriscv.v"',
    'DARKRISCV = str(OPENRTL_ROOT / "darkriscv/rtl/darkriscv.v")')
add("sim/tests/usage/test_dataflow_latency_open_source.py",
    'file_path="/Users/fundou/my_dv_proj/openrtl/opentitan/hw/ip/prim/rtl/prim_fifo_sync.sv")',
    'file_path=str(OPENRTL_ROOT / "opentitan/hw/ip/prim/rtl/prim_fifo_sync.sv"))')
add("sim/tests/unit/test_p3_bugs.py",
    "file_path = '/Users/fundou/my_dv_proj/openrtl/opentitan/hw/ip/uart/rtl/uart_rx.sv'",
    "file_path = str(OPENRTL_ROOT / 'opentitan/hw/ip/uart/rtl/uart_rx.sv')")
add("sim/tests/cli/test_cli_f_flag_filelist_routing.py",
    '"/Users/fundou/my_dv_proj/openrtl/picorv32/picorv32.v"]',
    'str(OPENRTL_ROOT / "picorv32/picorv32.v")]')
add("sim/tests/cli/test_cli_f_flag_filelist_routing.py",
    'f.write("/Users/fundou/my_dv_proj/openrtl/picorv32/picorv32.v\\n")',
    'f.write(str(OPENRTL_ROOT / "picorv32/picorv32.v") + "\\n")')
# conftest: 3 处 openrtl 探测路径
for _rest in [
    '"opentitan/hw/ip/prim/rtl/prim_max_tree.sv"',
    '"NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv"',
    '"picorv32/picorv32.v"',
]:
    add("sim/tests/unit/conftest.py",
        f'"/Users/fundou/my_dv_proj/openrtl/{_rest[1:-1]}"',
        f"str(OPENRTL_ROOT / {_rest})")

# ---------------------------------------------------------------- 执行
changed, failed = [], []
for rel, pairs in sorted(_edits_by_file.items()):
    p = ROOT / rel
    t = p.read_text(encoding="utf-8")
    for old, new in pairs:
        if old not in t:
            failed.append((rel, old[:70]))
            continue
        t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    changed.append(rel)

print(f"changed: {len(changed)} files")
for rel in changed:
    print("  +", rel)
if failed:
    print("FAILED to locate:")
    for rel, old in failed:
        print("  -", rel, "::", old)

# 语法校验
errs = []
for rel in changed:
    try:
        ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    except SyntaxError as e:
        errs.append((rel, str(e)[:80]))
print("syntax errors:", errs or "无")

# 残留检查
r = subprocess.run(["grep", "-rn", "/Users/fundou", "sim/tests/", "--include=*.py"],
                   capture_output=True, text=True, cwd=ROOT)
print("残留硬编码:", r.stdout.count("\n"), "行")
if r.stdout:
    print(r.stdout[:2000])
