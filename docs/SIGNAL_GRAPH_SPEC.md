# Signal Graph 输入输出 Spec (SIGNAL_GRAPH_SPEC)

> 创建时间: 2026-08-27
> 状态: 活跃维护
> 目的: **权威定义 SignalGraph 的输入契约（什么 SV → 什么 graph）与输出契约（node/edge 字段、kind、语义）**，消灭散落在代码注释里、无单一权威的现状。
> 任务来源: [task 1] 用户 2026-08-27 13:28 — "signal graph 缺少一个明确的输入输出 spec"

---

## 0. 一句话定义

**SignalGraph** 是 `networkx.DiGraph` 的子类，用**有向图**描述 RTL 硬件设计中**信号之间的驱动/负载/连接关系**。节点 = 信号（或常量/函数/条件分支），边 = 信号如何驱动/影响其他信号。

```
信号 A --DRIVER--> 信号 B --LOAD--> 信号 C
 (driver)          (signal)         (load)
```

---

## 1. 输入契约 (Input Contract)

### 1.1 输入来源

```
SV 源码文件列表 (_sources) + target_module (可选)
        │
        ▼
pyslang Compilation (elaborated, 来自 _get_compiler().get_root())
        │
        ▼
SemanticAdapter(root=Compilation.root, compiler, target_module)
        │  ← 这是 GraphBuilder 的真正输入 "adapter" (PyslangAdapter)
        ▼
GraphBuilder(adapter, target_module)  .build()  →  SignalGraph
```

### 1.2 GraphBuilder 输入参数

| 参数 | 类型 | 契约 |
|------|------|------|
| `adapter` | `PyslangAdapter` | **必填**。封装了 pyslang `Compilation` 的 semantic AST。提供 `get_module_instances()`、`get_net_declarations()`、`get_genvar_context()` 等 API（见任务 2 的 pyslang 使用模式）。GraphBuilder 只通过 adapter 访问 AST，不直接碰 pyslang。 |
| `target_module` | `str \| None` | 可选。设置后，SignalGraph 节点用此作为 root namespace（替代自动检测的 first top instance）。控制实例路径命名。 |

### 1.3 支持的 SV 输入语法（adapter 层契约）

> 2026-08-27 Phase 3 修订: 前版表过于乐观。仅列 ✅ 完整 / ⚠️ 不支持两档，没有反映 🔶 有条件支持 / ⛔ 不支持中间状态。表内所有 ⛔/⚠️/🔶 行均由 [test_spec_unsupported_syntax.py](../../sim/tests/test_spec_unsupported_syntax.py) 实测锁口，fixture 在 [spec_golden/](../../sim/tests/fixtures/spec_golden/)。

