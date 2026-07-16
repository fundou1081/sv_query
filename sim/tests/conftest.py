"""
pytest configuration for automatic test report generation.

[User 2026-07-09] 不能用 SWAP 来规避 OOM 问题.
The previous 4GB bytearray reclaim trick has been removed. Memory pressure
must be handled by the user (smaller filelists, larger machine, or
explicit OOM errors).
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path




def pytest_configure(config):
    """Store test start time + setup /tmp filelist symlinks."""
    config._test_start_time = datetime.now()

    # [V8 2026-07-16] Auto-create /tmp/*.f symlinks from sim/tests/fixtures/
    # Tests use hardcoded /tmp/openofdm_tx.f, /tmp/verilog-axi.f, /tmp/sched.f paths.
    # Create symlinks so tests can find them, regardless of CWD or env.
    fixtures_dir = Path(__file__).parent / "fixtures"
    tmp_links = {
        "/tmp/openofdm_tx.f": fixtures_dir / "openofdm_tx" / "filelist.f",
        "/tmp/verilog-axi.f": fixtures_dir / "verilog-axi" / "filelist.f",
        "/tmp/sched.f": fixtures_dir / "ventus_scheduler" / "filelist.f",
    }
    for tmp_path, src_path in tmp_links.items():
        tmp_p = Path(tmp_path)
        if not tmp_p.exists() and src_path.exists():
            try:
                tmp_p.symlink_to(src_path.resolve())
            except (OSError, FileExistsError):
                pass  # Best effort



def pytest_collection_modifyitems(config, items):
    """Collect test items for report"""
    pass


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Generate test report after test run"""
    # Only generate report if requested
    if not os.environ.get('SV_QUERY_GENERATE_REPORT', 'true').lower() in ('1', 'true', 'yes'):
        return
    
    duration = (datetime.now() - config._test_start_time).total_seconds()
    
    stats = {
        'duration_sec': round(duration, 1),
        'total': terminalreporter._numcollected,
        'passed': 0,
        'failed': 0,
        'errors': 0,
        'skipped': 0,
        'xfailed': 0,
        'xpassed': 0,
        'deselected': getattr(terminalreporter, '_numdeselected', 0),
    }
    
    for category in ('passed', 'failed', 'error', 'skipped', 'xfailed', 'xpassed'):
        stats[category if category != 'error' else 'errors'] = len(
            getattr(terminalreporter.stats, category, [])
        )
    
    # Find report location
    repo_root = Path(__file__).resolve().parent.parent.parent
    report_path = repo_root / 'sim' / 'TEST_REPORT.md'
    
    # Read existing report if any
    existing = {}
    if report_path.exists():
        try:
            with open(report_path) as f:
                for line in f:
                    if '|' in line and ':' in line:
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 2:
                            existing[parts[0]] = parts[-1]
        except Exception:
            pass
    
    # Generate report
    with open(report_path, 'w') as f:
        f.write(f"# Test Report\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Duration: {stats['duration_sec']}s\n\n")
        f.write("## Results\n\n")
        f.write("| Metric | Count |\n")
        f.write("|--------|-------|\n")
        for k, v in stats.items():
            f.write(f"| {k} | {v} |\n")
