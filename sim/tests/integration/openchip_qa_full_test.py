#!/usr/bin/env python3
#==============================================================================
# openchip_qa_full_test.py - OpenChip QA 完整测试脚本 v3
#==============================================================================
# 使用 sv_query 工具对开源芯片项目进行完整测试
# 记录所有结果到指定文件夹

import os
import sys
import json
from datetime import datetime
import pytest

# 添加 src 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer

# 项目列表 - 使用 filelist 方式配置
FILENAME_LIST = [
    {'name': 'clacc', 'path': '~/my_dv_proj/clacc', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'serv', 'path': '~/my_dv_proj/serv', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'cva6', 'path': '~/my_dv_proj/cva6', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'picorv32', 'path': '~/my_dv_proj/picorv32', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'darkriscv', 'path': '~/my_dv_proj/darkriscv', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'neorv32', 'path': '~/my_dv_proj/neorv32', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'zipcpu', 'path': '~/my_dv_proj/zipcpu', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'vortex', 'path': '~/my_dv_proj/vortex', 'description': 'RISC-V GPU', 'file_limit': 50},
    {'name': 'XiangShan', 'path': '~/my_dv_proj/XiangShan', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'riscv', 'path': '~/my_dv_proj/riscv', 'description': 'RISC-V 处理器', 'file_limit': 50},
    {'name': 'riscv-boom', 'path': '~/my_dv_proj/riscv-boom', 'description': 'RISC-V BOOM 处理器', 'file_limit': 50},
    {'name': 'rocket-chip', 'path': '~/my_dv_proj/rocket-chip', 'description': 'RISC-V Rocket 处理器', 'file_limit': 50},
    {'name': 'ProNoC', 'path': '~/my_dv_proj/ProNoC', 'description': 'NoC 路由器', 'file_limit': 50},
]

def find_verilog_files(project_path, extensions=['.v', '.sv']):
    """查找项目中的 Verilog 文件"""
    files = []
    for root, dirs, filenames in os.walk(os.path.expanduser(project_path)):
        # 跳过特定目录
        dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', '__pycache__', 'build', 'sim', 'tools', 'doc']]
        for filename in filenames:
            if any(filename.endswith(ext) for ext in extensions):
                files.append(os.path.join(root, filename))
    return files

def analyze_file(filepath):
    """分析单个文件"""
    result = {
        'file': filepath,
        'modules': [],
        'module_count': 0,
        'instances': [],
        'ports': 0,
        'parameters': 0,
        'issues': []
    }

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        if not content.strip():
            result['issues'].append('empty_file')
            return result

        # 使用 UnifiedTracer 分析文件
        try:
            tracer = UnifiedTracer(sources={'file': content})
            tracer.build_graph()
            graph = tracer.get_graph()
        except Exception as e:
            result['issues'].append(f'parse_error: {str(e)[:50]}')
            return result

        # 获取模块信息
        modules = list(graph.nodes())
        result['module_count'] = len(modules)
        result['modules'] = modules

        # 统计信息
        result['ports'] = len([n for n in modules if 'PORT' in str(graph.get_node(n).kind)])

    except Exception as e:
        result['issues'].append(f'error: {str(e)[:100]}')

    return result

@pytest.mark.parametrize("project", FILENAME_LIST)
def test_project(project, output_dir):
    """测试单个项目"""
    print(f"\n{'='*60}")
    print(f"测试项目: {project['name']} ({project['description']})")
    print(f"{'='*60}")

    project_dir = os.path.join(output_dir, project['name'])
    os.makedirs(project_dir, exist_ok=True)

    # 查找 Verilog 文件
    files = find_verilog_files(project['path'])
    print(f"找到 {len(files)} 个 Verilog 文件")

    results = {
        'project': project['name'],
        'description': project['description'],
        'path': project['path'],
        'total_files': len(files),
        'files': [],
        'summary': {
            'total_modules': 0,
            'total_instances': 0,
            'total_ports': 0,
            'total_parameters': 0,
            'files_with_issues': 0,
            'issue_types': {}
        },
        'timestamp': datetime.now().isoformat()
    }

    # 限制每个项目最多N个文件
    max_files = project.get('file_limit', 50)
    files_to_process = files[:max_files]

    for i, filepath in enumerate(files_to_process):
        if i % 10 == 0:
            print(f"  处理文件 {i+1}/{len(files_to_process)}...")

        file_result = analyze_file(filepath)
        results['files'].append(file_result)

        # 更新汇总
        results['summary']['total_modules'] += file_result.get('module_count', 0)
        results['summary']['total_instances'] += len(file_result.get('instances', []))
        results['summary']['total_ports'] += file_result.get('ports', 0)
        results['summary']['total_parameters'] += file_result.get('parameters', 0)

        if file_result['issues']:
            results['summary']['files_with_issues'] += 1
            for issue in file_result['issues']:
                results['summary']['issue_types'][issue] = \
                    results['summary']['issue_types'].get(issue, 0) + 1

    # 保存结果
    result_file = os.path.join(project_dir, 'result.json')
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)

    # 生成摘要报告
    summary_file = os.path.join(project_dir, 'summary.md')
    with open(summary_file, 'w') as f:
        f.write(f"# {project['name']} 测试报告\n\n")
        f.write("## 项目信息\n\n")
        f.write(f"- 描述: {project['description']}\n")
        f.write(f"- 路径: {project['path']}\n")
        f.write(f"- 测试时间: {results['timestamp']}\n\n")
        f.write("## 测试结果\n\n")
        f.write(f"- 总文件数: {results['total_files']}\n")
        f.write(f"- 分析文件数: {len(results['files'])}\n")
        f.write(f"- 总模块数: {results['summary']['total_modules']}\n")
        f.write(f"- 总实例数: {results['summary']['total_instances']}\n")
        f.write(f"- 总端口数: {results['summary']['total_ports']}\n")
        f.write(f"- 总参数数: {results['summary']['total_parameters']}\n")
        f.write(f"- 有问题的文件: {results['summary']['files_with_issues']}\n\n")

        if results['summary']['issue_types']:
            f.write("## 问题类型\n\n")
            for issue, count in results['summary']['issue_types'].items():
                f.write(f"- {issue}: {count}\n")

        # 列出前5个模块
        if results['files']:
            f.write("\n## 示例模块\n\n")
            for fdata in results['files'][:3]:
                if fdata['modules']:
                    f.write(f"- `{fdata['file']}`: {', '.join(fdata['modules'][:5])}")
                    if len(fdata['modules']) > 5:
                        f.write(f" (+{len(fdata['modules'])-5} more)")
                    f.write("\n")

    print(f"  结果已保存到: {project_dir}")

    # 基本断言 - 文件应该被处理
    if results['total_files'] == 0:
        pytest.skip(f"项目 {project['name']} 未找到 Verilog 文件，跳过")

    assert len(results['files']) > 0, f"项目 {project['name']} 分析文件数为 0"
