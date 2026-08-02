# 定点数计算架构图 — 功能 Spec

> 创建: 2026-08-02
> 目标: 一张图看清计算架构 — 运算链、时延、控制、位宽、选择逻辑

---

## 用户需求

一张图能同时看到:
1. **计算架构** — 数据是怎么算的 (a+b, a<<b, signed>>> 等)
2. **运算链** — 从 input 到 output 的完整路径，每个节点是什么运算
3. **时延** — 经过了多少拍 (cycle/stage)，哪些在同一个 cycle
4. **控制** — 哪些信号受条件控制 (if state==..., mux 选择)
5. **数值** — 每个信号的位宽 [7:0]、[4:0]
6. **选择逻辑** — MUX/conditional assign 的具体条件

---

## 现有能力分析

### 已有视图

| 命令 | 做了什么 | 缺什么 |
|------|---------|--------|
| `compute` | 边上显运算符(+/-/&)，按 op 分类着色 | 无 cycle/stage 划分，无 control 条件，信号节点是纯数据 |
| `timed` | 时间轴 + OP圆形节点 + pipeline stage cluster | 依赖 pipeline stage 检测（非 pipeline 模块无 stage），位宽不在边上 |
| `dataflow` | data path + control 边（虚线），条件标注 | 无运算符可视化，无 cycle 信息 |
| `chain` | input→output 方形路径 | 无运算细节，仅路径连通性 |
| `pipeline` | register chain → time cycle/stage | 需要 register chain 存在才能用 |
| `graph` | 全信号关系图 | 信息过载，不易定位计算链 |

### 核心数据结构 (V6.7 VizData)

```
VizData
├── nodes: list[VizNode]
│   ├── id, label, module, kind (REG|WIRE|PORT_IN|PORT_OUT|CONST)
│   ├── width: (msb, lsb)          ✅ 位宽已可用
│   ├── stage_id, cycle             ✅ pipeline stage 已可用
│   └── class_: DATA|CONTROL|CLOCK   ✅ 分类已可用
│
└── edges: list[VizEdge]
    ├── src, dst, kind, expression   ✅ 已有
    ├── source_op: "+", "&", "<<"    ✅ 运算符已提取
    ├── source_bit_start/end         ✅ 位范围已提取
    ├── source_casts: ["$signed"]    ✅ cast 已提取
    ├── condition: "if state==FETCH" ✅ 条件已提取
    ├── edge_cycle_delta             ✅ 跨 cycle 信息
    └── assign_type                  ✅ continuous/blocking/nonblocking
```

### 关键差距

| 用户要的 | 现状 | 差距 |
|----------|------|------|
| 运算符在节点上可见 | 运算符在边上 (compute) | 需要 OP 节点模式 (timed 有但依赖 pipeline) |
| cycle/stage 划分 | timed 有但依赖 pipeline | 需要 infer pipeline stages 或用 comb_logic_depth 估算 |
| 控制/MUX 条件 | dataflow 有虚线 | 未在 compute/timed 中整合 |
| 位宽在节点标签 | 已有 `[7:0]` | compute 缺，graph 有 |
| 选择逻辑 (a ? b : c) | 未特殊处理 ternary/mux | 需要识别并标注在边上 |
| 延迟注释 | 无 | 需要标注每个 stage 或 register-to-register 延迟 |

---

## Spec 设计

### 方案：`datapath` — 新的可视化命令

在现有 `compute` + `timed` 基础上，融合为一个新的 `datapath` 视图，专门为定点数计算架构优化。

#### 设计目标

一张图 = **数据流方向(LR) + 时间轴(stage cluster) + OP节点(圆形) + 条件(虚线) + 位宽(节点标签) + 选择(mux标注)**

#### 渲染规则

```
┌─────────────────────────────────────────────────────────┐
│  Datapath View: top_module                              │
│                                                         │
│  Cycle 0 (Inputs)    Cycle 1 (Comb)     Cycle 2 (Output)│
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ a [7:0]   ──┼───→│    (+)     ─┼───→│ y_arith[7:0]│  │
│  │ b [7:0]   ──┘    │ arith       │    │             │  │
│  │                 │    (<<)    ─┼───→│ y_shift[7:0]│  │
│  │ a [7:0]       │ shift       │    │             │  │
│  │ sh_am[4:0]    │             │    │             │  │
│  │                 │   (>>>)    ─┼───→│y_signed[7:0]│  │
│  │ sra ─ ·· ·· ··│*signed      │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                         │
│  Legend: ○ arith  — → data  ··→ control(MUX/cond)      │
└─────────────────────────────────────────────────────────┘
```

#### 具体规则

1. **Layout**: LR (left-to-right)，数据从左流向右边
2. **Stage 划分**:
   - 有 pipeline reg → 同 timed，按 register 分 cycle
   - 纯组合逻辑 → infer combinational depth (0→pipeline_inputs, 1→operator_nodes, N→comb_outputs)
   - stage cluster 用 `subgraph cluster_stage_N`，灰色背景
3. **OP 节点**: 圆形 (`shape=circle`)，填充运算符符号 (+, −, ×, &, |, <<, >> 等)
   - 同 timed 的 OP 节点模式
   - 按 op 类别着色 (算术=橙, 逻辑=蓝, 移位=绿, 比较=紫)
