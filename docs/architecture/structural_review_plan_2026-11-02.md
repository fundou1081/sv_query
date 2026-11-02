# 结构审查与动态子图 — 开发计划

**日期**: 2026-11-02
**状态**: 方向已确认；执行前必须先完成 P59 旧资产清理。
**计划源**: [PLAN.md](../../PLAN.md) 的 P58~P62（本文件只解释设计与验收，不另立状态）。

---

## 1. 背景与结论

多轮真实使用后的结论：

1. **全设计图作为分析入口不成立**
   - 简单设计：图是多余的翻译层，读代码更快；
   - 复杂设计：节点/边超过人眼工作记忆，图不能承担数据流计算或架构建模；
   - 连接关系确认：CLI 结论更精确、可引用、可 diff，图反而多一步。

2. **图作为数据结构仍然必要**
   - SignalGraph 已支撑 fanin/fanout、paths、dataflow、bit consistency、verify；
   - 图的价值在“可计算的结构”，不在“画出来”。

3. **图作为 review 证据有条件成立**
   - 必须是局部子图（5~20 节点）；
   - 必须服务于一个已经成立的 finding；
   - 必须高亮 expected/actual 与证据；
   - 全图不是 review artifact。

4. **架构级建模是另一条产品线**
   - 若目标变成全芯片架构/数据流 IR，CIRCT/MLIR 这类 IR 比 slang 图更合适；
   - 但这是独立投资，不在本计划内，也不应作为可视化功能的补丁。

**一句话**：

> 把“图”从展示对象降级为查询结果；把“动态子图”升级为 core 能力；  
> 可视化只作为 finding 的可选局部证据。

---

## 2. 目标与非目标

### 目标

| 目标 | 说明 |
|---|---|
| **动态子图 core API** | 高频、确定性、有预算、有 boundary/truncated |
| **结构审查 findings** | 对称性、连接签名、typo 候选；输出证据而不是图 |
| **局部 review artifact** | finding 邻域的可选 SVG/HTML；人可快速确认 |
| **清理旧可视化** | 全设计图命令/渲染器/文档退出产品面 |

### 非目标

- ❌ 恢复“全设计 graph/dataflow/pipeline 一览图”作为主功能；
- ❌ 本阶段接 CIRCT / dielet / MLIR；
- ❌ 为每个命令维护一套渲染器；
- ❌ 修改用户 RTL/工程文件；
- ❌ 用图证明逻辑等价；
- ❌ 现在做完整交互式 UI（必须先有稳定子图/ finding API）。

---

## 3. 关键决策

| ID | 决策 | 理由 |
|---|---|---|
| D1 | 全设计图退出默认产品面，只保留 exp/归档 | 真实使用中不可读、不可算 |
| D2 | SignalGraph 保留为唯一结构数据源 | trace/verify 已依赖，不能丢 |
| D3 | 动态子图是 core 查询，不是 view 功能 | agent、review、symmetry 共用 |
| D4 | 一个子图实现，渲染器只消费子图 JSON | 避免 6 套 renderer 分叉 |
| D5 | finding 先于图；图只画 finding 邻域 | 防止“为画图而画图” |
| D6 | CIRCT 作为独立未来 track | 不把 slang 图硬撑成架构 IR |
| D7 | 交互式 debug 最后做，且有 gate | 没有稳定 API 前做 UI 会返工 |
| D8 | 旧命令先冻结、再删除/归档 | 不盲删，保留 git 可追溯 |

---

## 4. 目标架构

```text
SignalGraph
   │
   ├─ graph subgraph <seeds>  ──→ 局部 nodes/edges/boundary JSON
   │                                  │
   │                                  ├─ agent 连续追问
   │                                  ├─ symmetry/typo findings
   │                                  └─ review artifact（可选 SVG/HTML）
   │
   └─ verify structural ──→ findings JSON
                              │
                              └─ subgraph spec（finding 自带的邻域查询）
```

原则：

- subgraph 只返回**结构事实**，不返回布局/颜色/HTML；
- finding 只返回**结论 + 证据 + 子图查询参数**；
- view 层只做**渲染**，不重新遍历图；
- 不存在“`visualize` 自己取一份子图”的第二套逻辑。

---

## 5. 核心命令契约（P60）

### 5.1 `graph subgraph`

```bash
svq graph subgraph <seed...> \
  --depth 2 \
  --direction in|out|both \
  --edge-kinds driver,connection \
  --max-nodes 80 \
  --max-edges 160 \
  --evidence \
  --json
```

#### 参数

| 参数 | 默认 | 语义 |
|---|---|---|
| `seed...` | 必填 | canonical/relative signal；多 seed 去重 |
| `--depth` | 2 | k-hop；0 = 只返回 seed |
| `--direction` | both | 相对 seed 的遍历方向；输出边仍保留方向 |
| `--edge-kinds` | `driver,connection` | 可选 `control,clock,reset,bit_select` |
| `--max-nodes` | 80 | 含 seed 的硬上限 |
| `--max-edges` | 160 | 两端都在结果内的边上限 |
| `--evidence` | false | 是否附 file:line / 边证据 |
| `--json` | true | core 必须 JSON |
| `--from-snapshot` | 无 | 复用已建图（P60 可选） |

