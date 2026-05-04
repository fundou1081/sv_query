#!/usr/bin/env python3
"""纪律校验脚本 - 在代码提交时自动检查"""

import subprocess
import sys
import os
import re

def check_regex():
    """检测正则使用（禁止用于SV源码分析）"""
    result = subprocess.run(
        ["grep", "-rn", "re\\.(findall|match|search)", 
         "src/trace/core/", "--include=*.py"],
        capture_output=True, text=True
    )
    violations = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        # 排除日志、CLI参数解析
        if any(x in line for x in ['log', 'cli', '__pycache__', 'test']):
            continue
        if 'sim/' not in line:  # 测试文件允许
            violations.append(line)
    return violations

def check_file_structure():
    """检测文件结构"""
    errors = []
    src_dir = "src/trace"
    
    # 检查深度
    for root, dirs, files in os.walk(src_dir):
        depth = root.replace(src_dir, '').count(os.sep)
        if depth > 3:
            errors.append(f"目录过深: {root}")
    
    return errors

def check_imports():
    """检测禁止的导入"""
    errors = []
    forbidden = ['igraph', 'graphviz']
    
    for root, dirs, files in os.walk('src/trace'):
        for f in files:
            if f.endswith('.py'):
                path = os.path.join(root, f)
                with open(path) as fp:
                    content = fp.read()
                    for lib in forbidden:
                        if f'import {lib}' in content:
                            errors.append(f"禁止导入 {lib} 在 {path}")
    return errors

def main():
    print("检查开发纪律...")
    
    errors = []
    
    # 1. 正则检测
    regex_err = check_regex()
    if regex_err:
        errors.append("正则使用违规 (用于源码分析):")
        errors.extend(regex_err[:5])
    
    # 2. 文件结构
    struct_err = check_file_structure()
    errors.extend(struct_err)
    
    # 3. 禁止导入
    import_err = check_imports()
    errors.extend(import_err)
    
    if errors:
        print("❌ 纪律违规:")
        for e in errors[:10]:
            print(f"  {e}")
        if len(errors) > 10:
            print(f"  ... 还有 {len(errors)-10} 条")
        return 1
    
    print("✅ 纪律校验通过")
    return 0

if __name__ == "__main__":
    sys.exit(main())
