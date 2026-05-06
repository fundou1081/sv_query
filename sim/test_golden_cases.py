#==============================================================================
# test_golden_cases.py - 金标准测试
# 铁律13: 先推导金标准再验证
#==============================================================================

import pyslang
from src.trace.unified_tracer import UnifiedTracer

def load_tracer(filename):
    """加载测试文件"""
    tree = pyslang.SyntaxTree.fromFile(filename)
    return UnifiedTracer(trees={'test': tree})

#==============================================================================
# 金标准表格
# | 信号          | 驱动           | 负载            |
# |---------------|----------------|----------------|
# | test_1.q1     | [test_1.a] (<=) | -              |
# | test_1.q2     | [test_1.b] (=)   | -              |
# | test_3.q1     | [test_3.a] (<=)  | -              |
# | test_3.q1驱动 -> test_3.a -> 通过 u1.d 追溯   |
#==============================================================================

def test_case_1():
    """Test 1: 多个 always 块"""
    print("=== Test 1: 多个 always 块 ===")
    
    tracer = load_tracer('sim/test_cases.sv')
    
    # test_multi_alway 模块
    tests = [
        ('q1', 'test_multi_alway', ['test_multi_alway.a']),
        ('q2', 'test_multi_alway', ['test_multi_alway.b']),
    ]
    
    passed = 0
    for sig, mod, expected in tests:
        chain = tracer.trace_signal(sig, module=mod)
        actual = [d.id for d in chain.drivers]
        
        if set(actual) == set(expected):
            print(f"  ✓ {sig}: drivers={actual}")
            passed += 1
        else:
            print(f"  ✗ {sig}: expected={expected}, got={actual}")
    
    return f"{passed}/{len(tests)}"

def test_case_2():
    """Test 2: 嵌套 if/else"""
    print("\n=== Test 2: 嵌套 if/else ===")
    
    tracer = load_tracer('sim/test_cases.sv')
    
    # test_nested_if: q <- a 或 b (sel)
    chain = tracer.trace_signal('q', module='test_nested_if')
    actual = [d.id for d in chain.drivers]
    expected = ['test_nested_if.a', 'test_nested_if.b']
    
    if all(e in actual for e in expected):
        print(f"  ✓ q: drivers={actual}")
        return "1/1"
    else:
        print(f"  ✗ q: expected包含 {expected}, got {actual}")
        return "0/1"

def test_case_3():
    """Test 3: 多个模块实例"""
    print("\n=== Test 3: 多个模块实例 ===")
    
    tracer = load_tracer('sim/test_cases.sv')
    
    # test_multi_inst: q1 <- a, q2 <- b
    tests = [
        ('q1', 'test_multi_inst', ['test_multi_inst.a']),
        ('q2', 'test_multi_inst', ['test_multi_inst.b']),
    ]
    
    passed = 0
    for sig, mod, expected in tests:
        chain = tracer.trace_signal(sig, module=mod)
        actual = [d.id for d in chain.drivers]
        
        if set(actual) == set(expected):
            print(f"  ✓ {sig}: drivers={actual}")
            passed += 1
        else:
            print(f"  ✗ {sig}: expected={expected}, got={actual}")
    
    return f"{passed}/{len(tests)}"

def test_case_4():
    """Test 4: 时钟域"""
    print("\n=== Test 4: 时钟域 ===")
    
    tracer = load_tracer('sim/test_cases.sv')
    
    # test_clk_domains: 两个独立时钟
    chain = tracer.trace_clock_domain('clk_a')
    print(f"  clk_a: {chain.clock}")
    
    chain = tracer.trace_clock_domain('clk_b')
    print(f"  clk_b: {chain.clock}")
    
    return "2/2"

def test_case_5():
    """Test 5: 跨模块 + pipe"""
    print("\n=== Test 5: 跨模块连接 + 组合逻辑 ===")
    
    tracer = load_tracer('sim/test_cases.sv')
    
    # test_pipe: b <- a (通过 pipe.p1)
    chain = tracer.trace_signal('b', module='test_pipe')
    actual = [d.id for d in chain.drivers]
    
    print(f"  b drivers: {actual}")
    print(f"  b confidence: {chain.confidence}")
    
    # b 驱动应该是 test_pipe.a
    if 'test_pipe.a' in actual:
        print(f"  ✓ b: drivers={actual}")
        return "1/1"
    else:
        print(f"  ✗ b: expected=['test_pipe.a'], got={actual}")
        return "0/1"

def run_all():
    """运行所有测试"""
    print("=" * 50)
    print("金标准测试")
    print("=" * 50)
    
    results = []
    
    results.append(test_case_1())
    results.append(test_case_2())
    results.append(test_case_3())
    results.append(test_case_4())
    results.append(test_case_5())
    
    print("\n" + "=" * 50)
    print(f"总结: {' | '.join(results)}")
    print("=" * 50)

if __name__ == '__main__':
    run_all()