| SV 语法 | 处理路径 | 支持级别 |
|---------|---------|---------|
| `assign` (连续赋值) | DriverExtractor `_parse_assign` | ✅ 完整 |
| `always_ff` 过程块 (同步非阻塞) | `_create_always_edges` (升 REG 节点) | ✅ 完整 |
| `always_comb` 过程块 (阻塞/非阻塞 一视同仁) | `_create_always_edges` | ✅ 完整（assign_type 总是 `nonblocking`，不区分 ≤ vs =） |
| `always_latch` 过程块 | `_create_always_edges` (同入口，无 latch 特殊分支) | ⚠️ **部分支持**：latch 语义信息（enable condition）丢失，不升 `REG/latch` 节点 |
| **`initial` 块** | `_collect_assignments_from_stmt` 但 line 3346-3349 显式 `pass` | ⛔ **不支持**：probe_initial.sv 实测 3 节点/2 DRIVER（仅来自 always_ff，initial q=1'b0 不产生任何边） |
| 模块端口连接 (port mapping) | ConnectionExtractor | ✅ 完整 |
| generate-for 内 wire 声明 (`wire prod = data*weights[i]`) | `get_generate_net_declarations` (G3) | ✅ 完整 (G3, 2026-08-27) |
| **generate-if/case 内 wire 声明** | 同上（`get_generate_net_declarations` 只查 `GenerateBlockArray`） | 🔶 **有条件支持**：必须用 hierarchical name (`g_label.prod`) 访问；裸名裸体范围内不可见 → build 丢 driver 边。probe_generate_if_wire.sv 实测：assign 依赖 `g_use1.prod1` 才能 elaboration 成功 |
| generate block 展开 (per-iteration) | `hierarchicalPath` 区分 + `_gen_iter_map` | ✅ 完整 (G1/G2/G3) |
| 三元条件 `? :` | OP_TERNARY 节点 (emit, Plan B) | ✅ 完整（嵌套限 5 层解包装） |
| **`casez (sel)` / `casex (sel)`** | `_flatten_case`（line 2971 把 `Case`/`PatternCase` 同等处理） | ⛔ **不支持**：通配符 `?`/`x`/`z` 语义**丢失**，按普通 case 展开。probe_casez.sv/probe_casex.sv 实测与 case 完全一致 |
| **`unique case (sel)` / `priority case (sel)`** | `unique`/`priority` 修饰符被 strip | ⛔ **不支持**：仅产生 `[CaseRedundantDefault]` warning，unique/priority 语义（冲突检测、并行优先级）**全无**。probe_unique_case.sv 实测确认 |
| case 语句（普通） | OP_CASE 节点 (emit, Plan B) | ✅ 完整 |
| 位选/部分选 `a[msb:lsb]` | BitSelectHandler + BIT_SELECT 边 | ✅ 完整 |
| 函数调用 | SubroutineExpander + FUNCTION_CALL | ⚠️ **部分支持**：递归可能无限展开（line 3810） |
| class / constraint | ClassGraphBuilder (子图) | ✅ 完整 |
| struct 赋值 | `_expand_struct_assignments` | ✅ 完整 |
| 常量 `{W{1'b1}}` (concatenation + replication) | semantic 展开 | ✅ (G3 验证) |
| **`{W{1'b1}}` 作为 LHS** | **SV 标准不允许** | ⛔ **SV 规范禁止**（不是 driver_extractor 锅）：elaboration error `expression is not allowed as a statement`。RHS replication (`{3{q}}`) 则**正常**生成 DRIVER 边 |
| **非标准部分选 `acc[N][?:0]`** | pyslang 标为 `InvalidExpression` | ⚠️ 明确不支持 |

**图中符号**: ✅ 完整 / ⚠️ 部分（有缺陷） / 🔶 有条件（部分场景下不准） / ⛔ 不支持（spec 不应谎称支持）

### 1.4 输入边界（什么 NOT 进 graph）

- **非标准 / 非法 SV 语法**（如 `acc[N][?:0]`）会被 pyslang semantic 标为 `InvalidExpression`，其驱动边**被跳过**（G3 决定：改 fixture 而非为非法语法做兜底）。
- **`initial` 块**：代码 line 3346-3349 显式 `pass`，不产生任何边（Phase 1A matrix + #5 实测确认）。
- **`casez`/`casex`/`unique case`/`priority case`**：按普通 case 展开，通配符/修饰符语义静默丢失（Phase 1A matrix + #14-16 实测确认）。
- cross-module 内部原语信号（utility cell）默认不过滤，需按 target_module 过滤（consume PR1-7 的 `_filter_by_target`）。

---

## 2. 输出契约 (Output Contract)

### 2.1 数据容器

`SignalGraph` (models.py:300, 继承 `nx.DiGraph`) 私有字段：

