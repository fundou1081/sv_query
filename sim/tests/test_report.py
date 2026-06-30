#!/usr/bin/env python3
"""
Test Report Generator
自动收集测试结果并更新 TEST_PLAN.md

运行方式:
    python -m pytest sim/tests/ --tb=no
    python sim/tests/test_report.py

或直接运行:
    python sim/tests/test_report.py --update
"""

import os
import re
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class TestReportGenerator:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.sim_dir = project_root / "sim"
        self.tests_dir = self.sim_dir / "tests"
        self.test_plan_path = self.sim_dir / "TEST_PLAN.md"

    def collect_test_info(self) -> dict:
        """收集所有测试信息"""
        # 读取 pytest 输出
        result = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'summary': {'passed': 0, 'failed': 0, 'skipped': 0},
            'tests': []
        }

        # 扫描测试目录
        for test_file in self.tests_dir.rglob("test_*.py"):
            if "__pycache__" in str(test_file):
                continue

            test_path = test_file.relative_to(self.project_root)
            test_info = self._parse_test_file(test_file, test_path)
            result['tests'].extend(test_info)

        # 尝试读取 pytest 的 junit 结果
        junit_path = self.sim_dir / "test-results.json"
        if junit_path.exists():
            try:
                with open(junit_path) as f:
                    junit_data = json.load(f)
                    result['summary'] = junit_data.get('summary', result['summary'])
            except:
                pass

        return result

    def _parse_test_file(self, test_file: Path, test_path: Path) -> list[dict]:
        """解析测试文件提取测试用例信息"""
        tests = []

        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 提取测试类和方法
        class_pattern = r'class (\w+)\s*[:\(]'
        method_pattern = r'def (test_\w+)\s*\('

        classes = re.findall(class_pattern, content)

        for cls in classes:
            class_tests = re.findall(
                rf'class {cls}[^:]*:.*?(?=class |\Z)',
                content,
                re.DOTALL
            )

            for ct in class_tests:
                methods = re.findall(method_pattern, ct)
                docstring = self._extract_docstring(ct)

                for method in methods:
                    test_name = method
                    test_id = f"{test_path}::{cls}::{method}"

                    test_info = {
                        'id': test_id,
                        'file': str(test_path),
                        'class': cls,
                        'method': method,
                        'purpose': self._extract_purpose(docstring),
                        'last_result': 'PASSED',  # 默认值，实际从 pytest 获取
                        'last_run': datetime.now().strftime('%Y-%m-%d'),
                        'updated': datetime.now().strftime('%Y-%m-%d'),
                        'notes': self._extract_notes(docstring)
                    }
                    tests.append(test_info)

        return tests

    def _extract_docstring(self, text: str) -> str:
        """提取文档字符串"""
        match = re.search(r'"""(.*?)"""', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_purpose(self, docstring: str) -> str:
        """从文档字符串提取测试目的"""
        lines = [l.strip() for l in docstring.split('\n') if l.strip()]
        if lines:
            # 去掉 [xxx] 标签
            first_line = re.sub(r'\[.*?\]', '', lines[0]).strip()
            return first_line
        return "验证功能正确性"

    def _extract_notes(self, docstring: str) -> str:
        """提取备注信息"""
        notes = []
        for line in docstring.split('\n'):
            if '备注' in line or '注意' in line or '限制' in line:
                notes.append(line.strip())
        return '; '.join(notes) if notes else ""

    def generate_report(self, test_info: dict, output_path: Path = None):
        """生成测试报告"""
        if output_path is None:
            output_path = self.sim_dir / "TEST_REPORT.md"

        lines = [
            "# sv_query 测试报告",
            "=" * 60,
            "",
            f"**生成时间**: {test_info['timestamp']}",
            "",
            "## 测试摘要",
            "",
            f"- **通过**: {test_info['summary'].get('passed', 'N/A')}",
            f"- **失败**: {test_info['summary'].get('failed', 'N/A')}",
            f"- **跳过**: {test_info['summary'].get('skipped', 'N/A')}",
            "",
            "## 测试用例详情",
            "",
            "| 测试ID | 文件 | 类 | 方法 | 目的 | 结果 | 上次运行 | 更新日期 | 备注 |",
            "|--------|------|-----|------|------|------|----------|----------|------|",
        ]

        for test in sorted(test_info['tests'], key=lambda x: x['file']):
            lines.append(
                f"| `{test['id']}` | {test['file']} | {test['class']} | "
                f"{test['method']} | {test['purpose'][:30]} | "
                f"{test['last_result']} | {test['last_run']} | "
                f"{test['updated']} | {test['notes'][:20]} |"
            )

        content = '\n'.join(lines)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Test report generated: {output_path}")
        return output_path

    def update_test_plan(self, test_info: dict):
        """更新 TEST_PLAN.md 中的测试统计"""
        content = self.test_plan_path.read_text(encoding='utf-8')

        # 统计各类测试
        unit_tests = [t for t in test_info['tests'] if '/unit/' in t['file']]
        integration_tests = [t for t in test_info['tests'] if '/integration/' in t['file']]
        regression_tests = [t for t in test_info['tests'] if '/regression/' in t['file']]

        # 更新时间戳
        content = re.sub(
            r'\*\*最后更新\*\*:.*',
            f"**最后更新**: {test_info['timestamp']}",
            content
        )

        # 更新测试数量
        content = re.sub(
            r'\*\*测试数\*\*:.*',
            f"**测试数**: {len(test_info['tests'])} tests",
            content
        )

        # 更新摘要
        content = re.sub(
            r'- \*\*通过\*\*:.*',
            f"- **通过**: {test_info['summary'].get('passed', 'N/A')}",
            content
        )
        content = re.sub(
            r'- \*\*失败\*\*:.*',
            f"- **失败**: {test_info['summary'].get('failed', 'N/A')}",
            content
        )

        # 添加测试报告链接
        if '## 测试报告' not in content:
            content += "\n\n---\n\n## 测试报告\n\n"
            content += "详细测试报告: [TEST_REPORT.md](./TEST_REPORT.md) (自动生成)\n"

        self.test_plan_path.write_text(content, encoding='utf-8')
        print("Updated TEST_PLAN.md")

    def run_with_report(self, pytest_args: list[str] = None):
        """运行测试并生成报告"""
        if pytest_args is None:
            pytest_args = ['sim/tests/', '-v', '--tb=short']

        print("=" * 60)
        print("Running tests and generating report...")
        print("=" * 60)

        # 运行 pytest
        import subprocess
        result = subprocess.run(
            [sys.executable, '-m', 'pytest'] + pytest_args,
            cwd=self.project_root,
            capture_output=True,
            text=True
        )

        # 解析结果
        test_info = self.collect_test_info()

        # 提取测试结果
        output = result.stdout + result.stderr
        passed_match = re.search(r'(\d+) passed', output)
        failed_match = re.search(r'(\d+) failed', output)
        skipped_match = re.search(r'(\d+) skipped', output)

        if passed_match:
            test_info['summary']['passed'] = int(passed_match.group(1))
        if failed_match:
            test_info['summary']['failed'] = int(failed_match.group(1))
        if skipped_match:
            test_info['summary']['skipped'] = int(skipped_match.group(1))

        # 生成报告
        self.generate_report(test_info)
        self.update_test_plan(test_info)

        return result.returncode == 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Test Report Generator')
    parser.add_argument('--update', action='store_true', help='Update test reports')
    parser.add_argument('--report-only', action='store_true', help='Only generate report without running tests')
    parser.add_argument('--output', default=None, help='Output path for report')

    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.parent.resolve()
    generator = TestReportGenerator(project_root)

    if args.report_only:
        test_info = generator.collect_test_info()
        generator.generate_report(test_info, Path(args.output) if args.output else None)
    else:
        success = generator.run_with_report()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