#### 返回结构

```json
{
  "ok": true,
  "command": "graph_subgraph",
  "params": {...},
  "seeds": [
    {"requested": "top.u.addr", "resolved": "top.u.addr", "status": "ok"}
  ],
  "result": {
    "nodes": [
      {"id": "...", "kind": "SIGNAL", "module": "...",
       "width_msb": 7, "width_lsb": 0, "width": 8,
       "precision": "bus", "parent": null, "bit_range": null}
    ],
    "edges": [
      {"src": "...", "dst": "...", "kind": "DRIVER",
       "expression": "...", "condition": "...", "bit_slice": ""}
    ],
    "boundary": ["..."],
    "truncated": {"nodes": false, "edges": false, "depth": false},
    "stats": {"visited": 42, "returned_nodes": 42, "returned_edges": 61}
  },
  "errors": []
}
```

#### 硬性规则

- 节点 ID 必须是 canonical；不接受渲染用短名；
- 默认排除 `BIT_SELECT` 聚合边、clock/reset；
- `boundary` 是预算/深度截断处的节点 stub，供 UI 继续展开；
- `truncated` 必须显式；
- BFS 顺序稳定；输出按 id 排序，保证可 diff；
- 有环安全；
- 多 seed 缺失/歧义逐项报错；至少一个有效 seed 才 `ok=true`；
- 预算内不返回“图外邻居”的边。

### 5.2 性能目标

- 不复制整图；只从 seed 邻接索引遍历；
- `visited` 以预算为上限，不做全图 BFS；
- 10k 节点图、depth=2、80 节点预算目标 < 100ms（不含建图）；
- 高频交互另做长驻 session，不把 daemon 塞进 CLI。

---

## 6. 结构审查 findings（P61）

### 6.1 首批检查

| check | 说明 | 置信 |
|---|---|---|
| `symmetry.port_signature` | 同类型 sibling 实例的端口连接签名偏差 | high/medium |
| `symmetry.source_pattern` | generate 分组内源信号命名/索引模式偏差 | medium |
| `connection.width` | 连接两端 width/slice 不一致 | high |
| `connection.one_ended` | 只有一端、另一端缺失的候选 | medium |
| `typo.candidate` | 综合上述偏差的 typo 候选 | low/medium |

不做的检查：

- 功能等价；
- 时序等价；
- 算术谓词证明；
- 依赖猜测的“应该接这里”。

### 6.2 Finding schema

```json
{
  "id": "sym:top.u[0].addr",
  "check": "symmetry.port_signature",
  "severity": "warning",
  "confidence": "medium",
  "message": "u[0] 与 u[1] 的 addr 源模式不一致",
  "seeds": ["top.u[0].addr", "top.u[1].addr"],
  "expected": {"port": "addr", "source": "cfg.addr"},
  "actual": {"port": "addr", "source": "cfg.data"},
  "evidence": [{"file": "top.sv", "line": 42, "edge": "..."}],
  "subgraph": {
    "seeds": ["top.u[0].addr", "top.u[1].addr"],
    "depth": 2,
    "direction": "both",
    "edge_kinds": ["driver", "connection"]
  }
}
```

规则：

- 无证据不输出 finding；
- 不能证明时 `confidence=low/unknown`，不伪造 high；
- finding 只带 **subgraph 参数**，不带图数据；
- `verify structural` 只读、JSON-first；
- 按严重度/置信度排序，支持 `--max-findings`。

### 6.3 与现有 verify 的关系

- `verify consistency`：图结构不变量（全图 reciprocity/bit/connection）；
- `verify claim`：单条 claim 验证；
- **`verify structural`**：局部模式/对称性/typo 候选。

三者不互相替代，也不重复实现同一语义。

---

## 7. 局部 review artifact（P62）

### 7.1 第一版：静态 artifact

```bash
svq verify structural ... --json > findings.json
svq review render findings.json --finding-id ... --svg out.svg
```

（命令名暂定，P62.1 再定；原则是**一个 finding 一张局部图**。）

要求：

- 只画 finding 的 subgraph；
- 高亮 expected/actual/异常边；
- 默认 ≤ 20 节点；超出显式提示；
- 复用 VizData/ELK 或 Graphviz 的**一个**渲染路径；
- 不重新查询/遍历图，只消费 subgraph JSON；
- 无 finding 时不生成“全图替代品”。

### 7.2 第二版：交互式 debug（gate）

只有满足以下条件才启动：

1. P60 子图 API 在真实 review 中稳定使用；
2. P61 至少产出一组真实 typo/symmetry finding；
3. 静态 artifact 被证明降低 review 时间；
4. 有长驻 session/API 方案，不每次点击重建图。

交互形态：

```text
finding 面板 → 局部图 → 点击节点展开一跳 → evidence 面板
```

不做：

- 全图浏览；
- 自由拖拽全设计；
- 为每个命令做一套 UI。

---

## 8. 旧代码清理（P59，必须先于 P60）