| 字段 | 类型 | 语义 |
|------|------|------|
| `_node_data` | `dict[str, TraceNode]` | node_id → TraceNode（节点的权威存储） |
| `_edge_data` | `dict[tuple[str,str], list[TraceEdge]]` | (src,dst) → 边列表（支持多边，不同 condition） |
| `_port_to_internal` | `dict[str, str]` | 实例端口路径 → 内部信号 id |
| `_port_to_module_type` | `dict[str, str]` | 实例端口 → `<module_type>.<port>` 短名 |
| `_expr_trees` | `dict[str, dict]` | dst_key → 结构化表达式树（driver_extractor 构建） |
| `_const_map` | `dict[str, list]` | dst_short → 常量字符串列表 |
| `_func_info` | `dict[str, tuple\|None]` | 函数名 → (msb, lsb) |
| `_gen_block_map` | `dict[str, str]` | dst_signal_short → GenerateBlockArray.name（真实 label） |
| `_gen_iter_map` | `dict[str, int]` | dst_short → per-element generate entry_idx |

### 2.2 NodeKind 枚举 (models.py:88)

| 分组 | Kind | 语义 |
|------|------|------|
| 核心硬件 | `SIGNAL` | 普通信号 |
| | `WIRE` | wire |
| | `REG` | reg / 触发器输出 |
| | `PORT_IN` / `PORT_OUT` / `PORT_INOUT` | 模块端口方向 |
| | `CONST` | 常量（含字面量, 自动创建） |
| 架构 | `PARAM` | parameter |
| | `INSTANTIATED_MODULE` | 实例节点 (top.inst) |
| | `GENERATE_BLOCK` | generate 块节点 (top.GEN) |
| Class/Constraint | `CLASS`, `CLASS_INSTANCE`, `CLASS_INSTANCE_PROPERTY`, `CLASS_PROPERTY`, `CONSTRAINT_BLOCK`, `CONSTRAINT_EXPR`, `CONSTRAINT_IF`, `CONSTRAINT_ELSE`, `CONSTRAINT_IMPLIES`, `CONSTRAINT_UNIQUE`, `CONSTRAINT_SOLVE`, `CONSTRAINT_FOREACH`, `CONSTRAINT_RANGE` | class/constraint 图节点 |
| 实验 | `EXPRESSION`, `FUNCTION_CALL` | 表达式函数节点 |
| 条件分支 | `OP_TERNARY` (name=`?: (sel)`), `OP_CASE` (name=`case (sel)`) | 三目/case 节点 (2026-08-21) |

### 2.3 EdgeKind 枚举 (models.py:129)

| 分组 | Kind | 语义 |
|------|------|------|
| 核心硬件 | `DRIVER` | 数据驱动 (q <= d) |
| | `CLOCK` | 时钟触发 (clk -> q) |
| | `RESET` | 异步复位 (rst_n -> q) |
| | `CONNECTION` | 模块端口连接 |
| | `BIT_SELECT` | 位选择聚合 |
| Class/Constraint | `CONSTRAINS`, `HAS_CONDITION`, `HAS_CONSEQUENT`, `HAS_ALTERNATE`, `HAS_LHS`, `HAS_RHS`, `HAS_MEMBER`, `HAS_LOOP_VAR`, `HAS_BEFORE`, `HAS_AFTER`, `CONTAINS_MEMBER`, `IS_INSTANCE_OF`, `SUPER_CALL`, `MEMBER_SELECT` | class/constraint 图关系 |
| 条件分支 | `BRANCH_CONDITION`, `BRANCH_TRUE`, `BRANCH_FALSE`, `BRANCH_RESULT` | 三元条件边 |
| | `CASE_SELECT`, `CASE_ITEM`, `CASE_RESULT` | case 边 |

> ⚠️ 铁律16: `ENABLE`/`DATA` **不作为独立边类型** — ENABLE 用 `condition` 属性表达，DATA 与 DRIVER 重复。

### 2.4 TraceNode 字段 (models.py:170)