4. **信号节点**: 方框 (`shape=box`)，带位宽 `[7:0]`
   - PORT_IN: 浅橙色 invhouse
   - PORT_OUT: 浅绿色 invhouse
   - REG: 浅蓝色方框，加粗边框
   - WIRE: 白色方框
5. **边**:
   - **data path**: 实线，同 op 颜色
   - **control/MUX**: 虚线，标注条件 `if sra`
   - **选择逻辑**: ternary `a?b:c` → 从 a 出来虚线 `if a`，b/c 各分叉
6. **位宽标注**: 每个信号节点 label 包含 `name [width]`
7. **来源引用**: 可选 `--show-source` → 节点标签加 `file:line`

#### CLI 接口

```
sv_query visualize datapath [OPTIONS]

定点数计算架构图: 一张图看清运算链、时延、控制、位宽、选择逻辑。

Options:
  --file/-f           SystemVerilog 源文件 (单文件模式)
  --filelist          filelist 路径 (项目模式)
  --include/-I        Include 目录
  --target/-t         Target module
  --no-strict         非严格模式 (partial AST)
  --focus/-F          只画特定信号的计算链 (可选)
  --stages STAGES     阶段划分模式: auto(default) | reg | depth2 | depth3
  --show-control      显示控制/条件边 (默认: 仅数据)
  --show-source       节点加 file:line 注释
  --layout/-l         LR(default) | TB
  --dot               DOT 输出路径
  --png               PNG 输出路径 (自动 dot -Tpng)
  --svg               SVG 输出路径
  --html              HTML 输出路径 (交互式)
```

#### Stage 划分模式

| 模式 | 说明 |
|------|------|
| `auto` | 有 REG 用 timed 模式，没有则用 depth2 |
| `reg` | 仅按 register 分 cycle (原 timed 逻辑) |
| `depth2` | 2 stage: inputs → [OP层] → outputs |
| `depth3` | 3 stage: inputs → [OP组合1] → [OP组合2] → outputs |

---

### 实现策略

#### 最小改动路径

现有的 `viz_timed_compute_renderer.py` (265 lines) 已经实现了 OP圆形节点 + stage cluster 的核心逻辑。`datapath` 在它基础上做三个增强:

1. **Stage 检测增强** (data_builder 层，~50行)
   - 对非 pipeline 模块用 topological depth 做 stage inference
   - 从 PORT_IN depth=0 → 每过一个 driver_edge depth+1

2. **控制/条件边整合** (renderer 层，~30行)
   - 遍历 edges，有 `condition` 的用虚线 + 条件标签
   - 已存在的 MUX 检测逻辑按需增强

3. **位宽显示优化** (renderer 层，~10行)
   - 节点 label 里 width 已经是 `[7:0]`→ 确认渲染正确

#### 新建文件

```
src/trace/core/graph/viz/viz_datapath_renderer.py  (~200行, 新文件)
src/cli/commands/datapath.py                        (~100行, 新文件, 注册到 visualize)
```

#### 复用模块

- `viz_data_models.py` — VizData/VizNode/VizEdge 不变
- `viz_data_builder.py` — VizBuildOptions 加 `datapath_mode` 字段
- `_dot_common.py` — sanitize_dot_id 复用
- `signal_classifier.py` — DATA/CONTROL 分类复用
- `driver_extractor.py` — 驱动信息提取复用 (V6.5 的 SignalSource 已完整)


### 阶段划分

| Phase | 内容 | 预估 |
|-------|------|------|
| P0 | datapath renderer (OP节点+stage cluster+位宽) | 2h |
| P1 | 控制/条件边整合 + MUX 选择逻辑 | 1.5h |
| P2 | Stage inference (非pipeline模块) | 1.5h |
| P3 | CLI 注册 + golden tests + golden baseline | 1.5h |
| P4 | HTML 交互式输出 (highlight/zoom) | 2h |

总计 ~8.5h，P0-P3 可达 MVP (~6.5h)

---

### 验证用例

1. `binary_ops.sv` — 定点数运算全覆盖 (+, <<, >>>, nested &, |)
2. `golden_mini/mux_demo.sv` — MUX 选择逻辑
3. 真实定点数模块 (TBD — 用户提供或从 open source 找)

### 输出格式

- DOT → graphviz → PNG (最基础)
- SVG (矢量，方便缩放看细节)
- HTML (交互式，节点点击展开 source)

---

## 讨论点

1. **stage 检测算法**: 从 PORT_IN 做 BFS topological depth，用 comb assign 边? 还是用 always_ff 的 clock edge 当 stage 边界?
2. **OP 节点合并**: 多个操作数是否合并到同一个 OP 节点 (如 `a+b` → `a` 和 `b` 都指向 `(+)`) — 当前 timed 已实现合并
3. **节点太多怎么办**: `--focus SIGNAL` 只画 N-hop 邻域 (类似 teach 的 focus 模式)
4. **跟现有命令怎么共存**: `datapath` 是新命令，不删 `compute/timed/chain` 等，各司其职
