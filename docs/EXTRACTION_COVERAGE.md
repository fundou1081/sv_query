# sv_query SV 语法抽取覆盖率总表

> **创建日期**: 2026-08-27 23:48
> **维护人**: QClaw Agent + 方豆
> **状态**: 初版
> **来源**: [memory/2026-08-27.md §Phase 1A](../memory/2026-08-27.md) + 实测修正 + 100+ fixtures 盘点
> **关联**: [SV_SYNTAX_MAPPING.md](SV_SYNTAX_MAPPING.md) (SV 语法 → sv_query 节点映射) +
>          [PYSLANG_SEMANTIC_USAGE.md](PYSLANG_SEMANTIC_USAGE.md) (pyslang 11.0 API 用法)

## 📊 总览（实测，2026-08-27）

| 支持度 | 数量 | 含义 |
|---|---:|---|
| ✅ 完整支持 | **18** | 全场景覆盖, 全套 1461 测试 + golden fixture 验证 |
| ⚠️ 部分支持 | **4** | 主路径支持, 边界/限定子场景不生成 driver 边 |
| 🔶 有条件支持 | **2** | GenerateBlockArray 支持, GenerateBlock 单块未处理 |
| ❌ 不支持 | **5** | 显式不识别, 用 silent pass 或 fallback |
| 🔸 已知缺陷 | **4** | 行为存在但不完全, 已记录问题 |
| **总语法类别** | **33** | — |

⚠️ **修正**（2026-08-27 实测）: Phase 1A 原矩阵列了"function 递归可能无限展开" + "alias 方向语义与 SV 规范相反"——**两者均经实测确认为误报**，本表已修正。

## ✅ 完整支持（18 种）

| # | SV 语法 | 主要 fixture | 测试覆盖 | 实现位置 | 备注 |
|---|---|---|---|---|---|
| 1 | `assign` (continuous) | `golden_mini/case_demo.sv` 等 50+ | 全部 `sim/tests/integration/` | `_handle_normal_assign` (driver_extractor.py:1543, 待 Step 4 拆) | 主路径 |
| 2 | `always_ff` | `golden_mini/golden_dataflow_10_function.sv` | `orphan_regression/orphan_01_ternary_in_always_ff.sv` 等 12+ | `_create_always_edges` (driver_extractor.py 待 Step 6 拆) | 含 clock/reset 提取 |
| 3 | `always_comb` | `golden_mini/fixed_point_patterns.sv` | `orphan_regression/orphan_31_always_comb_case_ternary.sv` | 同上 | 同上, **🔸 阻塞/非阻塞无差别** |
| 5 | `wire x = expr;` (顶层) | `golden_mini/case_demo.sv` 等 50+ | 全部集成测试 | `_create_net_decl_edges` (driver_extractor.py 待 Step 3b 拆) | 主路径 |
| 6 | `wire x = expr;` (generate-for 内) | `golden_mini/golden_dataflow_27_generate_loop.sv` | 集成测试 | 同上 | Plan G3 2026-08-27 12:35 引入 |
| 7 | `case` (普通) | `golden_mini/golden_dataflow_17_if_case_mixed.sv` | `orphan_regression/orphan_05_case_many_labels.sv` 等 4+ | `_flatten_case` (driver_extractor.py 待 Step 5 拆) | 不区分 casez/casex |
| 8 | RHS 位选 (`a[7:0]`) | `golden_mini/golden_dataflow_25_array_index.sv` | 全部集成测试 | `_get_signal` (→ _common.py) | 限 5 层嵌套解包装 |
| 9 | LHS 位选 (`y[3:0] = x`) | `golden_mini/concat_*` | `orphan_regression/orphan_*` | `_handle_normal_assign` | 同上 |
| 10 | `{a, b}` 拼接赋值 (RHS) | `golden_mini/calc_chain.sv` | 全部集成测试 | `_handle_concat_assign` (driver_extractor.py 待 Step 4 拆) | Concat 识别 |
| 11 | `{a, b}` 拼接赋值 (LHS) | 同上 | 同上 | 同上 | 同上 |
| 12 | `alias b = a;` | `sim/tests/integration/dataflow_fixtures/` 等 | 集成测试 | `alias_extractor.py` ✅ **已拆 (Step 1+2 commit b6708b5)** | 实测 `refs[0]=target (LHS), refs[1]=source` 是 SV 规范 |
| 13 | `function` 定义 + 调用 | `golden_mini/golden_dataflow_19_function_multi.sv` 等 | 全部集成测试 | `_handle_invocation` (driver_extractor.py 待 Step 7 拆) | SubroutineExpander 不深入函数体 |
| 14 | `task` 定义 + 调用 | 同上 | 同上 | 同上 | 同上 |
| 15 | 三元 `?:` (限 5 层) | `golden_mini/ternary_demo.sv` | `orphan_regression/orphan_*ternary*` 32 个 | `_extract_ternary_condition` + `_handle_normal_assign` | 主路径, **🔸 嵌套限 5 层** |
| 16 | `class` (基础) | `sim/tests/integration/dataflow_fixtures/cva6_alu_pattern.sv` | 集成测试 | semantic_adapter | 仅元数据抽取, 不生成 driver 边 |
| 17 | `parameter` / `localparam` | 全部 fixture | 全部测试 | `_filter_compile_time_signal_names` (driver_extractor.py:367) | **自动过滤为非信号** (Fix F 2026-7-14) |
| 18 | `genvar` + `for` (generate-for) | `golden_mini/golden_dataflow_27_generate_loop.sv` | `case27_1to1_truth` (4 个) | semantic_adapter.get_genvar_context + `_get_signal` 的 ctx 参数 | Plan F1 2026-08-12 引入 |

