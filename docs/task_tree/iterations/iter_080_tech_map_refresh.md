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

---

## 🔬 追加 (同日): Signal Graph 核心回归集筛选 (方豆 "要挑选哪些 test?")

### 筛选方法

按 signal graph 核心链路 (semantic_adapter → extractors (driver/connection/mig/bit_select)
→ expr_tree → graph_builder → graph models → signal_tracer), 从 TECH_MAP 实测引用中
挑出每项底层技术 ≥1 个直接测试 + 金标准行为文件, 共 39 文件。

### 验证结果

- **38 文件 / 317 测试全绿 / ~19s** (2026-09-01 实测)
- 1 个失败隔离: `integration/test_bitselect_handler_diff.py::test_nested_diff`

### 发现: test_nested_diff 双重纪律问题 (pre-existing)

1. **fixture 非法 SV**: `data[3:0][1:0]` — pyslang strict 拒绝
   (SelectAfterRangeSelect, "cannot chain select expressions after a range select")。
   实测确认 `d[0][1:0]` (element 后 chain) 合法, `d[3:0][1:0]` (range 后 chain) 非法。
   测试意图"多维位选嵌套"应该用 element 嵌套写, fixture 本身是语法错误。
2. **路径 B 用 `strict=False`** (L147) — 违反 AGENTS.md 纪律 #1。
   文件是 iter_035/036 (#2 BitSelect 改造) 时代遗留, 未在 iter_064 纪律升级时清理。

**影响面**: integration 全量 404 passed + 15 failed (pre-existing; iter_058 记录 baseline 13,
现 15 = 含此 diff 相关 + benchmark/human_output/tree_output 等既有), 非本集引入。

**处置建议**: 单独迭代修 fixture (改合法嵌套写法 + 去 strict=False), 不阻塞核心集。

---

## 🔬 追加 (同日): test_nested_diff 修复 (方豆 "对, 修掉")

### 修复内容 (sim/tests/integration/test_bitselect_handler_diff.py)

1. **fixture 修合法**: `data[3:0][1:0]` (非法, range-select 后 chain select)
   → `logic [3:0][7:0] data; slice <= data[0][1:0];` (packed array, element-select
   后 chain — 实测 `d[0][1:0]` strict 编译通过)
2. **去掉 `strict=False`** (路径 B `_build_graph_builder_only` L147) — 恢复默认
   strict=True, 消除纪律 #1 违规
3. 同步更新 test_nested_diff docstring + fixture 注释

### 验证

- 修复后: `test_bitselect_handler_diff` **8 passed**
- **有效性**: revert fixture 为非法 `data[3:0][1:0]` → strict 拒绝
  (SelectAfterRangeSelect) → 测试 FAILED; 恢复 → 8 passed
- ruff: 12 errors 全为 pre-existing (I001 import 排序 / F841 print-only diff /
  W292), stash 前后一致, 修复未引入新 error
- integration 全量: 15 failed → **14** (test_nested_diff 转绿)

### 决策

- F841 (diff 变量未用) 是 print-only 测试设计 (diff 输出供人工 review),
  保留不修 — 不属于本次范围

---

## 🔬 追加 (同日): 完整回归构成 + 覆盖差距 (方豆 "测试太少了, 完整的回归测试包含什么")

### 完整回归 = 6 层全量 (301 文件 / 2997 测试), 已写入 TEST_MAP §0

| 层 | 测试数 | 角色 |
|---|---|---|
| unit | 1095 | 单元 (每提取器/构建器行为) |
| regression | 766 | 语法金标准 (DRIVER/CONSTRAINS 边) |
| integration | 422 | 跨模块端到端 |
| cli | 389 | CLI 命令 subprocess |
| usage | 298 | 真实项目大场景 |
| truth | 22 | 1:1 SVG 断言 |
| poc | 5 | native POC |

**实测**: unit+regression = 1857 passed + 4 沙箱 env 失败 (86s); regression 766 全绿;
integration 404 + 14 pre-existing; cli 385 + 4 沙箱 env。

### 覆盖差距分析 (为什么"感觉测试少")

**语法矩阵 (EXTRACTION_COVERAGE 33 语法 × 5 档) 对照实测**:

| 语法 | 档位 | 直接测试现状 | 结论 |
|---|---|---|---|
| #19 always_latch | ⚠️ 部分 | 仅 integration/test_latch (3 测试) | 🟡 **薄** — 无 unit 级 latch 语义测试 |
| #23/24 generate-if/case wire | 🔶 条件 | integration/test_generate + unit/test_generate_handling (13) | 🟢 可接受 (probe fixture 有) |
| #26/27 casez/casex | ❌ 不支持 | integration/test_case_stmt + spec_unsupported (有) | 🟢 已测不支持语义 |
| #30 replication LHS | ❌ 不支持 | regression/test_replication_fix (3) | 🟢 已测 |

**真正偏薄的点** (有实现但测试少):
1. **regression 语法金标准 vs 语法矩阵**: 33 语法中约一半 (16 种) 是"主路径全覆盖"
   但**无独立 regression 文件** (靠 integration 顺带测) — 例如 assign/always_comb/wire
   顶层/net decl — 缺独立行为断言
2. **integration 14 个 pre-existing 失败** (benchmark/human_output/tree_output) — 不是
   测试少, 是**有测试但挂了** — 需要修而不是补
3. **truth 层仅 22 测试** — case27 SVG 断言覆盖窄, 其他模块无 1:1 truth

### 结论

测试总量不少 (2997), 用户"感觉少"的合理来源:
- 核心回归集 (38 文件 317) 只覆盖 signal graph 链路 → 感觉少 (但那是**快速子集**)
- **完整回归应跑 unit+regression (1857)** 或 6 层全量 (2997)
- 真正缺口: 16 种主路径语法无独立 regression 文件 + integration 14 个挂着的测试 + truth 薄

**候选行动** (等方豆拍板): 补 16 种主路径语法的独立行为断言 regression / 修 integration
14 个 pre-existing / 扩 truth 层。