| 字段 | 类型 | 语义 |
|------|------|------|
| `id` | `str` | 节点唯一 id（含完整路径, 如 `top.u_dut.clk` 或 generate `generate_loop.gen_accum[0].prod`） |
| `name` | `str` | 短名（不带 module 前缀） |
| `module` | `str` | 所在模块 |
| `kind` | `NodeKind` | 节点类型 |
| `width` | `tuple[int,int]` | (msb, lsb) 位宽 |
| `bit_range` | `str\|None` | 位选范围字符串, 如 `[8:1]` |
| `file` / `line` | `str/int` | 源码位置（--show-source 用） |
| `is_clock` / `is_reset` / `is_enable` / `is_port` | `bool` | 特殊信号标记 |
| `parent` | `str\|None` | 父节点 id（位选 → 完整信号） |
| `parent_bit_start` / `parent_bit_end` | `int\|None` | 位选在父节点中的起止位 |
| `modport_dir` | `str\|None` | modport 方向 (input/output/inout) |
| `extra` | `dict` | 任意扩展 metadata (向后兼容) |

### 2.5 TraceEdge 字段 (models.py:193)

| 字段 | 类型 | 语义 |
|------|------|------|
| `src` / `dst` | `str` | 源/目标节点 id |
| `kind` | `EdgeKind` | 边类型 |
| `assign_type` | `str` | always_ff/always_comb/continuous/blocking/nonblocking |
| `condition` | `str` | 驱动条件 |
| `effective_condition` | `str` | 清除扰动后的条件 |
| `condition_ast` | `Any` | 条件表达式 AST (semantic) |
| `clock_domain` | `str` | 时钟域 |
| `modport_dir` | `str\|None` | modport 方向 |
| `confidence` | `str` | high/low |
| `expression` | `str` | 驱动表达式 (如 `a + b`) |
| `bit_slice` | `str` | 位选择 |
| `source_location` | `SourceLocation` | 源码位置 |
| `function_return` | `bool` | 是否函数返回值 |
| `is_function_call` | `bool` | 是否函数调用边 |
| `source` | `SignalSource` | 结构化信号源 (V6.6, driver/load 共享) |
| `condition_chain` | `list[str]` | 嵌套条件累积链 (V7.0, AND 语义) |
| `extra` | `dict` | 扩展 metadata |

### 2.6 DriverInfo (models.py:222)

驱动信息 dataclass：`node`(驱动节点), `source`, `condition`, `expression_tree`(结构化 AST), `reset_condition`, `clock_domain`, `assign_type`, `distance`(驱动距离), `target_signal`。`expression`/`bit_slice` 是 @property 从 `source` 派生。`full_statement()` 组装完整驱动语句(debug 用)。

---

## 3. 构建流程 (Pipeline)

### 3.1 两层管线 (分层归属修正, 2026-08-27 复核)

SignalGraph 构建分**两层**：`UnifiedTracer.build_graph()`（高层编排）调用 `GraphBuilder.build()`（节点/边抽取）。**前一版 spec 把高层步骤错误归到了 GraphBuilder，现已修正**。

```
UnifiedTracer.build_graph()  (src/trace/unified_tracer.py:435)
├─ 1. 缓存加载 (use_cache + content-hash key)   [拿到则直接返回]
├─ 2. root = compiler.get_root()
├─ 3. SemanticAdapter(root, compiler, target_module)
├─ 4. GraphBuilder(adapter, target_module).build()   ← 见 3.2 (内部 11 步)
├─ 5. graph._adapter = semantic_adapter             (供 coverage_generator)
├─ 6. ClassGraphBuilder(adapter).build(graph)        (class/constraint 子图)
├─ 7. _resolve_class_member_access(adapter, graph)   (MEMBER_SELECT 边)
├─ 8. BitSelectHandler(adapter, graph).process()     (位选父子关系)
├─ 9. ModuleInstanceGraph(adapter, graph).build()    (跨模块边界)
├─ 10. PathResolver(graph, module_graph)
├─ 11. _init_tracers()
├─ 12. _emit_conditional_op_nodes()                  (OP_TERNARY/OP_CASE 从 expr_trees emit)
├─ 13. _backfill_source_locations(adapter)           (--show-source)
└─ 14. 缓存保存 (use_cache)
```

### 3.2 GraphBuilder.build() 内部 11 步 (src/trace/core/graph_builder.py:63)

