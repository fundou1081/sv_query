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

> 所有赋值类（`assign`/wire init/过程赋值）最终都生成 **`EdgeKind.DRIVER`** + 不同 `assign_type`；区别在**怎么建节点、怎么命名、怎么展开 generate**。

| SV 语法 (源码) | pyslang semantic 识别 | SignalGraph 产物 | assign_type |
|---|---|---|---|
| `assign q = d;` | `ContinuousAssign` symbol (semantic) | `q --DRIVER--> d` | `continuous` |
| `always_ff @(posedge clk) q <= d;` | `ProceduralBlock` → `AssignmentExpression` | `q --DRIVER--> d` + `clk --CLOCK--> q` | `nonblocking` |
| `always_comb q = a + b;` | `ProceduralBlock` → `AssignmentExpression` | `q --DRIVER--> (a+b 展开)` | `blocking` |
| `wire prod = data * weights[i];` (顶层) | `NetSymbol.initializer` | `prod --DRIVER--> data/weights[i]` | `continuous` |
| **wire prod = ... (generate-for 内)** | **`GenerateBlockArraySymbol.entries[N]` → `GenerateBlockSymbol` → `NetSymbol.initializer`** | **genvar substitute: `weights[i]→weights[N]`; `hierarchicalPath` 当 node id (`gen_accum[N].prod`)** | `continuous` |
| `a = cond ? x : y;` (三元) | `ConditionalOp` symbol | `OP_TERNARY` 节点 (name=`?: (sel)`) + BRANCH_CONDITION/TRUE/FALSE/RESULT 边 | `conditional` |
| `case (sel) ... endcase` | `CaseStatement` symbol | `OP_CASE` 节点 + CASE_SELECT/ITEM/RESULT 边 | `conditional` |
| 位选 `q <= d[msb:lsb];` | `ElementSelectSymbol` / BitSelect | 位选节点 + `BIT_SELECT` 聚合边 + `parent` 关系 | — |
| 函数调用 `f(x,y)` | `SubroutineCall` → SubroutineExpander | `FUNCTION_CALL` 节点 + 展开 | — |
| 端口连接 `.clk(clk)` | `PortConnectionSymbol` | `INSTANTIATED_MODULE` 节点 + `CONNECTION` 边 + `_port_to_internal` | — |
| 常量 `{W{1'b1}}` | MultipleConcatenation (semantic 展开) | `CONST` 节点（值展开） | — |
| alias `alias a = b;` | `NetAlias` symbol | `a --DRIVER--> b` | `alias` |
| class / constraint | `ClassSymbol` | ClassGraph 子图 (CLASS/CONSTRAINT_* 节点 + 关系边) | — |

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