### 8.1 原则

1. **先冻结，再删**：先隐藏/停止注册，跑全量；再删除/归档；
2. **先盘点，不盲删**：每个文件/命令/测试/文档标记 keep/archive/delete；
3. **保留 git 历史**：删除前确认可追溯；文档归档到 `docs/archive/`；
4. **不删 SignalGraph / trace / verify**；
5. **不删 bit/width/cache 相关核心修复**；
6. **一个语义只留一个实现**。

### 8.2 盘点对象

| 资产 | 当前状态 | 初判 |
|---|---|---|
| `src/cli/view/visualize*.py` 7 命令 | hidden/exp | 全设计图命令冻结/归档 |
| `src/cli/view/arch.py` | hidden/exp | `summary` 可评估保留；图形模式归档 |
| `src/cli/view/design.py` | hidden/exp | 归档（覆盖少，与 review 目标不符） |
| `src/trace/core/graph/viz/` | VizData/ELK | 仅保留局部 review 需要部分 |
| `src/trace/core/graph/analyzer/*viz*` | 旧 DOT | 评估后删除/归档 |
| `trace fanin/fanout --format dot` | legacy 输出 | 盘点后决定保留/移除 |
| `trace overview` | view 叙述 | 可能保留为 review 摘要，单独评估 |
| `VISUALIZATION.md` / `VIZ_COMMANDS.md` / `VIZ_DESIGN_SPEC.md` / `VIZ_GOLDEN_PLAN.md` | 过期/冻结 | 归档；新文档重写 |
| 旧 visualize 测试 | 大量/部分 skip | 随命令删除/归档；保留的加 smoke |
| `PRIMARY_FEATURES.md` 的 visualize 主推声明 | 过期 | 改为指向新计划 |
| `LayerSpec view` “stable/in_capabilities” | 与实际 `_v`→exp 不一致 | 清理时统一 |

### 8.3 清理验收

- `sv_query --help` 不再出现全设计图命令；
- `capabilities` 不承诺 view 全图；
- `rg` 无对已删模块的 import/引用；
- 文档无死链、无“已删命令”教程；
- 全量测试 + 真实项目 smoke 0 failed；
- 删除/归档在独立 commit，可 revert；
- **P59 完成前不开始 P60 实现。**

---

## 9. 阶段与验收

> 状态以 [PLAN.md](../../PLAN.md) 为准；下表只描述交付物。

| 阶段 | 交付物 | 验收 |
|---|---|---|
| **P58** | 本计划 + 决策记录 | 方豆确认；PLAN 登记 |
| **P59** | 旧资产清单、冻结、删除/归档、文档/测试收口 | 8.3 全满足 |
| **P60** | `graph subgraph` core + JSON schema + tests | 稳定排序/预算/boundary/ambiguous/性能 |
| **P61** | `verify structural` findings + tests | finding 有证据/置信/子图 spec；真实项目无误报 |
| **P62** | 局部 SVG/HTML artifact + 可选交互 | 只画 finding 邻域；复用子图数据 |

### P60 测试矩阵

- 单 seed / 多 seed；
- depth 0/1/2；
- in/out/both；
- edge kind 过滤；
- 预算截断（nodes/edges/depth）；
- 环；
- 歧义/不存在 seed；
- bit/parent 节点；
- 确定性（两次输出一致）；
- evidence on/off；
- 10k 节点性能烟测。

### P61 测试矩阵

- 对称 sibling 正常（无 finding）；
- 一个端口源偏差（finding）；
- width/slice 偏差；
- generate 分组；
- 证据缺失 → 不输出 finding；
- confidence 不升级；
- finding 的 subgraph spec 可被 P60 执行。

---

## 10. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 清理误删仍被依赖的渲染器 | 先冻结 + `rg` 引用 + 全量；独立 commit 可 revert |
| 子图 API 变成“可视化专用” | 强制 core JSON、agent 测试、finding 复用 |
| 高频交互性能差 | 先 benchmark；必要时长驻 session，不污染 CLI |
| symmetry/typo 误报 | 只输出候选 + confidence；证据不足不输出 |
| 又回到全图 | 默认预算/局部 seed；全图命令退出产品面 |
| ELK 维护成本 | 只在局部 artifact 复用；不迁移旧 renderer |

---

## 11. 成功标准

1. 旧全图命令不再出现在产品面；
2. `graph subgraph` 成为 agent/review/symmetry 共用的唯一子图入口；
3. 一个真实 typo/symmetry finding 能带证据和局部子图 spec 输出；
4. review artifact 只画 finding 邻域，且不重新遍历图；
5. 全量门禁与真实项目 smoke 保持绿色；
6. 不再新增“每个命令一套渲染器”。

---

## 12. CIRCT / 架构级建模

**本计划不做。**

如果未来目标变成：

- 全芯片架构 IR；
- 可组合数据流变换；
- 形式化/优化 passes；
- 层次化 dielet 建模；

则应单独立项评估 CIRCT/MLIR。  
`sv_query` 的定位仍是**源码忠实的局部查询 + 结构校验层**，不把 slang 图硬撑成架构 IR。
