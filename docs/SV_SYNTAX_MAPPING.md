# SV 语法识别与 SignalGraph 对应 (SV_SYNTAX_MAPPING)

> 创建时间: 2026-08-27
> 状态: 活跃维护
> 目的: **建立「SV 语法 → pyslang semantic 识别 → SignalGraph node/edge」的准确对应表**，让验证工程师/开发者一眼看清每种真实 SV 语法在 graph 里长什么样、怎么被识别。
> 任务来源: [task 3] 用户 2026-08-27 13:28 — "也缺少对sv语法识别的准确探索和对应"
> 配套: `docs/SYNTAX_KIND_HANDLER_MAP.md`（976 个 SyntaxKind → handler 的完整枚举, syntax 层）;
>       `docs/PYSLANG_SEMANTIC_USAGE.md`（pyslang semantic 使用模式）;
>       `docs/SIGNAL_GRAPH_SPEC.md`（SignalGraph 输入输出 spec）。

---

## 0. 本文 vs SYNTAX_KIND_HANDLER_MAP

| 维度 | SYNTAX_KIND_HANDLER_MAP | 本文 (SV_SYNTAX_MAPPING) |
|------|------------------------|--------------------------|
| 层 | syntax 层 (SyntaxKind) | **semantic 层**（pyslang symbol） |
| 粒度 | 976 个 kind 完整枚举 | **实战常见的 SV 语法** + 对应 node/edge |
| 目的 | handler 分发完整性 | **SV 写法 → graph 结构长啥样** |

---

## 1. 核心对应表：SV 语法 → Node/Edge

> **黄金代词**: 所有 ⛔ / ⚠️ / 🔶 行有 [Phase 3 golden](test_spec_unsupported_syntax.py) 实测锁口。
>
> 所有赋值类（`assign`/wire init/过程赋值）最终都生成 **`EdgeKind.DRIVER`** + 不同 `assign_type`；区别在**怎么建节点、怎么命名、怎么展开 generate**。

| SV 语法 (源码) | pyslang semantic 识别 | SignalGraph 产物 | assign_type |
|---|---|---|---|
| `assign q = d;` | `ContinuousAssign` symbol (semantic) | `q --DRIVER--> d` | `continuous` |
| `always_ff @(posedgeclk) q <= d;` | `ProceduralBlock` → `AssignmentExpression` | `q --DRIVER--> d` + `clk --CLOCK--> q`; 是 always_ff → 节点升为 `NodeKind.REG` | `nonblocking` |
| `always_comb q = a + b;` | `ProceduralBlock` → `AssignmentExpression` | `q --DRIVER--> (a+b 展开)`; **not always_ff → 节点保持 `NodeKind.SIGNAL`** | `nonblocking` ⚠️ |
| `always_latch q = ...;` ⚠️ | `ProceduralBlock`（同入口，无 latch 特殊分支） | 按普通 always 处理。latch 语义信息（enable condition）丢失，不会升为 `REG/latch` 节点 | `nonblocking` ⚠️ |
| **`initial` 块** ⛔ | `InitialBlock` 走 `_collect_assignments_from_stmt` 但 **line 3346-3349 显式 `pass`**（statement 处理代码被注释） | 不生成任何 driver 边。`probe_initial.sv` 实测：3 节点/2 DRIVER（只来自 always_ff，initial q=1'b0 不产生任何边） | — |

