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
