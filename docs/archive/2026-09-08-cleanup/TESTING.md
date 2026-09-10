# 测试指南

> 更新: 2026-07-29
> 测试数: 2958 (97.1% pass)

---

## 测试分类 (V6.7)

| 类别 | marker | 说明 | 速度 | 使用场景 |
|------|--------|------|------|---------|
| **golden** | `-m golden` | 纯 SV fixture + golden 文件对比 | 🚀 快 (30s) | 日常开发，先跑这个 |
| **opensource** | `-m opensource` | 依赖开源项目 (picorv32, OpenTitan 等) | 🐢 慢 (5-15min) | 提交前验证 |
| **普通** | 无 marker | 其余所有测试 | ⚡ 中速 (1-2min) | 日常开发 |

### 快速命令 (按需选择)

```bash
# 日常开发 (golden + 普通, 跳过开源项目)
PYTHONPATH=src python3 -m pytest sim/tests/ -m "not opensource" -q

# 只跑 golden 测试 (最快，30s)
PYTHONPATH=src python3 -m pytest sim/tests/ -m golden -q

# 只跑开源项目验证 (发布前)
PYTHONPATH=src python3 -m pytest sim/tests/ -m opensource -v

# 全量
PYTHONPATH=src python3 -m pytest sim/tests/ -q
```

---

## 测试结构

```
sim/tests/
├── unit/          # ~85 文件, ~1320 tests, 最快 (30s)
├── cli/           # ~47 文件, ~400 tests, 端到端 (1-2min)
├── integration/   # ~54 文件, ~482 tests, 跨模块 (5min)
├── regression/    # ~60 文件, ~713 tests, 工业项目 (15min)
└── poc/           # 1 文件, 5 tests (快速)
```

---

## 快速命令

```bash
# 日常开发 (30s)
cd ~/my_dv_proj/sv_query
PYTHONPATH=src python3 -m pytest sim/tests/unit/ -q

# 提交前 (5min)
PYTHONPATH=src python3 -m pytest sim/tests/unit/ sim/tests/cli/ sim/tests/integration/ -q --tb=short

# 全量 (15-20min, 含 picorv32/OpenTitan/Ventus 等工业项目)
PYTHONPATH=src python3 -m pytest sim/tests/ -q --tb=short

# 单个文件
PYTHONPATH=src python3 -m pytest sim/tests/cli/test_picorv32_validation.py -v

# 单个测试
PYTHONPATH=src python3 -m pytest sim/tests/unit/test_viz_data.py::TestVizDataBasic -v

# 按关键字过滤
PYTHONPATH=src python3 -m pytest sim/tests/ -k "dataflow" -v

# 只跑失败的
PYTHONPATH=src python3 -m pytest sim/tests/ --lf
```

---

## 测试分类

### unit/ — 单元测试 (最快，优先跑)

单文件 SV，验证单个函数或类。适合开发时循环跑。

```bash
PYTHONPATH=src python3 -m pytest sim/tests/unit/ -q  # ~30s
```

**关键测试文件:**
- `test_viz_data.py` — VizData 数据层 (V6.7)
- `test_graph_models.py` — TraceNode/TraceEdge
- `test_signal_normalizer.py` / `test_signal_tracer.py` — 信号归一化与追踪 (V6.9 后 SignalExpressionVisitor 已移除)
- `test_driver_extractor_*.py` — Driver extraction

### cli/ — CLI 端到端测试

运行完整 `run_cli.py` 命令，验证端到端流程。

```bash
PYTHONPATH=src python3 -m pytest sim/tests/cli/ -q  # ~1-2min
```

**关键测试文件:**
- `test_picorv32_validation.py` — picorv32 全量验证 (慢)
- `test_signal_source_bitprecision.py` — SignalSource 位精确 (V6.5)
- `test_known_limitations.py` — 已知限制文档
- `test_visualize_teach_*.py` — 可视化 teach 命令

### integration/ — 集成测试

跨模块追踪、数据流分析、golden 对比。

```bash
PYTHONPATH=src python3 -m pytest sim/tests/integration/ -q  # ~5min
```

### regression/ — 回归测试

大型工业项目编译验证 (OpenTitan, picorv32, CVA6 等)。

```bash
PYTHONPATH=src python3 -m pytest sim/tests/regression/ -q  # ~15min
```

---

## 工业项目依赖

很多回归测试依赖 `~/my_dv_proj/` 下的开源项目(vpicorv32, darkriscv, OpenTitan 等).

- 项目**没装** → `pytest.skip` 自动跳过
- 项目**装了** → 自动跑

CI 跑全套含工业项目。本地没工业项目也能跑 unit + cli。

---

## 已知失败 (55 个，全为既存)

| 模块 | 数量 | 原因 |
|------|------|------|
| test_fix_timescale | 6 | MissingTimeScale 检测差异 |
| test_fix_report | 2 | 报告格式变化 |
| test_deadlock_cli | 1 | naplespu filelist 不存在 |
| test_dataflow_else_if | 36 | 条件表达式比较差异 |
| test_dataflow_else_if_typo | 4 | 同上 |
| test_dataflow_golden | 3 | golden 比较差异 |
| test_ventus_all_viz | 5 | arch/trace/PNG 波动 |

**全部 55 个均为既存问题，与 V6.5-V6.7 改动无关。**

---

## 跑全量的正确方式

```bash
cd ~/my_dv_proj/sv_query

# 方式 1: 全量 (一次跑完, 15-20min)
PYTHONPATH=src python3 -u -m pytest sim/tests/ -q --tb=short

# 方式 2: 分批跑 (并行, 更快)
# Terminal 1: unit + regression
PYTHONPATH=src python3 -u -m pytest sim/tests/unit/ sim/tests/regression/ -q --tb=short > /tmp/pytest_ur.txt

# Terminal 2: cli + integration + poc
PYTHONPATH=src python3 -u -m pytest sim/tests/cli/ sim/tests/integration/ sim/tests/poc/ -q --tb=short > /tmp/pytest_ci.txt

# 方式 3: 只看新失败
PYTHONPATH=src python3 -m pytest sim/tests/ -q --tb=line --lf
```

---

## 内存注意事项

8GB MBA 跑大工业项目会 OOM。pyslang **不会报错，静默失败**。

跑前先回收内存:
```bash
python3 -c "import time; a = bytearray(4 * 1024**3); time.sleep(3); del a"
```

详见 `docs/PYSLANG_MEMORY_ISSUE.md`

---

## CI

GitHub Actions workflow: `.github/workflows/tests.yml`

| Job | 内容 | 时间 |
|-----|------|------|
| unit+cli | sim/tests/unit + sim/tests/cli | ~5min |
| integration | sim/tests/integration | ~8min |
| regression | sim/tests/regression | ~15min |
| benchmark | tools/benchmark | ~5min |