> ⚠️ **assign_type 修正 (2026-08-27 13:48 首修, 13:55 复核)**: driver_extractor `_create_always_edges` **对 always_phys 和 always_comb 统一用 `assign_type="nonblocking"`**（代码不严格区分 blocking/nonblocking）。**标准取值仅 3 种** `continuous`/`nonblocking`/`alias`（**代码里没有 `blocking`**，早期推断 `always_comb→blocking` 是错的）。
>
> ⚠️ **assign_type 完整审计 (2026-08-27 13:55, 全库 grep)**: 除上述 3 种标准取值外，代码里还真实存在 **4 种非标准/辅助取值**，未在 TraceEdge 中统一建模：
> - `internal` — connection_extractor 跨模块内部连接边 (src/trace/core/connection_extractor.py:441,459; graph_builder.py:573)
> - `wrapper_passthrough` — wrapper 模块 port passthrough 边 (graph_builder.py:885)
> - `connection` — 模块端口连接边 (connection_extractor.py:429,466)
> - `port` — 输入端口外部驱动边 (handshake_detector.py:359)
>
> 影响: `models.py:286` 的 `full_statement` 用 `assign_map.get(self.assign_type, self.assign_type or "=")` 只识别 nonblocking/blocking/continuous，**其他取值 fallback 到 `=`**；`elk_svg_renderer.py:156` 只按 `== 'nonblocking'` 区分。**这些取值应被文档化而非被忽略**（后续可选:收敛到单一 enum）。
| `wire prod = data * weights[i];` (顶层) | `NetSymbol.initializer` | `prod --DRIVER--> data/weights[i]` | `continuous` |
| **wire prod = ... (generate-for 内)** | **`GenerateBlockArraySymbol.entries[N]` → `GenerateBlockSymbol` → `NetSymbol.initializer`** | **genvar substitute: `weights[i]→weights[N]`; `hierarchicalPath` 当 node id (`gen_accum[N].prod`)** | `continuous` |
| **wire prod = ... (generate-if/case 内)** 🔶 | **`GenerateBlock` (单块, 无 arrayIndex) → `NetSymbol.initializer`** | **必须用 hierarchical name `g_label.prod` 访问；`get_generate_net_declarations` (`semantic_adapter.py:1196`) 只查 `GenerateBlockArray`，未处理 `GenerateBlock` 单块 → build 丢 driver 边** | `continuous` 🔶 |
| `a = cond ? x : y;` (三元) | `ConditionalOp` symbol | `OP_TERNARY` 节点 (name=`?: (sel)`) + BRANCH_CONDITION/TRUE/FALSE/RESULT 边 | `conditional` |
| `case (sel) ... endcase` | `CaseStatement` symbol | `OP_CASE` 节点 + CASE_SELECT/ITEM/RESULT 边 | `conditional` |
| **`casez (sel) ... endcase`** ⛔ | 同 case，但 `_flatten_case` (line 2971) 把 `Case`/`PatternCase` 同等处理 | 按普通 case 展开。`?`/`z` 通配符语义**丢失**。`probe_casez.sv` 实测：3 DRIVER（全部分支驱动 q） | `conditional` ⛔ |
| **`casex (sel) ... endcase`** ⛔ | 同 casez | 同 casez。`x` 通配符语义丢失。`probe_casex.sv` 实测与 casez 完全一致 | `conditional` ⛔ |
| **`unique case (sel)`** ⛔ | 同 case，`unique` 修饰符被 strip | 按普通 case 展开 + 仅产生 `[CaseRedundantDefault]` warning（不是 unique 冲突检测）。`probe_unique_case.sv` 实测：`unique` 语义（冲突检测、并行优先级）**全无** | `conditional` ⛔ |
| **`priority case (sel)`** ⛔ | 同 unique | 同 unique（无任何 priority 处理） | `conditional` ⛔ |
| 位选 `q <= d[msb:lsb];` | `ElementSelectSymbol` / BitSelect | 位选节点 + `BIT_SELECT` 聚合边 + `parent` 关系 | — |
| **`{W{1'b1}} = q` (Replication 作 LHS)** ⛔ | SV 标准**不允许** | elaboration error：`expression is not allowed as a statement`（不是 driver_extractor 锅，是 SV 规范禁止）。RHS replication (`{3{q}}`) 则**正常生成 DRIVER** | — ⛔ |
| 函数调用 `f(x,y)` | `SubroutineCall` → SubroutineExpander | `FUNCTION_CALL` 节点 + 展开 | — |
| 端口连接 `.clk(clk)` | `PortConnectionSymbol` | `INSTANTIATED_MODULE` 节点 + `CONNECTION` 边 + `_port_to_internal` | — |
| 常量 `{W{1'b1}}` | MultipleConcatenation (semantic 展开) | `CONST` 节点（值展开） | — |
| alias `alias a = b;` | `NetAlias` symbol | `a --DRIVER--> b`（**注：方向语义与 SV 规范相反**，refs[0]=target, refs[1]=source 见 driver_extractor.py:1147-1148） | `alias` |
| class / constraint | `ClassSymbol` | ClassGraph 子图 (CLASS/CONSTRAINT_* 节点 + 关系边) | — |

> **图中符号说明**: ✅ 完整 / ⚠️ 部分（有缺陷） / 🔶 有条件（部分场景下不准） / ⛔ 不支持（spec 不应谎称支持）

**> ** Phase 3 golden 证据**: 本表所有 ⛔/⚠️/🔶 行均由 `sim/tests/test_spec_unsupported_syntax.py` 锁口实测，fixture 位于 `sim/tests/fixtures/spec_golden/`。

---

## 2. Generate-for 展开的准确识别 (G1/G2/G3 核心)

这是 case27 的主战场，也是最容易踩坑处。

### 2.1 generate-for 的信号声明 (`wire prod = data*weights[i]`)

```
源码                     pyslang semantic                对应产物
─────────────────────   ─────────────────────────────   ─────────────────────────
generate for (genvar i   module.body 顶层只看到
  = 0; i < W; i++)       GenerateBlockArraySymbol
begin : gen_accum        ├─ loopVariable.name = 'i'      genvar 名
  wire prod = data       └─ entries[0..3]                per-iteration 实例
    * weights[i];          每个 entry = GenerateBlockSymbol
end                          ├─ arrayIndex = N            genvar 值 {i: N}
                              └─ __iter__ → NetSymbol     'prod' (name)
                                  └─ initializer =        init = data*weights[i]
                                     BinaryOp (*)          (genvar substitute → weights[N])
                                  └─ hierarchicalPath =   node id 'generate_loop.gen_accum[N].prod'
                                     'generate_loop.gen_accum[N].prod'
```

