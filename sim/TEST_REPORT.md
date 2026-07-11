# Test Report

Generated: 2026-07-11T08:37:02.526020
Duration: 0.2s

## Results

| Metric | Count |
|--------|-------|
| duration_sec | 0.2 |
| total | 5 |
| passed | 0 |
| failed | 0 |
| errors | 0 |
| skipped | 0 |
| xfailed | 0 |
| xpassed | 0 |
| deselected | 0 |

## Phase 1 POC: portConnections 替代 MIG (2026-07-11)

**目标**: 验证 pyslang native API 能否替代自建 MIG

**位置**: `sim/tests/poc/test_portconn_native_poc.py` (5 tests)

### 实测结果 (darkriscv darksocv)

| 假设 | 结果 |
|------|------|
| topInstances.filter(target) 找目标 | ✅ 找到 (4 top instances, darksocv in them) |
| hierarchicalPath 自动以 target 为前缀 | ✅ **7/7 都是 darksocv.\\*** (无需 rewrite) |
| portConnections 给 clean port mappings | ✅ 19 ports on bridge0.core0 |
| Native walk 比 MIG 快 | ✅ **4.3x** (19ms → 4.5ms) |
| Generate block 自动处理 | ✅ `s_ifaces[0..3]` 等 indexed paths 自动正确 |

### 跨项目验证

| 项目 | 结果 |
|------|------|
| darkriscv (darksocv) | ✅ 7 instances, 4.5ms |
| verilog-axi (axi_crossbar) | ✅ 19 instances (含 generate), namespace 正确 |

### 推翻 MEMORY.md 旧判断

> 旧 (2026-06-25): "hierarchicalPath 还是 pyslang namespace, 仍需 rewrite"
> 
> 新 (实测): Filter by user target → pyslang 自动以 target 为前缀

### 影响

- arch.py namespace rewrite (~50 行) → **可删**
- module_instance_graph.py port_to_internal (~200 行) → **可删**
- 总代码 -250 行
- 性能 4.3x 提升
- 2326 tests 0 regression 预期

### 下一步

**Phase 2** (待方豆批准): 全量实现 (~4-6h)
- 重写 module_instance_graph.py 用 portConnections
- 删 arch.py namespace rewrite
- 重跑所有测试验证

**Commit**: `834d7d9` (POC test file)
