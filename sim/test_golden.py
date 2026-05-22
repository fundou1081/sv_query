#==============================================================================
# test_golden.py - 金标准测试 (sv_query 核心功能)
# 测试设计: data_out = always_ff 时钟驱动 data_in
# 预期结果:
#   - data_out 的驱动: [data_in, 1'b0] (always_ff 非阻塞)
#   - data_in 的负载: [data_out] (always_ff)
#   - data 的驱动: [din] (assign)
#   - din 的负载: [data] (assign)
#==============================================================================
# [铁律7] 金标准测试原则:
# 1. 先推导金标准 - 不看代码，人工分析 RTL 语义
# 2. 明确记录 - 在注释中以表格形式记录
# 3. 对比验证 - 运行被测代码，与金标准逐项对比
# 4. 完全一致才能提交
#==============================================================================

import pyslang
from src.trace.unified_tracer import UnifiedTracer

# 加载测试文件
tree = open('sim/test_simple.sv').read()
tracer = UnifiedTracer(sources={'test_simple.sv': tree})
tracer.build_graph()

# 金标准表格 (Golden Standard)
# | 信号   | 驱动              | 负载              |
# |--------|-------------------|------------------|
# | din    | -                 | [data] (assign) |
# | data   | [din] (assign)    | [dout] (always_ff) |
# | dout   | [data, 1'b0] (<=)| -               |
# 注: 1'b0 是 always_ff 复位值，驱动链追踪时视为常量

tests_passed = 0
tests_failed = 0

def check(name, actual, expected, filter_const=True):
    """[铁律4] 数据字段验证"""
    global tests_passed, tests_failed
    # 过滤常量驱动 (1'b0 类似)
    if filter_const:
        actual = [x for x in actual if not x.endswith('.0')]
    actual_set = set(actual)
    expected_set = set(expected)
    if actual_set == expected_set:
        print(f'✓ {name}')
        tests_passed += 1
    else:
        print(f'✗ {name}')
        tests_failed += 1

# Test 1: din 的负载
# RTL 分析: assign data = din; => data 负载是 din
chain = tracer.trace_signal('din', module='top')
check('din -> loads', 
      [l.id for l in chain.loads],
      ['top.data'])

# Test 2: data 的驱动
# RTL 分析: assign data = din; => data 驱动是 din
chain = tracer.trace_signal('data', module='top')
check('data -> drivers',
      [d.id for d in chain.drivers],
      ['top.din'])

# Test 3: data 的负载
# RTL 分析: always_ff dout <= data; => data 负载是 dout  
chain = tracer.trace_signal('data', module='top')
check('data -> loads',
      [l.id for l in chain.loads],
      ['top.dout'])

# Test 4: dout 的驱动
# RTL 分析: always_ff @(posedge clk) dout <= data; (非阻塞)
#   复位: if (!rst_n) dout <= 1'b0;
#   有效: else if (en) dout <= data;
# 驱动来源: [data, 1'b0]，但 1'b0 是常量，过滤
chain = tracer.trace_signal('dout', module='top')
check('dout -> drivers',
      [d.id for d in chain.drivers],
      ['top.data'])

print()
print(f'Results: {tests_passed} passed, {tests_failed} failed')

# [铁律10] 置信度检查
chain = tracer.trace_signal('dout', module='top')
print(f'Confidence: {chain.confidence}')
assert chain.confidence in ['high', 'medium', 'uncertain'], "缺少置信度标注"
