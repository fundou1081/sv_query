# sv_query 架构 Review 报告

> **审查日期**: 2026-07-15  
> **审查人**: QClaw Agent  
> **范围**: src/trace/core/* (33 文件, ~12K LOC), docs/, tools/, sim/tests/  
> **触发**: 用户 (方豆) 要求: "重新 review 项目自身的架构，是否有违反设计规则的地方"

---

## 一、违反铁律的发现

### 🔴 高优先级 (违反核心铁律)

#### V1. 铁律4 (模型即契约) + 铁律6 (Schema 宪法) 严重违反
**位置**: `tools/llm_schema.json` 的 EdgeKind enum

**问题**: Schema 把 NodeKind 和 EdgeKind 混在一个 enum 里 (13 个值), 既不覆盖 NodeKind 全部 (17 种), 也不覆盖 EdgeKind 全部 (17 种)。还包含了 `CONTROL`, `UNKNOWN` 两个不在任何 enum 的值。

| Schema 值 | 实际归属 | 状态 |
|----------|---------|------|
| DRIVER, CLOCK, RESET | EdgeKind | ✅ |
| CONNECTION, BIT_SELECT, CONSTRAINS, HAS_* | EdgeKind | ❌ Schema 缺 |
| CONTROL | — | ❌ Schema 多 (无来源) |
| SIGNAL, WIRE, REG, PORT_IN, PORT_OUT | NodeKind | ✅ |
| CONST, PARAM, INSTANTIATED_MODULE | NodeKind | ✅ |
| UNKNOWN | — | ❌ Schema 多 (无来源) |
| PORT_INOUT, GENERATE_BLOCK, CLASS*, CONSTRAINT_* | NodeKind | ❌ Schema 缺 |

**修复**: 删 CONTROL/UNKNOWN, 分 `NodeKind` (25 values) + `EdgeKind` (19 values). commit 841dca4

#### V2. 铁律5 (原子化) 严重违反
**位置**: `src/trace/core/pyslang_adapter.py` (158 行, 12 个方法)

**问题**: 整个文件已 dead code。`base.py:79` 才是 primary PyslangAdapter (93 个方法)。所有 import 的代码 (driver_extractor, graph_builder, connection_extractor 等) 都用 `from .base import PyslangAdapter`。`pyslang_adapter.py` 没有任何外部 import，没有 test 文件引用它 (除了迁移注释)。

**修复**: 删除文件 (158 行), commit d16cd03. 守卫 test_no_pyslang_adapter_legacy 加防 re-introduction

#### V3. 铁律1 (AST 唯一数据源) 违反 ✅ 已修复 (commit 254c75d, 2026-07-15)
**位置**: `src/trace/core/uvm_testbench_extractor.py:63`

**问题**: 在生产代码中直接调用 `pyslang.SyntaxTree.fromText(source)`, 跳过 Compiler。

**修复**: 改用 `Compilation + addSyntaxTree` 入口 (铁律1 允许的统一数据源)。

**附带发现**: SVCompiler 完整 pipeline 对 parameterized UVM 类
(`uvm_driver#(my_transaction)`) 会污染 `token.name.value` 产生 0xfb 非
UTF-8 字节。所以直接用 `Compilation` 而不是 `SVCompiler`。

**回归测试**: `sim/tests/regression/test_v3_iron1_compliance.py` (5 tests)
- `test_no_direct_syntax_tree_from_file`: 静态守卫
- `test_parameterized_uvm_driver_extracted`: parameterized uvm_driver 提取
- `test_parameterized_driver_type_inference`: 推断为 'driver'
- 原有 30 UVM 测试全部通过 (regression/test_uvm_testbench + extractors_negative)

### 🟡 中优先级

#### V4. 铁律31 (消除重复代码) 违反
**位置**: `src/trace/core/driver_extractor.py` (2327 行)

**问题**: 20+ 个 `result.edges.append(TraceEdge(...))` 散布在文件中。已经有 `edge_factory.make_edge()` 工厂模式 (8 处使用), 但绝大多数地方没用。

**修复**: 引入 _append_edge wrapper, 7 处直接 TraceEdge() → 走 factory, commit 1763dcb. condition 也作为 sig_cond 别名

#### V5. 铁律5 (原子化) 违反
**位置**: `src/trace/core/data_models.py` 里 `SignalNode`, `SignalChain` 类

**问题**: `SignalNode` (path, width, is_port, is_reg) 是早期版本的 graph node 抽象, 只有 `pyslang_adapter.py` (已 dead code) 还在用。  
`TraceNode` (id, name, kind, ...) 是 primary, 有 9+ 文件引用。

**修复**: 删除 `SignalNode`, 统一用 `TraceNode`。删除 `SignalChain` (同理)。

#### V6. 铁律33 (基础组件彻底修复) 局部风险
**位置**: `sim/tests/cli/test_ventus_chunk_filelist.py`

**问题**: 注释说 "If 0 instances, that's a known limitation of the small filelist"。虽不是 documented leak 测试, 但措辞与新铁律精神有冲突。

**修复**: 把注释改成 "If 0 instances, the small filelist covers only part of the design, not all"; 删除 "known limitation" 字样。

### 🟢 低优先级 (风格问题, 不违反铁律)

#### V7. 文档过期 (铁律8 弱违反)
**位置**: `docs/CODE_DISCIPLINE_REVIEW.md` (2026-05-23)

**问题**: 报告基于旧 commit `1a60e08`, 没有更新到当前 V2 + 33 文件的状态。后续修复 (Phase 7.4, 7.5, 7.6, Phase 8/Fix F, F.5, F.6) 都没追加 review。

**修复**: 写一份 `docs/CODE_DISCIPLINE_REVIEW_2026-07-15.md`, 评估 V2 + Fix 链。

---

## 二、架构合理性总结

### 合理的分层
- **L1 module 抽取** → `module_extractor.py` + `SemanticAdapter`
- **L2 端口连接** → `connection_extractor.py` + `PyslangAdapter` (base.py)
- **L3 内部信号** → `driver_extractor.py` + `signal_expression_visitor.py` + `load_extractor.py`
- **L4 可视化** → `graph_builder.py` + `graph/signal_graph_viewer.py`

### 合理的 visitor 模式
- `visitors/` 目录 18 个文件
- `BaseVisitor, OperatorVisitor, MemberVisitor, PortVisitor, ...` 多继承
- 装饰器 `_HANDLERS` 派发
- 最近的 `signal_expression_visitor.py` 是 Phase 1b 重构后的 canonical 实现

### 合理的 Cache
- `src/trace/core/cache/` (在 visitors 之外有独立 cache 目录?)

### 不合理/需要重构
1. **pyslang_adapter.py dead code** (V2) ← 最显眼
2. **Schema enum 错** (V1) ← 影响所有 LLM 消费者
3. **uvm_testbench_extractor.py:63 违反铁律1** (V3)
4. **data_models.py 重复抽象** (V5)

---

## 三、强烈推荐下一步

按优先级:

1. **删除 dead code** (V2 + V5): 立刻修复, 低风险, 不影响功能
2. **重写 schema** (V1): 拆分 EdgeKind/NodeKind enum, 让 schema 与代码对齐
3. **修 V3**: uvm_testbench_extractor.py 走 Compiler
4. **扩展 edge factory** (V4): 一次性消除 20+ 重复
5. **更新 doc review** (V7): 与当前状态对齐

不在本次 fix 范围内: 重写 driver_extractor.py 2327 行巨型文件 (需要单独规划)。

---

## 四、附录: 各铁律现状对照

| 铁律 | 状态 | 备注 |
|------|------|------|
| 1 - AST唯一数据源 | ⚠️ | uvm_testbench_extractor.py:63 违规 |
| 2 - 位精确性 | ✅ | |
| 3 - 不可信则不输出 | ✅ | |
| 3.1 - 错误处理禁静默 | ✅ | |
| 4 - 模型即契约 | ⚠️ | Schema 不与代码对齐 (V1) |
| 5 - 原子化 | ⚠️ | dead code (V2), parallel abstractions (V5) |
| 6 - Schema 宪法 | ⚠️ | V1 同上 |
| 7 - 边界测试 | ✅ | |
| 8 - 文档同步 | ⚠️ | 旧 review 未更新 (V7) |
| 10 - 置信度标注 | ✅ | data_models.py 有 |
| 11 - Agent 调用示例 | ✅ | visitor 有 __main__ |
| 13 - 金标准测试 | ✅ | |
| 14 - Syntax 中间层 | ✅ | |
| 15 - Visitor 模式 | ✅ | |
| 16 - 改动前评估 | ✅ | |
| 17 - 强断言 | ✅ | |
| 18 - 负面测试 | ✅ | |
| 19 - RTL 来源 | ✅ | |
| 20 - 全面性 | ✅ | |
| 21 - 双重工具验证 | ✅ | |
| 22 - 具体行为 | ✅ | |
| 23 - Class composition | ✅ | |
| 24 - SUPER_CALL | ✅ | |
| 25 - 多语句 block | ✅ | |
| 26 - Visitor 必用 | ✅ | |
| 27 - 每语法类型 visitor | ✅ | |
| 28 - Visitor 单测 | ✅ | |
| 29 - Graph 重构 fallback | ✅ | |
| 30 - 完整测试套件 | ✅ | |
| 31 - 消除重复 | ⚠️ | V4 |
| 32 - 分阶段 | ✅ | |
| 33 - 基础组件彻底 | ✅ | (Fix F.6 + 纪律已写入) |