**关键规则**:
- 顶层 `get_net_declarations(module)` **拿不到** generate 内的 wire（只有顶层 `prod` 无 init 的那个）。必须用 `get_generate_net_declarations`（G3 新增, §引用 PYSLANG_SEMANTIC_USAGE §2.2）。
- 4 个 entry 的 `prod` 是 **4 个独立 symbol**（`hierarchicalPath` 不同）。用 `module.name`（`generate_loop.prod` 都一样）会 max-合并成 1 个 → gap_2 只 1 个 `*`。**必须用 hp 当 node id**。

### 2.2 generate-for 内的 assign（genvar ctx substitute）

```
源码                           pyslang semantic              对应产物
───────────────────────────  ────────────────────────────  ─────────────────
for (genvar i=0;i<N;i++)      GenerateBlockArraySymbol       (driver 边 per entry)
begin : gen                   ├─ loopVariable.name 'i'
  always_ff q[i] <= in[i+1]   ├─ entry.arrayIndex N          genvar_ctx {'i': N}
                              └─ → AssignmentExpression      `in[i+1]` → `in[N+1]`
                                                              (acc[i+1]→acc[2] 独立节点,
                                                              不合并成 acc[i+1])
```

### 2.3 generate if/case

```
generate if (PARAM) begin : A ... end else begin : B ... end
```
- `GenerateBlock` symbol（单个 block, 无 arrayIndex）
- **必须 filter `isUninstantiated`**（false 分支仍 expose symbol, 不 filter 造幻觉边）
- genvar_ctx = {}（无 genvar）

---

## 3. 三元 / case 的准确对应 (G3 新增)

### 3.1 `sum_out = (acc[N] > max) ? 255 : acc[N]`

```
pyslang semantic:  ConditionalOp (条件三目)
  ├─ condition:  (acc[N] > max)   → BRANCH_CONDITION 边
  ├─ then:       255               → BRANCH_TRUE 边 → '8'd255' (CONST)
  └─ else:       acc[N]            → BRANCH_FALSE 边 → 'acc[N]'
结果:  OP_TERNARY 节点 (name='?: (sel)') → BRANCH_RESULT → sum_out

实际 rendered label: "?: (W, acc[N], {W{1'b1}})"   ← 带 selector 条件后缀
                    (不是纯 "?:")
```

**⚠️ 关键对应 (V6.9, 2026-08-13)**: `_filter_compile_time_signal_names` 里 `_walk_conds`
**专门把 ternary 的 condition 信号过滤掉** — 如 `g ? h ? x0 : x1 : x2`, g/h 是条件信号,
**不作为 driver**。原因: 条件是 selector, 不是数据驱动; 保留会污染 trace_fanin。
这也解释了为什么 ternary 的 BRANCH_CONDITION 边由渲染层 (expr_trees) 出, 而 driver 边
(DRIVER) 默认不带 condition 信号。

**⚠️ 已知边界 (G3 2026-08-27)**:
- 合法三元 `acc[N] > max ? 255 : acc[N]` → pyslang semantic 完整解析 ✅
- **非法语法 `acc[N][?:0]`**（非标准 PartSelect）→ pyslang 标 `InvalidExpression`, 三元/else 全丢。**决策: 改 fixture 而非兜底**（语法非法）。

### 3.2 case 语句

```
case (sel) → OP_CASE 节点 (name='case (sel)')
  2'd0: q = a;  → CASE_SELECT (sel) + CASE_ITEM (a) 
  2'd1: q = b;  → CASE_ITEM (b)
默认: q = c;     → CASE_ITEM (c)
结果: OP_CASE → CASE_RESULT → q
```

---

## 4. 常量 / 复制的识别

| SV 语法 | pyslang semantic | 产物 |
|---|---|---|
| `8'd255` | IntegerLiteral (semantic constant) | `CONST` 节点, label `8'd255` |
| `{W{1'b1}}` | MultipleConcatenation (+ replication) | semantic 展开 → `CONST`/值, label `{W{1'b1}}` |
| `{a, b}` | Concatenation | 展开成员 |
| `'0` / `'x` | 未填充字面量 | `CONST` |

**注意**: `{W{1'b1}}` 的 label 在渲染里保留成 `{W{1'b1}}`（不强制求值），但 `_get_all_real_signals` 会把它识别为常量而非信号。

---

## 5. 已知不支持 / 边界（准确识别为「不支持」）

| 语法 | 表现 | 处理 |
|---|---|---|
| `acc[N][?:0]` (非标准 PartSelect) | pyslang → `InvalidExpression` | **改 fixture / 跳过**（G3 决策, 不回退） |
| 跨模块内部原语 (utility cell) | 默认保留 | 按 target_module `_filter_by_target` 过滤 |
| SVA 断言 (assert property) | SVA 图待实现 | 不在 SignalGraph |

---

## 6. 与现有 docs 关系

- SYNTAX_KIND_HANDLER_MAP: 完整 SyntaxKind 枚举 (syntax 层, 976)
- PYSLANG_SEMANTIC_USAGE: 怎么安全用 pyslang semantic (模式)
- SIGNAL_GRAPH_SPEC: SignalGraph 输入输出契约
- **本文**: 真实 SV 写法 → graph 长啥样 (实战对应, semantic 层)
