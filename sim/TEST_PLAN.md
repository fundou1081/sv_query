# sv_query 测试计划 (v2.0)
# =======================

## 测试框架结构

```
sv_query/
├── sim/
│   ├── tests/
│   │   ├── __init__.py           # 统一 runner
│   │   ├── unit/                # 单元测试
│   │   ├── integration/         # 集成测试
│   │   └── regression/          # 回归测试
│   ├── test_cases.sv            # SystemVerilog 测试用例
│   ├── TEST_PLAN.md            # 本文档
```

## 测试分层

### 1. 单元测试 (Unit Tests)

**目的**: 验证每个工具/模块独立功能

| 测试文件 | 覆盖范围 | 状态 |
|---------|----------|------|
| test_graph_models.py | TraceNode/Edge 数据模型 | ✓ 完成 |
| test_signal_tracer.py | trace_signal() API | ✓ 完成 |
| test_pyslang_adapter.py | AST 适配器 | ✓ 完成 |
| test_clock_domain.py | 时钟域识别 | ✓ 完成 |
| **test_procedural_blocks.py** | always_ff/comb/latch | [待补充] |
| **test_expression.py** | 表达式解析 | [待补充] |

### 2. 集成测试 (Integration Tests)

| 测试文件 | 覆盖范围 | 状态 |
|---------|----------|------|
| test_unified_tracer.py | 统一入口 | ✓ 完成 |
| test_assign_chain.py | assign 链追踪 | ✓ 完成 |
| **test_combo_chain.py** | always_comb 链 | [待补充] |
| **test_seq_chain.py** | always_ff 链 | [待补充] |
| **test_branch_chain.py** | if/else 多分支 | [待补充] |
| **test_bit_select.py** | 位选择追踪 | [待补充] |
| **test_module_instance.py** | 跨模块连接 | [待补充] |

### 3. 回归测试 (Regression Tests)

| 测试文件 | 覆盖范围 | 状态 |
|---------|----------|------|
| test_edge_creates_node.py | Edge 创建 Node | ✓ 完成 |
| test_always_ff.py | always_ff 提取 | ✓ 完成 |
| **test_boundary.py** | 边界条件 | [待补充] |

---

## 功能覆盖矩阵

| 功能点 | 单元 | 集成 | 回归 | 状态 |
|--------|------|------|------|------|
| assign 连续赋值 | ✓ | ✓ | - | ✓ |
| always_ff 非阻塞 | ✓ | - | ✓ | △ |
| always_comb 阻塞 | - | - | - | ✗ |
| always_latch | - | - | - | ✗ |
| if/else 分支 | - | - | - | ✗ |
| 位选择 | - | - | - | ✗ |
| 模块实例化 | - | - | - | ✗ |
| 时钟域识别 | ✓ | - | - | △ |
| CDC 检查 | - | - | - | ✗ |
| 向量位宽 | - | - | - | ✗ |
| 端口方向 | - | - | - | ✗ |

---

## 测试运行

```bash
# 全部测试
PYTHONPATH=src:$PYTHONPATH python -m unittest discover -s sim/tests

# 单独运行
PYTHONPATH=src:$PYTHONPATH python -m unittest sim.tests.unit -v
PYTHONPATH=src:$PYTHONPATH python -m unittest sim.tests.integration -v
PYTHONPATH=src:$PYTHONPATH python -m unittest sim.tests.regression -v
```

---

## 通过标准

- [ ] 单元测试: ≥90% 通过
- [ ] 集成测试: ≥80% 通过
- [ ] 回归测试: 100% 通过

---

## 维护规则 (v2.0)

1. 每个新功能**必须**先有金标准测试 + 边界测试
2. 每个 Bug 修复**必须**有回归测试
3. 测试**必须**包含错误输入验证
4. 每周**必须**更新覆盖矩阵
5. CI **必须**运行全部测试

---

## 优先级改进 (P0-P2)

| 优先级 | 功能 | 测试文件 | 状态 |
|--------|------|---------|------|
| **P0** | always_comb 阻塞赋值 | test_combo_chain.py | 待补充 |
| **P0** | if/else 多分支 | test_branch_chain.py | 待补充 |
| **P0** | 位选择追踪 | test_bit_select.py | 待补充 |
| **P1** | 模块实例化 | test_module_instance.py | 待补充 |
| **P1** | always_latch | test_latch.py | 待补充 |
| **P1** | 向量位宽 | test_vector_width.py | 待补充 |
| **P2** | CDC 检查 | test_cdc.py | 待补充 |
| **P2** | 性能基准 | test_performance.py | 待补充 |
