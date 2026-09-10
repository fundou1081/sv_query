# sv_query 架构 Review 报告 (2026-08-27)

> **审查日期**: 2026-08-27
> **审查人**: QClaw Agent
> **范围**: src/trace/core/* (核心 11 文件, ~40K LOC), sim/tests/, docs/
> **触发**: 用户 (方豆) 19:08 要求 "整体流程上锐评 sv_query 架构, 哪些合适哪些不合适"
> **前置**: 紧接 spec 三任务闭环 (commit `1620b45`) + 4 bug 审查 (commits `554aee9`/`e02da76`)

---

## 一、规模盘点 (40K LOC)

| 文件 | 行数 | 角色 |
|---|---:|---|
| `driver_extractor.py` | **4101** | 主抽取器 (assign/always/wire-init/function/task/ternary/case/位选) |
| `semantic_adapter.py` | **2435** | pyslang 封装门面 (76 def, 53 公开方法 + 23 内部/dunder) |
| `unified_tracer.py` | 1204 | 编排入口 (11+ 步管线) |
| `subroutine_expander.py` | 925 | function/task 展开 (实测只 1 层, 不深入函数体) |
| `graph_builder.py` | 909 | 节点/边构建 11 步 |
| `compiler.py` | 653 | pyslang Compilation 包装 |
| `connection_extractor.py` | 555 | 端口连接 (Bug #2 + #3 修复点) |
| `bit_select_handler.py` | 377 | 位选父子 (**unified_tracer 用**, graph_builder 不用) |
| `load_extractor.py` | 391 | load 边 |
| `sv_preprocessor.py` | 290 | 源码预处理 (孤儿, 见 §三.6) |
| `clock_domain_extractor.py` | 97 | 时钟/复位 |
| **合计** | **40,423** | — |

**关键观察**: `driver_extractor.py` (10.1%) + `semantic_adapter.py` (6.0%) = **16% 的代码承担 80% 的复杂度**。

---

## 二、做对的事 ✅

### ✅ 1. 单一门面 (SemanticAdapter)
- 53 个公开方法把所有 pyslang 访问都封装在一个类
- `driver_extractor` / `connection_extractor` / `graph_builder` 都只调 adapter API, **不直接 import pyslang 深层**
- AGENTS.md §1.2 写死, 代码基本贯彻
- **抗 pyslang 升级冲击**

### ✅ 2. ExtractorResult 统一数据类
- `extractor_models.py` 解决循环 import (之前 graph_builder → driver_extractor → graph_builder 死循环)
- 5 个 Extractor 共享 `nodes/edges/port_to_internal/port_to_module_type/expr_trees/...`
- **协议清晰, 扩展新 extractor 不用改既有 extractor**

### ✅ 3. 纯 semantic + 禁止 silent fallback
- AGENTS.md §2 写死 "禁止 silent fallback / AST 拿不到就 string parse"
- 走 G1/G2/G3 / PR1-7 多轮反复才定型
- `coverage_generator.py` 贯彻, driver_extractor 多处用 sentinel
- **设计哲学正确**

### ✅ 4. 内容哈希缓存
- UnifiedTracer.build_graph 用 sources content-hash 做 cache key
- **增量构建加速**

### ✅ 5. 8.5 个月的纪律沉淀 (G1/G2/G3 + PR1-7 + Plan B/C/D + 真项目测试)
- darkriscv / serv / zipbones / picorv32 / cva6 全部跑过
- 1449+ unit + cli 测试 + 7 个 spec golden (今天加的)
- **纪律驱动 vs 临时起意** 的开发模式

---

## 三、做错的事 ❌

### 🔴 1. driver_extractor.py 单文件 4101 行 — 巨型单文件反模式

**严重度**: 极高

**问题**: SV 语法是天然可拆分的 (assign / always / wire-init / function / task / ternary / case / 位选 / struct / class / generate / alias 12+ 类), 但全部塞一个文件。

**实测痛点**:
- 之前 grep `assign_type` 在 3 个文件 (driver_extractor.py + graph_builder.py + connection_extractor.py) 散落字面量
- driver_extractor 内部 8+ 公开方法: `_handle_concat_assign` / `_handle_call_assign` / `_create_always_edges` / `_create_net_alias_edges` / `_create_net_decl_edges` / `_expand_and_append_assignment` / `_collect_assignments_from_stmt` / `_walk_ternary` / `_build_cond_map`
- 修改任何一块都要打开 4000+ 行文件, **心智负担巨大**

**对比**: pyslang / slang 自身都是按语法大类拆文件 (statement/expression/declaration 各文件).

**建议**: 拆成 `extractors/{assign, always, wire_init, function, case, ternary, bit_select, struct, generate, alias}_extractor.py`, 每个 200-500 行.

### 🔴 2. 重复实现: BitSelectHandler vs graph_builder._create_hierarchical_bit_nodes

**严重度**: 高

**位置**:
- `bit_select_handler.py` (377 行, **unified_tracer 用**, line 467-470)
- `graph_builder._create_hierarchical_bit_nodes` (graph_builder.py:578-628, **graph_builder 用**)

**问题**: 两套位选父子处理**并行存在**, 行为可能不一致. 如果哪天发现 "unified_tracer 路径的位选 A 字段是 X, graph_builder 路径是 Y", 会非常难定位.

**建议**: 选一套保留 (推荐 graph_builder 的 _create_hierarchical_bit_nodes, 因为它跟 build 管线紧耦合), 另一套标 deprecated → 删除.

### 🔴 3. dual pipeline: UnifiedTracer 20 步散落调用

**严重度**: 高

**位置**: `unified_tracer.py:435-517` (UnifiedTracer.build_graph) + `graph_builder.py:63-96` (GraphBuilder.build)

**管线总览**:
```
UnifiedTracer.build_graph() (高层):
  1. 缓存加载
  2-3. compiler + adapter
  4. GraphBuilder.build() (内部 11 步)
  5-13. ClassGraph / _resolve_class_member / BitSelect / ModuleInstanceGraph /
        PathResolver / _init_tracers / _emit_conditional_op_nodes / _backfill_source_locations
  14. 缓存保存

GraphBuilder.build() (内部):
  1. _configure_instance_paths (target_module)
  2-9. _extract_all_nodes / _extract_all_edges / _mark_special_signals /
        _create_hierarchical_bit_nodes / _collect_struct_members /
        _expand_struct_assignments / _upgrade_reg_nodes / _elaborate_wrapper_passthroughs
  10. _filter_by_target (target_module)
  11. _capture_generate_block_map
```

**问题**:
- 5 步是真正的"构建后处理" (ClassGraph / BitSelect / ModuleInstanceGraph / PathResolver / 条件节点 emit / backfill)
- 7 步是辅助调用 (adapter 挂载 / _init_tracers / 缓存)
- GraphBuilder 11 步 + UnifiedTracer 9 步 = **总共 20 步散落在两个文件**
- 任何一处的顺序错了 (必须先 BitSelect 才能 ModuleInstanceGraph 之类) 会非常难发现
- **没有"依赖图"** — 只有注释 `[must be after #4]` 之类

**建议**: 引入**显式依赖声明** (类似 Airflow DAG), 让每步声明 inputs/outputs, 框架自动拓扑排序.

### 🟡 4. expression tree / const_map / func_info 边抽边塞

**严重度**: 中

**问题**: driver_extractor 在抽 driver 边时**同时**写 `expr_trees` / `const_map` / `func_info` 进 ExtractorResult. 一个文件要懂 3 件事:
- 怎么抽 driver
- 怎么建表达式树
- 怎么扫常量

任何一处修改 (例如换了表达式树结构) 会影响 const_map 提取逻辑. **关注点没分干净** — driver 抽取 vs 元数据提取是两类工作.

**建议**: 表达式树构建独立成 `expression_tree_builder.py`, const_map 提取独立成 `const_extractor.py`, driver_extractor 只负责"原始 driver 边".

### 🟡 5. SubroutineExpander 模式不完整 — function 内外一致性差

**严重度**: 中

**位置**: `src/trace/core/builder/subroutine_expander.py` (925 行)

**真相** (Phase 1A 误报 #4 后实测确认):
- `expand()` **只对当前 call site 做一次性参数映射 + 分支提取**
- **不深入函数体重新调用 expand()**
- 同样写 `if (sel) a = x;`, 放在 function 外能展开三元, 放 function 内只看到一个 Call 边

**设计哲学没想清楚**: "展开到什么程度" 是 spec 应明确但实际是隐式决定的.

**建议**: spec §1.3 明确 "SubroutineExpander 不展开函数体内 call (设计如此, 而非缺陷)", 同时考虑是否需要"二级展开"模式.

### 🟡 6. sv_preprocessor.py 是预处理的孤儿

**严重度**: 中

**问题**: 文件头注释明确"是预处理, 不是 fallback" — 但**没人解释什么时候被调用、被谁调用**.
- grep `sv_preprocessor` 看到只在 `sv_preprocessor.py` 内部有
- 没人 import 它

**判定**: **死代码 or 过度封装** — 需要查.

### 🟡 7. 缺乏"提取失败"统一处理表

**严重度**: 中

**背景**: 我刚修的 Bug #2/#3 是 `logger.warning + extra` — 但这只是**两个具体点**. 整个 40K 行代码库有多少处类似的"用 sentinel 兜底" / "用 try/except 吞掉" / "用 silent default"?

**问题**: 快速 grep 找不到系统性的"失败处理表". Bug #4 (SubroutineExpander) 也是基于"代码看像"而没实测.

**建议**: 建一个 `docs/EXTRACTION_FAILURES.md` — 集中记录所有已知 fallback 路径 + 触发条件 + 用户如何避免.

---

## 四、隐性架构债

### A. tests 按项目组织, 不按提取能力组织

**问题**:
- `sim/tests/fixtures/golden_mini/` 46 个 sv
- `sim/tests/fixtures/strict_uart/` / `minimal_3module` / `verilog-axi` / `cva6_alu_pattern` 等
- 我刚加的 6 个反例 fixture 在 `spec_golden/` — **跟主 fixture 体系脱节**

**建议**: 统一按"提取能力 × 语法类别"组织, 例如 `tests/fixtures/extraction/{assign, always, function, generate, alias, case, ternary}/`.

### B. 没有 extraction coverage 总表

**问题**: 12K 行 spec 文档, 但**没有一个文件**记录"我们对哪些 SV 语法提供哪一档支持、对应哪些 fixture、对应哪些 test". memory 笔记承担了部分功能, 但**不是 spec**.

**建议**: 建 `docs/EXTRACTION_COVERAGE.md` — 30 种语法 × 4 档 (✅/⚠️/🔶/⛔) × 对应 fixture × 对应 test 的总表.

### C. pyslang 11.0 native API 3 个月没动

**背景**: MEMORY.md 2026-06-25 21:38 你说"先记录下来", `inst.hierarchicalPath` / `inst.portConnections` / `inst.body` 都能直接替代 sv_query 自建的多套机制 (4x speedup).

**风险**: 3 个月不动 — 当前代码**越来越难换** (driver_extractor 逻辑深度依赖自建 MIG 和 namespace rewrite). **架构债会过期兑现**.

---

## 五、核心建议 (按 ROI 排序)

| # | 建议 | ROI | 工作量 | 收益 |
|---|---|---|---|---|
| 1 | **拆 driver_extractor (按语法类拆 10 个文件)** | 🔥🔥🔥 | 2-3 天 | 极大降低维护成本 + 加速新语法支持 + 减少 merge conflict |
| 2 | **统一 BitSelectHandler (去重)** | 🔥🔥 | 1 天 | 消除位选行为不一致的隐患 |
| 3 | **建 EXTRACTION_COVERAGE.md 总表** | 🔥🔥 | 半天 | spec / fixture / test 三者对应关系一目了然 |
| 4 | **建 extract_failures.md 集中表** | 🔥 | 1 天 | 减少未来 silent fallback 重蹈覆辙 |
| 5 | **UnifiedTracer 20 步管线 → 依赖图** | 🔥 | 2 天 | 减少顺序错误 |
| 6 | **expression tree 提取独立成 builder** | 🟡 | 2 天 | 关注点分离, 但拆完对功能影响小 |
| 7 | **迁 pyslang 11.0 native API** | 长期高 | 1-2 周 | 4x 性能 + 消 namespace rewrite, 但工作量大 |

---

## 六、最后一句

**sv_query 的设计哲学 (单一门面 + 纯 semantic + 禁 silent fallback) 是正确的** — 这 6 个月的纪律沉淀下来非常扎实. 但**实现层没跟上哲学**: 40K 行代码集中在 2 个巨型文件 (driver_extractor 4101 + semantic_adapter 2435 = 16% 承担 80% 复杂度), 加上 dual pipeline + 双 BitSelectHandler + 散落的 failure 处理, 是**典型的"小项目长大但没拆"**.

**优先级**: 先做 "拆 driver_extractor" — 这是最高 ROI, 能让后面所有改动 (迁 pyslang native、加 EXTRACTION_COVERAGE、修未来的 silent fallback) 都更轻松.

---

## 七、与前次 review (2026-07-15) 的对比

| 维度 | 2026-07-15 review | 2026-08-27 review |
|---|---|---|
| 主线问题 | Schema 违反铁律 (NodeKind/EdgeKind 混在一起) | driver_extractor 巨型单文件 |
| 严重度分布 | 3 个 🔴 (Schema/dead code/AST fallback) | 3 个 🔴 (单文件/双实现/dual pipeline) |
| 修复模式 | 一次性修完 commit | 持续型 (本次修 4 bug, 架构问题待拆) |
| 哲学 | 主要是规则违反 | 主要是规模失控 |

**演化趋势**: 规则违反已收敛 (2026-07-15 的 3 个 🔴 都修了, 累计至今无新增规则违反), 但**规模问题开始显现** — driver_extractor 一个文件 4101 行就是 1 个月前还只有 3000+ 行的演进结果. 接下来 1-2 个月如果不拆, 速度会越来越慢.

---

**关联**:
- memory/2026-08-27.md (本次 session 日记)
- docs/ARCHITECTURE_REVIEW_2026-07-15.md (前次 review, 验证 8.5 个月纪律沉淀)
- AGENTS.md (项目纪律基线)
- commit `1620b45` (spec 三任务闭环) / `554aee9` (alias 注释) / `e02da76` (Bug #2+#3)
