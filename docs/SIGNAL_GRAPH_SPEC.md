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

| SV 语法 | 处理路径 | 支持级别 |
|---------|---------|---------|
| `assign` (连续赋值) | DriverExtractor `_parse_assign` | ✅ 完整 |
| `always_ff` / `always_comb` 过程块 | DriverExtractor, 含 blocking/nonblocking | ✅ 完整 |
| 模块端口连接 (port mapping) | ConnectionExtractor | ✅ 完整 |
| generate-for 内声明 (`wire prod = data*weights[i]`) | `get_generate_net_declarations` (G3 新增) | ✅ 完整 (G3, 2026-08-27) |
| generate block 展开 (per-iteration) | `hierarchicalPath` 区分 + `_gen_iter_map` | ✅ 完整 (G1/G2/G3) |
| 三元条件 `? :` | OP_TERNARY 节点 (emit, Plan B) | ✅ 完整 |
| case 语句 | OP_CASE 节点 (emit, Plan B) | ✅ 完整 |
| 位选/部分选 `a[msb:lsb]` | BitSelectHandler + BIT_SELECT 边 | ✅ 完整 |
| 函数调用 | SubroutineExpander + FUNCTION_CALL | ✅ 完整 |
| class / constraint | ClassGraphBuilder (子图) | ✅ 完整 |
| struct 赋值 | `_expand_struct_assignments` | ✅ 完整 |
| 常量 `{W{1'b1}}` (concatenation + replication) | semantie 展开 | ✅ (G3 验证) |
| **非标准部分选 `acc[N][?:0]`** | pyslang 标为 `InvalidExpression`，**不支持**（task 3 记录） | ⚠️ 明确不支持 |

### 1.4 输入边界（什么 NOT 进 graph）

- **非标准 / 非法 SV 语法**（如 `acc[N][?:0]`）会被 pyslang semantic 标为 `InvalidExpression`，其驱动边**被跳过**（G3 决定：改 fixture 而非为非法语法做兜底）。
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

`UnifiedTracer.build_graph()` 管线：

```
1. 缓存检查 (use_cache, content-hash key)
2. root = compiler.get_root()  →  SemanticAdapter(root, compiler, target_module)
3. GraphBuilder(adapter, target_module).build()
      ├─ _configure_instance_paths()        (target_module 时)
      ├─ _extract_all_nodes()               (Driver/Load/Connection/Clock extractors)
      ├─ _extract_all_edges()
      ├─ _mark_special_signals()
      ├─ _create_hierarchical_bit_nodes()
      ├─ _collect_struct_members() / _expand_struct_assignments()
      ├─ _upgrade_reg_nodes()
      └─ _elaborate_wrapper_passthroughs()  + _filter_by_target()
4. ClassGraphBuilder.build(graph)            (class/constraint 子图)
5. _resolve_class_member_access()
6. BitSelectHandler.process()                (位选父子关系)
7. ModuleInstanceGraph.build()               (跨模块边界追踪)
8. _emit_conditional_op_nodes()              (OP_TERNARY/OP_CASE 从 expr_trees emit)
9. _backfill_source_locations()              (--show-source)
10. 缓存保存
```

**输出**: 返回 `SignalGraph`，挂载 `self._module_graph`(ModuleInstanceGraph), `self._path_resolver`(PathResolver), 以及 `graph._adapter`(semantic adapter, 供 coverage)。

---

## 4. SignalGraph 对外 API

| 方法 | 语义 |
|------|------|
| `get_port_to_internal()` | 端口→内部信号映射 |
| `get_internal_signal(inst_port_id)` | 查实例端口的内部信号 |
| `add_trace_node(node)` | 加节点 |
| `add_trace_edge(edge)` | 加边（自动创建字面量/placeholder 节点, 孤儿节点防护） |
| `to_dict()` / `from_dict()` | 序列化（缓存用） |
| `_adapter` | 挂载的 semantic adapter (供 coverage_generator) |

---

## 5. 与任务 2/3 的关系

- **任务 2 (pyslang semantic 使用模式)**: 本 spec 的输入契约 (adapter API) 详细说明见 `docs/PYSLANG_SEMANTIC_USAGE.md`（任务 2 产出）。
- **任务 3 (SV 语法识别)**: §1.3 的 "支持的 SV 输入语法" 只是摘要，详细的 SV 语法 → pyslang semantic → node/edge 映射表见 `docs/SV_SYNTAX_MAPPING.md`（任务 3 产出）。

---

## 6. 已知 gap (审查发现, 供后续)

1. **转换规则未全文档化**: §1.3 每个语法的细粒度转换规则（SV 语法 → 具体 node/edge 组合）未在本文详细展开，靠代码注释。任务 3 补充。
2. **InvalidExpression 处理策略** 是"跳过 + 改 fixture"（G3 决策），未来如需支持非法语法的诊断性信息，需专门设计（当前明确不做）。
3. **`_gen_iter_map` / `_gen_block_map`** 是 G1-G3 新引入，语义特殊（per-element vs base name），已在 §2.1 记录但转换规则需任务 3 佐证。
