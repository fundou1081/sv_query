# sv_query 测试计划 (v3.0)
# =======================

## 测试框架结构

```
sv_query/
├── sim/
│   ├── tests/
│   │   ├── unit/                    # 单元测试
│   │   │   ├── test_pyslang_adapter.py
│   │   │   ├── test_signal_tracer.py
│   │   │   └── test_graph_models.py
│   │   ├── integration/             # 集成测试
│   │   │   ├── test_instance_connection.py
│   │   │   ├── test_instance_hierarchy.py
│   │   │   └── ...
│   │   ├── regression/              # 回归测试
│   │   │   └── ...
│   │   ├── conftest.py             # pytest 配置 (自动生成报告)
│   │   └── test_report.py          # 测试报告生成脚本
│   ├── TEST_PLAN.md                # 本文件
│   └── TEST_REPORT.md              # 自动生成的测试报告
```

## 测试信息格式

每个测试用例应包含以下元数据：

| 字段 | 格式 | 说明 |
|------|------|------|
| 测试目的 | `[目的描述]` | 标注在测试方法 docstring |
| 当前结果 | `PASSED/FAILED/SKIPPED` | 自动从 pytest 获取 |
| 测试时间 | `YYYY-MM-DD HH:MM` | 自动记录 |
| 更新日期 | `YYYY-MM-DD` | 每次测试后更新 |
| 备注 | `备注内容` | 可选 |

## 测试报告生成

### 自动更新 (推荐)

测试报告在每次 `pytest` 运行后自动更新：

```bash
# 运行测试，自动生成报告
python -m pytest sim/tests/ -v

# 报告将保存到: sim/TEST_REPORT.md
```

### 手动生成

```bash
# 仅生成报告
python sim/tests/test_report.py --report-only

# 运行测试并生成报告
python sim/tests/test_report.py --update
```

### 环境变量控制

```bash
# 禁用自动报告生成
SV_QUERY_GENERATE_REPORT=false python -m pytest sim/tests/
```

## 测试统计

| 类型 | 数量 | 状态 |
|------|------|------|
| **最后更新** | - | 自动更新 |

## pytest 配置

`conftest.py` 包含以下钩子：

- `pytest_configure`: 记录测试开始时间
- `pytest_terminal_summary`: 测试结束后自动生成报告

## 测试用例命名规范

- 测试文件: `test_*.py`
- 测试类: `Test*`
- 测试方法: `test_*`

测试方法的 docstring 应包含：
1. 测试目的描述
2. 可选的 `[limit]` 标记表示已知限制
3. 可选的 `[金标准]` 标记表示基准测试

## 自动更新流程

```
pytest 运行 → conftest.py 钩子 → 更新 TEST_REPORT.md → 更新元数据
```

报告包含：
- 测试时间戳
- 通过/失败/跳过统计
- 每个测试的详细结果
