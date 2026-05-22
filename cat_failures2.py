#!/usr/bin/env python3
"""Batch check: for each failing test, determine SV syntax error vs logic error"""
import subprocess, sys

FAILED_FILES = [
    'sim/tests/regression/test_advanced_features2.py',
    'sim/tests/regression/test_bit_select.py',
    'sim/tests/regression/test_bit_select_hierarchical.py',
    'sim/tests/regression/test_bit_select_in_always.py',
    'sim/tests/regression/test_boundary.py',
    'sim/tests/regression/test_case_multi_branch_v2.py',
    'sim/tests/regression/test_complex_inheritance.py',
    'sim/tests/regression/test_constraint_override.py',
    'sim/tests/regression/test_cross_module_tracking.py',
    'sim/tests/regression/test_dot_access_enhanced.py',
    'sim/tests/regression/test_edge_semantics.py',
    'sim/tests/regression/test_initial_fix.py',
    'sim/tests/regression/test_interface_instance.py',
    'sim/tests/regression/test_modport_direction.py',
    'sim/tests/regression/test_replication_fix.py',
    'sim/tests/regression/test_rhs_syntax.py',
    'sim/tests/regression/test_task_function.py',
    'sim/tests/integration/test_concat_and_hierarchy.py',
    'sim/tests/integration/test_graph_diff_health.py',
    'sim/tests/integration/test_negative_cases.py',
    'sim/tests/integration/test_port_reg_detection.py',
]

sv_files = []
logic_files = []

for f in FAILED_FILES:
    res = subprocess.run(
        ['python3', '-m', 'pytest', f, '-v', '--tb=no'],
        capture_output=True, text=True, cwd='/Users/fundou/my_dv_proj/sv_query', timeout=60
    )
    output = res.stdout + res.stderr
    
    has_compile_err = 'CompilationError' in output or 'Elaboration errors' in output
    has_assert_err = 'AssertionError' in output
    
    n_failed = res.stdout.count('FAILED')
    
    if has_compile_err and not has_assert_err:
        sv_files.append((f, n_failed))
    else:
        logic_files.append((f, n_failed))

print(f"SV 语法错误 (CompilationError): {len(sv_files)} 个文件")
for f, n in sv_files:
    print(f"  {f}: {n} tests")

print(f"\n逻辑错误 (AssertionError 等): {len(logic_files)} 个文件")
for f, n in logic_files:
    print(f"  {f}: {n} tests")

print(f"\n总计: {sum(n for _, n in sv_files)} SV语法错误 + {sum(n for _, n in logic_files)} 逻辑错误")