## ⚠️ 部分支持（4 种）

| # | SV 语法 | 不支持的部分 | 影响 | workaround | 实施建议 |
|---|---|---|---|---|---|
| 19 | `always_latch` | 按普通 `always` 处理, 无 latch 语义 | 推断边可能不准确（latch 应该只在条件不满足时保持) | 用户显式识别 latch 块 | 写 `_is_latch_context` + 条件边 |
| 20 | `reg/logic` array 整数组赋值 (`a = b;` where `a[3:0]`) | ElementSelect 字符串化, 整数组赋值不生成 driver 边 | 数组间 driver 链断 | 用户拆成元素级赋值 | 写 `_handle_array_assign` |
| 21 | `unique case` | 作为普通 case 处理 | 行为正确但丢失 unique 校验提示 | 用户自己保证唯一性 | 写 `unique` modifier 检测 |
| 22 | `priority case` | 同上 | 同上 | 同上 | 同上 |

## 🔶 有条件支持（2 种）

| # | SV 语法 | 支持的 | 不支持的 | workaround |
|---|---|---|---|---|
| 23 | `generate-if` 内 `wire x = expr;` | `get_generate_net_declarations` 只查 GenerateBlockArray（`for`/`case` 展开）| GenerateBlock（`if` 单块）未处理 | 拆 `if` 成 `case` 或加 `_handle_generate_if_wire` |
| 24 | `generate-case` 内 `wire x = expr;` | GenerateBlockArray 支持 | GenerateBlock 单块未处理 | 同上 |

⚠️ **特殊 fixture**: `spec_golden/probe_generate_if_wire.sv` — 测试 `generate-if` 内 wire, 预期"不生成 driver 边"但**不报错**。

## ❌ 不支持（5 种，已独立核验）

| # | SV 语法 | 当前行为 | 触发后果 | 用户应对 |
|---|---|---|---|---|
| 25 | `initial` 块 | `driver_extractor.py` 显式 `pass` (line 3346-3349) | 完全不抽取 | 用 `always_ff` + flag 替代 |
| 26 | `casez` | `_flatten_case` 不区分 casez/casex (line 2971) | casez 的 `?` 通配符当字面量处理 | 用 `case` + 显式 mask |
| 27 | `casex` | 同上 | 同上 | 同上 |
| 28 | `unique case` modifier | `_flatten_case` 无 modifier 识别 | 行为当普通 case | 同 #21 |
| 29 | `priority case` modifier | 同上 | 同上 | 同上 |
| 30 | `{W{1'b1}}` 作为 LHS | `_handle_concat_assign` 只查 `"Concatenation"`, Replication 不识别 | driver 边漏生成 | 用户展开 `{1'b1, 1'b1, ...}` 显式拼接 |

## 🔸 已知缺陷（4 条）

