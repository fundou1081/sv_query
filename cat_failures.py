#!/usr/bin/env python3
"""Categorize 66 failing tests: SV syntax error vs logic error"""
import sys, re, subprocess

sys.path.insert(0, '/Users/fundou/my_dv_proj/sv_query/sim/tests')
from sv_compile_check import check_sv_compiles

# Run pytest to get failed test list
result = subprocess.run(
    ['python3', '-m', 'pytest', 
     'sim/tests/regression', 'sim/tests/integration', 'sim/tests/unit',
     '--ignore=sim/tests/cli', '--ignore=sim/tests/integration/openchip_qa_full_test.py',
     '-q', '--tb=no'],
    capture_output=True, text=True, cwd='/Users/fundou/my_dv_proj/sv_query'
)

failed = []
for line in result.stdout.split('\n'):
    if 'FAILED' in line:
        # Parse test path
        m = re.search(r'FAILED (.*?)(?:\s|$)', line)
        if m:
            failed.append(m.group(1))

print(f"Total failed: {len(failed)}")
print()

# Group by test file
by_file = {}
for t in failed:
    parts = t.split('::')
    file = parts[0]
    if file not in by_file:
        by_file[file] = []
    by_file[file].append(t)

# For each test file, detect if the SV fixture has compilation errors
sv_errors = []
logic_errors = []

for file, tests in by_file.items():
    sv_error = None
    logic_error = None
    
    for t in tests[:1]:  # Sample first test of each file
        # Run with verbose to get error
        res = subprocess.run(
            ['python3', '-m', 'pytest', t, '-v', '--tb=line'],
            capture_output=True, text=True, cwd='/Users/fundou/my_dv_proj/sv_query',
            timeout=30
        )
        output = res.stdout + res.stderr
        
        if 'CompilationError' in output or 'Elaboration errors' in output:
            sv_error = True
        elif 'AssertionError' in output or 'assert' in output.lower():
            logic_error = True
    
    if sv_error:
        sv_errors.extend(tests)
    elif logic_error:
        logic_errors.extend(tests)
    else:
        logic_errors.extend(tests)  # Default to logic

print(f"SV syntax errors (fixture 不合规范): {len(sv_errors)}")
print(f"Logic errors (fixture 合规但代码逻辑问题): {len(logic_errors)}")
print()
print("=== SV 语法错误测试 ===")
for t in sorted(set(sv_errors)):
    print(t)
print()
print("=== 逻辑错误测试 ===")
for t in sorted(set(logic_errors)):
    print(t)