```
if target_module: _configure_instance_paths()
1. _extract_all_nodes()               (Driver/Load/Connection/Clock extractors)
2. _extract_all_edges()
3. _mark_special_signals()
4. _create_hierarchical_bit_nodes()
5. _collect_struct_members()
6. _expand_struct_assignments()
7. _upgrade_reg_nodes()               (must be after #4)
8. _elaborate_wrapper_passthroughs()  (wrapper 模块 port passthrough)
if target_module: _filter_by_target()
9. _capture_generate_block_map()      [V16.11] generate block → LHS base 信号映射
```

> ⚠️ **[V16.11] `_capture_generate_block_map` 是真实的最后一步**，前版 spec 漏了。它把 pyslang `GenerateBlockArray/GenerateBlock.name` → LHS base signal 映射存入 `graph._gen_block_map`（供 viz 用真实 label 归位，替代启发式）。

**输出**: 返回 `SignalGraph`。跨模块、条件节点、source-location 等由 UnifiedTracer 层在 build 后补充（见 3.1 step 6-13）。

---

## 4. SignalGraph 对外 API

| 方法 | 语义 |
|------|------|
| `get_port_to_internal()` | 端口→内部信号映射 |
| `get_internal_signal(inst_port_id)` | 查实例端口的内部信号 |
| `add_trace_node(node)` | 加节点 |
| `add_trace_edge(edge)` | 加边（自动创建字面量/placeholder 节点, 孤儿节点防护） |
| `get_node(node_id)` | 查单个节点 (TraceNode \| None) |
| `get_edge(src, dst)` | 查单边 |
| `get_edges(src, dst)` | 查 (src,dst) 之间所有边 |
| `set_node_modport_dir(node_id, dir)` | (P0-3) 设节点 modport 方向 |
| `compute_effective_condition(cond)` | 静态方法, 清除条件扰动 (供 caller 重用) |
| `to_dict()` / `from_dict()` | 序列化（缓存用） |
| `_adapter` | 挂载的 semantic adapter (供 coverage_generator) |

> 前版 spec 漏了 `get_node`/`get_edge`/`get_edges`/`set_node_modport_dir`/`compute_effective_condition`（2026-08-27 复核补全，见 src/trace/core/graph/models.py:322-435）。

---

## 5. 与任务 2/3 的关系

- **任务 2 (pyslang semantic 使用模式)**: 本 spec 的输入契约 (adapter API) 详细说明见 `docs/PYSLANG_SEMANTIC_USAGE.md`（任务 2 产出）。
- **任务 3 (SV 语法识别)**: §1.3 的 "支持的 SV 输入语法" 只是摘要，详细的 SV 语法 → pyslang semantic → node/edge 映射表见 `docs/SV_SYNTAX_MAPPING.md`（任务 3 产出）。

---

## 6. 已知 gap (审查发现, 供后续)

1. **转换规则未全文档化**: §1.3 每个语法的细粒度转换规则（SV 语法 → 具体 node/edge 组合）未在本文详细展开，靠代码注释。任务 3 补充。
2. **InvalidExpression 处理策略** 是"跳过 + 改 fixture"（G3 决策），未来如需支持非法语法的诊断性信息，需专门设计（当前明确不做）。
3. **`_gen_iter_map` / `_gen_block_map`** 是 G1-G3 新引入，语义特殊（per-element vs base name），已在 §2.1 记录但转换规则需任务 3 佐证。
4. **assign_type 取值未统一建模** (2026-08-27 复核发现): 标准 3 种 (continuous/nonblocking/alias) + 真实存在的 4 种非标准取值 (internal/wrapper_passthrough/connection/port)，`full_statement`/渲染层只识别 subset。详见 `docs/SV_SYNTAX_MAPPING.md` §1。
5. **管线分层已修正** (2026-08-27): 高层步骤 (ClassGraphBuilder/ModuleInstanceGraph/_emit_conditional_op_nodes/_backfill_source_locations/缓存) 归属 `UnifiedTracer.build_graph()`，GraphBuilder 只做 11 步内部抽取（含 `_capture_generate_block_map`）。
