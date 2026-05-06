#!/usr/bin/env python3
#==============================================================================
# test_gold_comprehensive.py - 金标准测试
# 严格按照铁律13: 先定义金标准再验证
#==============================================================================

import sys
sys.path.insert(0, '.')

import pyslang
from src.trace.unified_tracer import UnifiedTracer

def load_tracer(filename):
    tree = pyslang.SyntaxTree.fromFile(filename)
    return UnifiedTracer(trees={'test': tree})

# 测试矩阵 - 严格按照金标准定义
# | case | signal | module | expected_drivers | expected_loads |
TEST_CASES = [
    # Case 1: 基础组合逻辑
    {"case": "combo_basic", "signal": "data_out", "module": "combo_basic",
     "drivers": ["combo_basic.din"], "loads": []},
    
    # Case 2: 基础时序逻辑
    {"case": "seq_basic", "signal": "q", "module": "seq_basic",
     "drivers": ["seq_basic.d"], "loads": []},
     
    # Case 3: 异步复位
    {"case": "seq_async_rst", "signal": "q", "module": "seq_async_rst",
     "drivers": ["seq_async_rst.d"], "loads": []},
     
    # Case 4: 同步复位
    {"case": "seq_sync_rst", "signal": "q", "module": "seq_sync_rst",
     "drivers": ["seq_sync_rst.d"], "loads": []},
     
    # Case 5: 组合 always
    {"case": "combo_always", "signal": "q", "module": "combo_always",
     "drivers": ["combo_always.a", "combo_always.b"], "loads": []},
     
    # Case 6: 多驱动源 mux
    {"case": "seq_mux", "signal": "q", "module": "seq_mux",
     "drivers": ["seq_mux.a", "seq_mux.b"], "loads": []},
     
    # Case 7: 内部信号
    {"case": "seq_internal", "signal": "q1", "module": "seq_internal",
     "drivers": ["seq_internal.din"], "loads": []},
    {"case": "seq_internal", "signal": "q2", "module": "seq_internal",
     "drivers": ["seq_internal.din"], "loads": []},
     
    # Case 8: 跨模块 - 需要穿透实例
    # {"case": "pipe_top", "signal": "b", "module": "pipe_top",
    #  "drivers": ["pipe_top.a"], "loads": []},
     
    # Case 9: 时钟域
    {"case": "dual_clk", "signal": "qa", "module": "dual_clk",
     "drivers": ["dual_clk.da"], "loads": []},
    {"case": "dual_clk", "signal": "qb", "module": "dual_clk",
     "drivers": ["dual_clk.db"], "loads": []},
]

def run_test(test_case):
    case = test_case["case"]
    signal = test_case["signal"]
    module = test_case["module"]
    expected_drivers = set(test_case["drivers"])
    expected_loads = set(test_case["loads"])
    
    tracer = load_tracer('sim/test_comprehensive.sv')
    
    # 追踪驱动
    chain = tracer.trace_signal(signal, module=module)
    actual_drivers = set([d.id for d in chain.drivers])
    
    # 追踪负载
    chain_loads = tracer.trace_signal(signal, module=module)
    actual_loads = set([l.id for l in chain_loads.loads])
    
    # 比较结果
    drivers_match = (actual_drivers == expected_drivers)
    loads_match = (actual_loads == expected_loads)
    
    return {
        "case": case,
        "signal": signal,
        "module": module,
        "expected_drivers": expected_drivers,
        "actual_drivers": actual_drivers,
        "expected_loads": expected_loads,
        "actual_loads": actual_loads,
        "drivers_pass": drivers_match,
        "loads_pass": loads_match,
        "confidence": chain.confidence
    }

def main():
    print("="*70)
    print("Comprehensive Gold Standard Test")
    print("="*70)
    print()
    
    results = []
    passed = 0
    failed = 0
    
    for tc in TEST_CASES:
        result = run_test(tc)
        results.append(result)
        
        status = "✓" if result["drivers_pass"] else "✗"
        
        print(f"{status} {tc['case']}:{tc['signal']}")
        print(f"    drivers: expected={result['expected_drivers']}, actual={result['actual_drivers']}")
        print(f"    loads: expected={result['expected_loads']}, actual={result['actual_loads']}")
        print(f"    confidence: {result['confidence']}")
        
        if result["drivers_pass"] and result["loads_pass"]:
            passed += 1
        else:
            failed += 1
        print()
    
    print("="*70)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*70)
    
    return passed, failed

if __name__ == '__main__':
    main()
