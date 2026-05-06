# sv_query 测试计划
# =======================

## 测试框架结构

```
sim/
├── tests/
│   ├── __init__.py       # 统一入口 + runner
│   ├── unit/             # 单元测试
│   │   ├── test_*.py     # 每个工具单独测试
│   │   └── README.md
│   ├── integration/      # 集成测试
│   │   ├── test_*.py
│   │   └── README.md
│   └── regression/       # 回归测试
│       ├── test_*.py
│       └── README.md
├── test_cases.sv         # 测试用 SV 代码
└── TEST_PLAN.md          # 本文档
```

## 测试分层

### 1. 单元测试 (Unit Tests)

**目的**: 验证每个工具/模块独立功能

| 测试文件 | 覆盖范围 | 金标准 |
|---------|----------|--------|
| test_signal_tracer.py | trace_signal() API | drivers/loads 正确 |
| test_module_tracer.py | trace_module() API | 模块连接正确 |
| test_clock_domain.py | 时钟域识别 | CDC 检测 |
| test_graph_models.py | 数据模型 | TraceNode/Edge |
| test_pyslang_adapter.py | AST 适配器 | 模块/端口解析 |

### 2. 集成测试 (Integration Tests)

**目的**: 多模块协作 + 完整链路

| 测试文件 | 覆盖范围 | 金标准 |
|---------|----------|--------|
| test_unified_tracer.py | 统一入口 | trace_signal() 完整流程 |
| test_assign_chain.py | assign 链追踪 | din → data → dout |
| test_ff_chain.py | always_ff 链追踪 | d → q 追踪 |

### 3. 回归测试 (Regression Tests)

**目的**: 已知问题验证 + Bug 修复确认

| 测试文件 | 覆盖范围 | 金标准 |
|---------|----------|--------|
| test_issue_edge_no_node.py | Bug #1 修复 | Edge 创建时同时创建 Node |
| test_issue_always_ff.py | Bug #2 修复 | always_ff 赋值提取 |
| test_issue_combo.py | Bug #3 修复 | always_comb 阻塞赋值 |

## 测试运行

```bash
# 统一运行所有测试
PYTHONPATH=src:$PYTHONPATH python sim/tests/

# 或使用 runner
python -c "from sim.tests import run_tests; run_tests()"

# 单独运行
python -c "from sim.tests import run_unit_tests; run_unit_tests()"
```

## 通过标准

- [ ] 单元测试: 100% 通过
- [ ] 集成测试: 100% 通过  
- [ ] 回归测试: 100% 通过

## 维护规则

1. 每个新功能必须先有金标准测试
2. 每个 Bug 修复必须有回归测试
3. 测试失败必须记录到 ISSUE.md
