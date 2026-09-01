# Iteration 080: SIGNAL_GRAPH_TECH_TEST_MAP 同步刷新 (实测口径)

**Metadata**:
- **Iteration #**: 080
- **Task Tree Level**: L1
- **Parent Task**: 测试资产梳理 (方豆 "也同步刷新一下")
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (SIGNAL_GRAPH_TECH_TEST_MAP.md 刷新为实测口径)

## 🎯 本次目标

方豆 "也同步刷新一下" — TEST_MAP (iter_079) 重梳后, SIGNAL_GRAPH_TECH_TEST_MAP
(iter_072 创建) 的引用统计还是旧口径 (间接引用含字符串, 如 semantic_adapter 171 文件),
需统一为实测扫描口径。

## 📊 当前状态 / 预期结果

- 旧文档: 各技术引用文件数是 iter_072 快照 (如 2.9 "171 文件引用")
- 预期: python 扫描 301 个测试文件内容, 实测每项技术的引用文件数, 更新全部小节

## 🔬 实际结果

### 1. 实测扫描 (301 测试文件内容引用)

| 底层技术 | 实测引用文件 | 旧值 | 差异原因 |
|---|---|---|---|
| TraceNode/Edge | 61 | 60 | +1 (iter_073+ 新增) |
| DataFlow | 30 | 35 | 旧值含字符串误匹配 |
| SemanticAdapter | 23 | 171 | 旧值口径过宽 (含 `semantic_adapter` 字符串) |
| SignalTracer | 10 | 50 | 旧值含行为测试全量 |
| DriverExtractor | 10 | 17 | 同上 |
| ExprTree | 9 | 10 | — |
| GraphBuilder | 9 | 135 | 旧值含 UnifiedTracer 间接全量 |
| ModuleInstanceGraph | 6 | 9 | — |
| VizData | 4 | 5 | — |
| SignalSource | 2 | — | 新增 |
| BitSelectHandler | 2 | — | 新增 |
| ConnectionExtractor | 1 | — | 新增 |

**口径决策**: 引用文件数 = 内容引用 (import + 符号 + 字符串) 实测; "直接测试" 与
"行为测试" 分开标注, 不再混用旧 "135 文件" 这类间接全量口径。

### 2. 文档更新

- 每个小节: 引用文件数改为实测值 + 直接/行为测试分开列
- 覆盖缺口观察表: 补齐 graph 模型/driver/mig/graph_builder/signal_tracer/expr_tree/
  semantic_adapter 行 (全部 🟢), 明确 "8 项底层技术均有直接或行为覆盖"
- 关键测试集: 新增 connection_extractor / bit_select_handler / class_method /
  task_function (iter_073~076 产物)

## 💡 关键发现 / 决策

1. **旧 "135/171 文件引用" 是间接全量口径, 易误导**: 实际 GraphBuilder 直接 import
   仅 9 文件, SemanticAdapter 内容引用 23 文件。新口径分开直接/行为, 更诚实。
2. **实测扫描脚本可复用**: 301 文件内容扫描 < 10s, 后续 TECH_MAP 刷新应带此脚本。

## 📌 状态

- ✅ SIGNAL_GRAPH_TECH_TEST_MAP.md 刷新完成 (实测口径)
- 提交: docs/SIGNAL_GRAPH_TECH_TEST_MAP.md + 本迭代记录
