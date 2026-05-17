#!/usr/bin/env python3
"""
OpenChip QA Round 4 测试脚本
测试剩余 4 个项目并生成报告
"""

import sys
import os
import logging

logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trace.unified_tracer import UnifiedTracer
import pyslang


def find_sv_files(base_path, max_depth=3, max_files=50):
    """查找 SV/V 文件"""
    files = []
    skip_dirs = {'vendor', 'third_party', 'dv', 'tb', 'test', 'bench', 'sim', 'build', '.git'}
    
    for root, dirs, filenames in os.walk(base_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        depth = root[len(base_path):].count(os.sep)
        if depth >= max_depth:
            dirs[:] = []
            continue
        for f in filenames:
            if f.endswith('.sv') or f.endswith('.v'):
                files.append(os.path.join(root, f))
        if len(files) >= max_files:
            break
    return files


def test_project(name, path, max_files=30):
    """测试单个项目"""
    result = {
        'name': name,
        'path': path,
        'files_found': 0,
        'files_parsed': 0,
        'modules': 0,
        'module_list': [],
        'errors': []
    }
    
    if not os.path.exists(path):
        result['errors'].append(f'路径不存在: {path}')
        return result
    
    files = find_sv_files(path, max_files=max_files)
    result['files_found'] = len(files)
    
    if not files:
        result['errors'].append('未找到 SV/V 文件')
        return result
    
    trees = {}
    for f in files:
        try:
            trees[f] = pyslang.SyntaxTree.fromFile(f)
        except Exception as e:
            result['errors'].append(f'{os.path.basename(f)}: {str(e)[:30]}')
    
    result['files_parsed'] = len(trees)
    
    if not trees:
        return result
    
    try:
        tracer = UnifiedTracer(trees=trees, log_level='ERROR')
        tracer.build_graph()
        adapter = tracer._get_adapter()
        modules = list(adapter.get_modules())
        
        result['modules'] = len(modules)
        result['module_list'] = [
            {
                'name': adapter.get_module_name(m),
                'params': len(adapter.get_module_parameters(m)),
                'ports': len(adapter.get_port_declarations(m))
            }
            for m in modules[:10]
        ]
    except Exception as e:
        result['errors'].append(f'build_graph: {str(e)[:50]}')
    
    return result


def generate_report(results):
    """生成报告"""
    report = []
    report.append("# OpenChip QA Round 4 测试报告")
    report.append("")
    report.append("## 测试概述")
    report.append("")
    report.append("| 项目 | 路径 | 文件(找到/解析) | 模块数 |")
    report.append("|------|------|-----------------|--------|")
    
    for r in results:
        if r:
            status = '✅' if r['files_parsed'] > 0 else '❌'
            report.append(f"| {r['name']} {status} | {r['path']} | {r['files_parsed']}/{r['files_found']} | {r['modules']} |")
    
    report.append("")
    report.append("## 详细结果")
    report.append("")
    
    for r in results:
        if r and r['files_parsed'] > 0:
            report.append(f"### {r['name']}")
            report.append("")
            report.append(f"- 文件: {r['files_parsed']}/{r['files_found']} 解析成功")
            report.append(f"- 模块数: {r['modules']}")
            
            if r['module_list']:
                report.append("")
                report.append("| 模块 | 参数 | 端口 |")
                report.append("|------|------|------|")
                for m in r['module_list']:
                    report.append(f"| {m['name']} | {m['params']} | {m['ports']} |")
            
            if r['errors']:
                report.append("")
                report.append(f"**错误** ({len(r['errors'])}):")
                for e in r['errors'][:5]:
                    report.append(f"- {e}")
            
            report.append("")
    
    return '\n'.join(report)


def main():
    projects = {
        'opentitan': '/Users/fundou/my_dv_proj/opentitan/hw/ip',
        'tiny-gpu': '/Users/fundou/my_dv_proj/tiny-gpu/src',
        'verilog-axi': '/Users/fundou/my_dv_proj/verilog-axi/rtl',
        'verilog-ethernet': '/Users/fundou/my_dv_proj/verilog-ethernet/rtl',
    }
    
    results = []
    
    for name, path in projects.items():
        print(f"测试 {name}...", end=' ')
        sys.stdout.flush()
        result = test_project(name, path)
        results.append(result)
        print(f"完成 ({result['files_parsed']}/{result['files_found']} files, {result['modules']} modules)")
    
    # 生成报告
    report = generate_report(results)
    
    report_path = os.path.join(os.path.dirname(__file__), 'OPENCHIP_QA_ROUND4_REPORT.md')
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n报告已保存到: {report_path}")
    print("\n" + "="*60)
    print(report)
    
    return results


if __name__ == '__main__':
    main()