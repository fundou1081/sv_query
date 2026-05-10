# 弱断言修复计划

## 概述
- 日期: 2026-05-09
- 状态: 待处理

## 需要加强的测试

### 优先级 HIGH - 边验证缺失

这些测试只检查节点存在，未检查 CLOCK/RESET/DRIVER 边类型：

| 测试 | 文件 | 问题 |
|------|------|------|
| `test_constant_drive` | test_negative_cases.py:188 | 只验证节点存在，未验证 DRIVER 边 |
| `test_clock_oscillator` | test_negative_cases.py:326 | 只验证不崩溃，未验证 CLOCK 自环 |
| `test_two_drivers_conflict` | test_negative_cases.py:335 | 只验证节点存在，未验证多驱动冲突处理 |
| `test_reset_edge_priority` | test_negative_cases.py:345 | 只验证节点存在，未验证 RESET 边 |
| `test_clock_edge_negedge` | test_clock_reset_timing.py:67 | 只验证节点存在，未验证 CLOCK 边 |
| `test_clock_edge_both_edge` | test_clock_reset_timing.py:84 | 只验证不崩溃，未验证双沿边 |
| `test_async_reset_negedge` | test_clock_reset_timing.py:109 | 只验证节点存在，未验证 RESET 边 |
| `test_dual_clock_independent` | test_clock_reset_timing.py:162 | 只验证节点存在，未验证两个独立 CLOCK 边 |
| `test_clock_domain_cdc` | test_clock_reset_timing.py:178 | 只验证节点存在，未验证 CDC 边 |

### 优先级 MEDIUM - 错误处理验证缺失

| 测试 | 文件 | 问题 |
|------|------|------|
| `test_empty_module_no_crash` | test_negative_cases.py:32 | 只验证不崩溃，未验证空 module 的预期行为 |
| `test_empty_always_ff_no_crash` | test_negative_cases.py:46 | 只验证 clk 存在，未验证 empty always_ff 不产生 REG 节点 |
| `test_illegal_assignment_no_crash` | test_negative_cases.py:73 | 只验证不崩溃，未验证非法赋值的处理 |
| `test_fork_join_not_supported` | test_negative_cases.py:86 | 只验证 clk 存在，未验证 fork..join 被跳过 |
| `test_undefined_signal` | test_negative_cases.py:167 | 只验证图构建成功，未验证 undefined_signal 的处理 |
| `test_self_assign` | test_negative_cases.py:177 | 只验证节点存在，未验证自赋值边 |
| `test_delay_control` | test_clock_reset_timing.py:123 | 只验证不崩溃，未验证 #delay 处理 |
| `test_event_control` | test_clock_reset_timing.py:133 | 只验证不崩溃，未验证 @event 处理 |
| `test_wait_control` | test_clock_reset_timing.py:143 | 只验证不崩溃，未验证 wait 处理 |

### 优先级 LOW - 已知限制

| 测试 | 文件 | 问题 | 备注 |
|------|------|------|------|
| `test_array_of_instances` | test_instance_hierarchy.py:165 | 实例数组未展开 | 需要较大架构改动 |

## 加强断言模板

### 边验证示例
```python
# Before (弱断言)
self.assertIn('top.clk', graph.nodes())
self.assertIn('top.q', graph.nodes())

# After (强断言)
self.assertTrue(graph.has_edge('top.clk', 'top.q'),
    "clk -> q should have CLOCK edge")
edge = graph.get_edge('top.clk', 'top.q')
self.assertEqual(edge.kind, EdgeKind.CLOCK)
```

### 错误处理示例
```python
# Before (弱断言)
graph = self._build_graph(source)
self.assertIsNotNone(graph)

# After (强断言)
graph = self._build_graph(source)
self.assertIsNotNone(graph)
# 验证预期行为
if should_have_clock_edge:
    self.assertTrue(graph.has_edge('top.clk', 'top.q'))
```

## 统计

- **总计弱断言测试**: 18 个
- **HIGH 优先级**: 9 个
- **MEDIUM 优先级**: 9 个
- **LOW 优先级**: 1 个 (已知限制)