| # | 缺陷 | 位置 | 影响 | 修复优先级 |
|---|---|---|---|---|
| 31 | `always_comb` 阻塞/非阻塞无差别处理 | `_create_always_edges` | `assign_type` 总是 `nonblocking` | 🟡 中（行为正确, 只 metadata 错）|
| 32 | 嵌套三元限制 5 层解包装 | `_handle_normal_assign` (line 2302) | 5 层以上 ternary 解析失败 | 🟢 低（少见）|
| 33 | function 递归展开 | ~~SubroutineExpander 误报~~ | — | ✅ **误报, 已确认不修 (Phase 1A matrix 错误)** |
| — | alias 方向语义 | ~~与 SV 规范相反~~ | — | ✅ **误报, 实测 `refs[0]=target` 是对的** |

## 🔸 已知缺陷补充 (iter_062 测试缺口分析确认)

| # | 缺陷 | 位置 | 状态 (iter_063 修复核实) |
|---|---|---|---|
| 34 | `not inside` 约束表达式不生成节点 | constraint 提取 | 🚫 **pyslang 限制** (not inside → InvalidConstraint, 语义层不解析) |
| 35 | soft / dist :/ 不区分 | constraint 提取 | 🚫 **soft 是 pyslang 限制** (解析成普通 Expression, soft 修饰丢失); dist :/ 可提取 (DistWeight.Kind PerValue/PerRange) 但无消费者, 未建模 |
| 36 | coverpoint/cross 的 `iff` 未建模 | covergroup_extractor | ✅ **已修** (CoverpointInfo/CoverCrossInfo 加 iff 字段 + 提取) |
| 37 | wildcard / transition bins 浅提取 | covergroup_extractor | ✅ **已修** (BinsInfo 加 bin_type: wildcard/transition 识别) |
| 38 | 参数化 covergroup 参数不可用 | pyslang 限制 | 🚫 **pyslang 限制** (bins 内参数编译失败; 参数化实例化 not generic class) |
| 39 | expect / immediate assertion 不识别 | sva_extractor | 🟡 **immediate 已修** (assert/assume/cover 提取 + 消息); **expect 是 pyslang 限制** (expect 关键字语义层丢失, 呈现为空 Property) |
| 40 | 数组索引 DRIVER 边缺失 (确认 #20) | driver_extractor | 🚫 **设计约束** (_common.py:474 仅字面量 selector 产出节点; 动态索引 mem[idx] 有意不产出; 字面索引 mem[0] 正常) |

## 🟢 已确认误报修正（Phase 1A matrix 错误）

### 误报 #1: "alias 方向语义与 SV 规范相反"
- **Phase 1A 原描述**: "`alias a = b` 方向语义与 SV 规范相反（refs[0]=target, refs[1]=source）"
- **实测（2026-08-27 commit 554aee9）**: `alias b = a;` → pyslang `netReferences = [b, a]` → driver_extractor `refs[0]=target(b), refs[1]=source(a)`
- **真相**: SV 规范本身就是这样 —— `alias b = a` 表示 b 是 a 的别名, a→b 是对的
- **结论**: 注释错了 (spec alias 章节), 实测一致. **不修代码, 修 spec**

### 误报 #2: "function 递归可能无限展开"
- **Phase 1A 原描述**: "递归函数可能无限展开（line 3810）"
- **实测（2026-08-27 Bug #4 验证）**: `function automatic f(); f(); endfunction` + 互相递归 `f→g→f`, 30s timeout 内 build 正常, exit=0, 3 nodes / 2 edges
- **真相**: `SubroutineExpander.expand()` 只对当前 call site 一次性提取形参→实参映射 + 条件分支, **不深入函数体重新调用 expand()** —— 设计如此, 而非缺陷
- **结论**: subagent 看到 `_extract_assignments` / `_extract_signals_with_mapping` 等方法名 + 925 行代码, 误判为"会递归展开"。**没有实测过, 以后 subagent 的"潜在 bug"要打问号**
- **决定**: 不修代码, 在 spec 里明确写 "SubroutineExpander 不展开函数体内 call (设计如此)"

## 📊 测试 / Fixture 覆盖率

| 类别 | 数量 | 路径 | 测试函数 |
|---|---:|---|---|
| golden_mini 基础 demo | 7 | `sim/tests/fixtures/golden_mini/*.sv` | 集成测试 |
| golden_dataflow case 系列 | 30+ | `sim/tests/fixtures/golden_mini/golden_dataflow_N_*.sv` | 集成测试 + case27 truth |
| orphan_regression 边缘 case | 32 | `golden_mini/orphan_regression/orphan_01-32_*.sv` | 单元 + 集成 |
| spec_golden 边界 probe | 6 | `sim/tests/fixtures/spec_golden/probe_*.sv` | `test_spec_unsupported_syntax.py` 7 个 |
| 集成 dataflow fixture | 10+ | `sim/tests/integration/dataflow_fixtures/*.sv` | 集成测试 |
| minimal / 其他 | 10+ | `sim/tests/fixtures/minimal_*/` | 集成测试 |
| **总 fixture** | **101** | — | **1461 tests collected** |

## 🔸 已知缺陷补充 (iter_068 测试升级确认)

| # | 缺陷 | 位置 | 备注 |
|---|---|---|---|
| 41 | class 方法体内赋值 (`task reset; addr=0;`) 不生成 DRIVER 边 | class_graph_builder | ✅ **已修** (iter_075: 方法体赋值提取 → 成员 DRIVER 边; 含 id() 复用非确定 bug) |
| 42 | task 调用输出参数不生成 `din→dout` 边 (生成 EmptyArgument 占位边) | driver_extractor | ✅ **已修** (iter_076: flattener 保留 Call 整体 + `_parse_invocation_call` 放行 AssignmentExpression 实参 → 真边 `din→dout`, 占位边消失) |
| 43 | task 多语句体内部赋值不生成边 | driver_extractor | ✅ **已修** (iter_076: 同上, 多语句体内部驱动经 `analyze_task_internal_drivers` 独立映射到各 output 实参; 常量赋值无信号边为正确行为) |
| 44 | DPI 调用站点 (`assign result = add(1,2)`) 不生成 DRIVER 边 | driver_extractor | DPI 函数体不可见 (外部接口, 期望行为) |
| 45 | generate-only 实例化的模块 (无直接实例) get_modules 收集不到端口定义 → CONNECTION 边缺失 | semantic_adapter.get_modules | pyslang semantic 树不保留仅被 generate 实例化的模块定义; 生成模块通常也有直接实例, 故影响有限 (iter_072 实测) |
| 46 | `get_generate_instances` 覆盖率不一致: conditional+loop generate 场景返回 0 (M=2 + G=0) | semantic_adapter.get_generate_instances | iter_056 R2 核实附带发现, 当时承诺"记入已知清单"但未登记 (iter_078 补记); conditional+loop generate 实例可能漏报, 影响 connection_extractor L123/L147 的 generate 实例补集 |

## 🔗 关联文档

- [SV_SYNTAX_MAPPING.md](SV_SYNTAX_MAPPING.md) — SV 语法 → TraceNode/TraceEdge 类型映射 (29 KB)
- [PYSLANG_SEMANTIC_USAGE.md](PYSLANG_SEMANTIC_USAGE.md) — pyslang 11.0 API 在 sv_query 的用法 (16 KB)
- [SIGNAL_GRAPH_SPEC.md](SIGNAL_GRAPH_SPEC.md) — SignalGraph 数据模型 spec (3.6 KB)
- [ARCHITECTURE_REVIEW_2026-08-27.md](ARCHITECTURE_REVIEW_2026-08-27.md) — 架构 review (8.8 KB)
- [ARCHITECTURE_TODOLIST.md](ARCHITECTURE_TODOLIST.md) — 7 项改造任务追踪

## 🔄 状态变更日志

- **2026-09-01** — iter_076: #42/#43 修复 (task 调用站点完整形参映射)。
  - 根因: (a) `_parse_invocation_call` 的 token 过滤器把 AssignmentExpression
    (output 实参, 无 `.symbol`/`.expr`) 当 syntax-tree 杂项跳过; (b) flattener
    把 Call 拆成 output 占位赋值, 丢失 input 实参关联。
  - 修复: flattener 保留 Call 整体; `_parse_invocation_call` 放行 Assignment
    并走 LHS 提取; 命名实参由语义 AST 规范化为位置形式, 无需特判。
  - #44 DPI 为期望行为 (函数体外部不可见), 维持记录不修。
- **2026-08-27 23:48** — 初版, 基于 Phase 1A matrix + 实测修正 + 101 fixture 盘点.
  - 修正 2 个 Phase 1A 误报 (alias 方向 / function 递归)
  - 33 种 SV 语法类别 (18✅ / 4⚠️ / 2🔶 / 5❌ / 4🔸)
  - 101 fixture 路径 + 1461 测试覆盖
  - 下次刷新: 加 driver_extractor 拆分后 (#1 Step 4+) 的"语法→文件"映射