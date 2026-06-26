"""
pytest configuration for automatic test report generation
"""

import os
import json
from datetime import datetime
from pathlib import Path

def pytest_configure(config):
    """Store test start time"""
    config._test_start_time = datetime.now()

def pytest_collection_modifyitems(config, items):
    """Collect test items for report"""
    pass

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Generate test report after test run"""
    # Only generate report if requested
    if not os.environ.get('SV_QUERY_GENERATE_REPORT', 'true').lower() in ('1', 'true', 'yes'):
        return
    
    project_root = Path(__file__).parent.parent.parent
    report_path = project_root / 'sim' / 'TEST_REPORT.md'
    
    # Collect test results
    summary = terminalreporter.stats
    
    passed = len(summary.get('passed', []))
    failed = len(summary.get('failed', []))
    skipped = len(summary.get('skipped', []))
    
    # Build test details
    test_details = []
    
    for test in summary.get('passed', []):
        test_details.append({
            'id': test.nodeid,
            'result': 'PASSED',
            'duration': getattr(test, 'duration', 0)
        })
    
    for test in summary.get('failed', []):
        test_details.append({
            'id': test.nodeid,
            'result': 'FAILED',
            'duration': getattr(test, 'duration', 0)
        })
    
    for test in summary.get('skipped', []):
        test_details.append({
            'id': test.nodeid,
            'result': 'SKIPPED',
            'duration': 0
        })
    
    # Read existing report to preserve metadata
    existing_metadata = {}
    if report_path.exists():
        content = report_path.read_text()
        # Extract existing metadata section if present
        import re
        meta_match = re.search(r'<!-- METADATA -->(.*?)<!-- /METADATA -->', content, re.DOTALL)
        if meta_match:
            try:
                existing_metadata = json.loads(meta_match.group(1))
            except:
                pass
    
    # Generate report
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report_lines = [
        "# sv_query 测试报告",
        "=" * 60,
        "",
        "<!-- METADATA -->",
        json.dumps({
            'generated': timestamp,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'total': passed + failed + skipped
        }, indent=2),
        "<!-- /METADATA -->",
        "",
        "## 测试摘要",
        "",
        f"- **通过**: {passed}",
        f"- **失败**: {failed}",
        f"- **跳过**: {skipped}",
        f"- **总计**: {passed + failed + skipped}",
        f"- **时间**: {timestamp}",
        "",
        "## 测试结果详情",
        "",
        "| 状态 | 测试ID | 时长(秒) |",
        "|------|--------|----------|",
    ]
    
    for test in test_details:
        status_icon = "✅" if test['result'] == 'PASSED' else ("❌" if test['result'] == 'FAILED' else "⏭️")
        duration = f"{test['duration']:.3f}s" if test['duration'] else "-"
        # Shorten test ID
        short_id = test['id'].replace('sim/tests/', '')
        report_lines.append(f"| {status_icon} | `{short_id}` | {duration} |")
    
    report_lines.extend([
        "",
        "---",
        "*此报告由 pytest 自动生成*",
    ])
    
    report_path.write_text('\n'.join(report_lines))
    
    terminalreporter.write_sep("=", f"Test report saved to: {report_path}")


# ----------------------------------------------------------------------------
# [Bug fix 2026-06-26] Auto-build test filelists
# ----------------------------------------------------------------------------
# 之前: 多个 test 硬编码 /tmp/pulp_axi_xbar.f, /tmp/verilog-axi.f 等, 假设 build
#       output 存在. /tmp 清理后 test fail (pre-existing, ~15 tests affected).
# 现在: pytest_configure() 自动 build (从 source repo 路径).
#       Make test self-contained — 不依赖外部 /tmp/build 状态.

import os as _os
from pathlib import Path as _Path

# Source repo paths (assumption: user has these in /Users/fundou/my_dv_proj/)
_DV_PROJ = _Path(_os.environ.get("DV_PROJ", "/Users/fundou/my_dv_proj"))


def _build_filelist_if_missing(filelist_path, source_paths, include_dirs=None):
    """Build filelist from absolute source paths if not exists.
    Returns True if filelist was created.
    """
    if filelist_path.exists():
        return False
    if not source_paths:
        return False
    if not any(_Path(p).exists() for p in source_paths):
        return False

    content = []
    if include_dirs:
        for d in include_dirs:
            content.append(f"+incdir+{d}")
    for p in source_paths:
        content.append(str(p))

    filelist_path = _Path(filelist_path)
    filelist_path.parent.mkdir(parents=True, exist_ok=True)
    filelist_path.write_text("\n".join(content) + "\n")
    return True


def _auto_build_test_filelists():
    """[Bug fix 2026-06-26] Auto-build missing test filelists from source repos.

    Tests that reference /tmp/*.f need those filelists to exist. Rather than
    expecting manual setup, build them from source paths in /Users/fundou/my_dv_proj/.
    """
    built = []

    # 1. Pulp AXI xbar — for test_visualize_module_golden + test_pr3_mig_fallback
    #    + test_pr4_visualize_l2 + test_cross_module_trace_pulp + test_benchmark_pr5
    # [Bug fix 2026-06-26] Use minimal filelist (axi_xbar + axi_pkg + cf_math_pkg)
    #   Original full pulp_axi_xbar.f (125 sources) triggers pyslang memory issues
    #   on 8GB env. Minimal version has enough context for test targets.
    axi_src = _DV_PROJ / "axi/src"
    cc_src = _DV_PROJ / "cva6/vendor/pulp-platform/common_cells/src"
    if axi_src.exists() and cc_src.exists():
        # Use FULL pulp axi + common_cells for cross-module trace tests
        # (these tests need many modules to be visible)
        minimal_files = sorted([str(p) for p in axi_src.glob("*.sv")]) + \
                        sorted([str(p) for p in cc_src.glob("*.sv")])

        for target in ["/tmp/pulp_axi_xbar.f", "/tmp/pulp_axi_xbar_pr2.f"]:
            if _build_filelist_if_missing(
                _Path(target),
                source_paths=minimal_files,
                include_dirs=[
                    str(_DV_PROJ / "axi/include"),
                    str(cc_src.parent / "include"),
                ],
            ):
                built.append(target)

    # 2. verilog-axi — for test_cross_module_trace (uses /tmp/verilog-axi.f)
    verilog_axi_rtl = _DV_PROJ / "verilog-axi/rtl"
    if verilog_axi_rtl.exists():
        v_files = sorted([str(p) for p in verilog_axi_rtl.glob("*.v")])
        if _build_filelist_if_missing(
            _Path("/tmp/verilog-axi.f"),
            source_paths=v_files,
        ):
            built.append("/tmp/verilog-axi.f")

    # [Bug fix 2026-06-26] Create /tmp/common_cells symlink to vendor pulp-platform
    #   Some tests hardcode "/tmp/common_cells/include" + "/tmp/tech_cells_generic/src/rtl"
    #   Make them work by creating symlinks (or skip if not exists).
    cc_root = _DV_PROJ / "cva6/vendor/pulp-platform/common_cells"
    if cc_root.exists():
        if not _Path("/tmp/common_cells").exists():
            try:
                _Path("/tmp/common_cells").symlink_to(cc_root.resolve())
            except OSError:
                pass

    return built


# [ADD 2026-06-26] Override pytest_configure to also build filelists
_original_pytest_configure = pytest_configure


def pytest_configure(config):
    """[ADD 2026-06-26] Auto-build test filelists + existing report config."""
    _auto_build_test_filelists()
    _original_pytest_configure(config)
