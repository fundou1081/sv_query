# 📐 VIZ Golden Refinement Plan (2026-06-13)

> **目标**: 把 `dataflow` / `pipeline` / 新 `module` 可视化打磨成"精准且易懂"的图, 用 pulp axi_xbar 做 golden reference。
>
> **方法**: 边画 golden 边 review, 始终对比"代码实际"和"工具提取的结果", 迭代到对齐。

---

## 1. 决策记录

| 维度 | 决策 |
|------|------|
| Golden reference | **G4 = pulp-platform/axi_xbar** (64 文件, 工业级, 真 crossbar) |
| 对照基准 | **手工 review 图** (根据代码读出来的架构图) |
| 输出格式 | **DOT** (graphviz 渲染漂亮, 飞书可插入 PNG) |
| 跨 instance 名字 | **在 instance 边界截断** (例: `i_axi_demux.grant_o`, 不展开内部) |
| 迭代方式 | 边画边 review, 始终对比代码实际 vs 工具提取 |

---

## 2. 阶段规划 (4 个 PR, 按依赖顺序)

### PR1: Module-level 抽象 (L1)
**目标**: 1 box = 1 module instance, 边 = port connection

- 新增 `visualize module --module axi_xbar` 命令
- 不动 dataflow / pipeline
- Golden: pulp axi_xbar 顶层 (从 doc 读出架构)
- 1 个下午
- 验证: 在 Golden 上 1 box = 1 instance, port 名准确

### PR2: Dataflow 重写 (L2)
**目标**: 1 box = 1 reg / 1 combinational cluster, 边 = data flow, 节点合并

- 重写 `dataflow_viz.py`:
  - **节点合并**: 多 bit slice 同源 → 1 box
  - **passthrough 折叠**: 纯转发 → 边
  - **struct 字段**: 整体显示, 不展开
  - **clock/reset 默认隐藏** (`--show-clk-rst` flag)
  - **instance 边界截断** (按 G4 决策)
- Golden: G1 (synchronizer) + G2 (sync_fifo) + G3 (uart_transmit) + G4 (axi_xbar)
- 1-1.5 天

### PR3: Pipeline 重写 (L3)
**目标**: 1 box = 1 pipeline stage, 内部折叠, latency 计算

- 重写 `pipeline_viz.py`:
  - **真正的 stage 检测**: 用 control flow (enable/valid 链) 而非 BFS
  - **data path / control path 分离**
  - **latency 计算**: stage 0 → N 步数
  - **module instance 显示**: 跨 instance 时显示层级
  - **FSM 状态机检测**: 自动排除 state regs
- Golden: G2 + G3 + G4
- 1.5-2 天

### 收尾
- 文档 (README, screenshot)
- 黄金基础设施 (CI)
- 0.5 天

---

## 3. Golden Reference 设计

### G4 = pulp axi_xbar
**位置**: `~/my_dv_proj/axi/src/axi_xbar.sv` (+ 12 依赖)

**手画架构图** (作为黄金图, 1 box = 1 sub-module):

```
┌─ Slave Ports (×NoSlvPorts) ─────────────────────────┐
│  [ATOP filter] → [Spill Reg] → [Addr decoder]         │
│  [ATOP filter] → [Spill Reg] → [Addr decoder]         │
│  ...                                                  │
└──┬──────────────┬─────────────────────────────────────┘
   │ AW           │ AR
   ▼              ▼
┌─ AW Mux ─┐  ┌─ AR Mux ─┐
│ [AW Mux] │  │ [AR Mux] │
└─┬────────┘  └─┬────────┘
  ▼              ▼
┌─ AW Spill Reg ─┐  ┌─ AR Spill Reg ─┐
└─┬──────────────┘  └─┬───────────────┘
  ▼                   ▼
┌─ AW Arbiter (Round Robin) ─┐
│                            │ 选 master
│  1 → M0, 2 → M1, ...      │
└─┬─────┬─────┬──────────────┘
  ▼     ▼     ▼
[M0]  [M1]  [M2] ... [Mn]
  │ AW  │     │       │
  └────┴─────┴───────┘
       ▼
   [AW Spill Reg per master]
       ▼
   [Master port N]

(类似地有 W/B/R 通道)
```

### Golden 文件结构
```
tests/golden/
├── axi_xbar_module.json     # PR1: L1 抽象
├── axi_xbar_dataflow.json   # PR2: L2 数据流
├── axi_xbar_pipeline.json   # PR3: L3 流水线
├── sync_fifo_dataflow.json
├── uart_transmit_pipeline.json
└── gen.py                   # 把 actual tool 输出写成同样的 JSON
└── diff.py                  # 对比 golden vs actual
```

---

## 4. 黄金测试基础设施

### 文件格式 (JSON, 中间层, DOT 由 generator 渲染)

```json
{
  "module": "axi_xbar",
  "view": "dataflow",
  "level": 2,
  "nodes": [
    {"id": "aw_mux", "kind": "module", "label": "AW Mux",
     "cluster": "shared", "module_path": "i_aw_mux"},
    {"id": "aw_arb", "kind": "module", "label": "AW Arbiter",
     "cluster": "shared", "module_path": "i_aw_arbiter"},
    ...
  ],
  "edges": [
    {"from": "aw_mux", "to": "aw_arb", "kind": "data",
     "label": "aw_chan", "module_path": "i_aw_mux → i_aw_arbiter"},
    ...
  ],
  "clusters": [
    {"id": "slv", "label": "Slave Ports (×N)", "rank": "source"},
    {"id": "shared", "label": "Shared Logic", "rank": "middle"},
    {"id": "mst", "label": "Master Ports (×N)", "rank": "sink"}
  ],
  "metadata": {
    "source_files": 12,
    "total_modules": 11,
    "hand_drawn_by": "founder",
    "date": "2026-06-13"
  }
}
```

### 对比工具 (gen.py + diff.py)

```bash
# 1. 用工具生成 actual
python tools/golden/gen.py \
  --module axi_xbar --view dataflow \
  --filelist /tmp/pulp_axi_xbar.f \
  --output actual.json

# 2. 对比
python tools/golden/diff.py \
  --golden tests/golden/axi_xbar_dataflow.json \
  --actual actual.json

# 退出码:
#   0 = 完全一致
#   1 = 有差异 (打印差异列表)
#   2 = 工具崩溃
```

### CI 集成
```yaml
# .github/workflows/golden.yml (或本地 pre-commit)
- run: python tools/golden/run_all.py
  # 跑 4 个 reference, 全过才合并
```

---

## 5. instance 边界截断 (G4 决策 #4)

### 现状 (有问题)
```
axi_xbar.gen_slv_ports[0].i_axi_demux.i_arbiter.grant_o
```
200+ 字符, 不可读。

### 期望
```
i_axi_demux.grant_o
```
`i_axi_demux` 是 instance 边界, 在它之上的层级省略, 只保留**最内层 instance + 信号名**。

### 实现策略
1. 从 `graph.get_node(id)` 拿到 node, 看 `node.module` 字段
2. 取 `module` 字段中**最后 1-2 层 instance hierarchy**
3. 例如 `axi_xbar.gen_slv_ports[0].i_axi_demux` → `i_axi_demux` (最后 1 层)
4. 信号名拼上: `i_axi_demux.grant_o`
5. 提供 flag `--depth N` 控制截断深度 (默认 1)

### 边界条件
- 同名 instance: 保留 index `[0]`
- 顶层 (无 instance): 用模块名

---

## 6. 4 个 Golden 模块的优先级

| 阶段 | 模块 | 为什么 |
|------|------|--------|
| **PR1** | `axi_xbar` (顶层) | 验证 instance 截断 + module box |
| **PR2 start** | `synchronizer` | 极简, 调试基本 pipeline |
| **PR2** | `sync_fifo` | 验证 hand-shake pattern |
| **PR2** | `uart_transmit` | 验证单方向 stage detection |
| **PR2** | `axi_xbar` (完整) | 验证多通道 + module 聚合 |
| **PR3** | `sync_fifo` (pipeline) | 2-stage wr/rd 分离 |
| **PR3** | `uart_transmit` | 3-stage shift register |
| **PR3** | `axi_xbar` | 多通道 latency |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| Golden 图手画 = 我的主观判断 | 每次画完附"代码出处" (file:line), 跟用户确认 |
| 工具无法抽取 sub-module 关系 (interface modport 复杂) | 复用之前的 `_set_interface_modport_dirs` |
| 跨 instance 信号长, 自动截断可能丢信息 | `--depth` flag + 默认 1 层 |
| 1490 行 DOT, 渲染慢 | L1 抽象 + 默认折叠 = 50 行 |
| Pipeline stage 检测算法换了 (BFS → control flow) | 旧行为保留为 `--legacy` flag |

---

## 8. 进度跟踪

| 阶段 | 状态 | 起点 | commit |
|------|------|------|--------|
| 计划文档 | ✅ | 2026-06-13 | - |
| PR1: Module-level 抽象 | 🔵 即将开始 | - | - |
| PR2: Dataflow 重写 | ⏸ | - | - |
| PR3: Pipeline 重写 | ⏸ | - | - |
| Golden 基础设施 | ⏸ | - | - |
| CI 集成 | ⏸ | - | - |
| README 更新 | ⏸ | - | - |

---

## 9. 第一周目标 (4-5 天)

- [ ] **Day 1 上午**: PR1 基础 — `visualize module` 命令, 抽 instance 边界
- [ ] **Day 1 下午**: PR1 黄金 — 手画 axi_xbar 顶层 L1 图, JSON 写完
- [ ] **Day 2 上午**: PR1 收尾 — 黄金测试通过, 1 box = 1 instance 验证
- [ ] **Day 2 下午 - Day 3**: PR2 — Dataflow 重写, 4 个黄金
- [ ] **Day 4-5**: PR3 — Pipeline 重写, 3 个黄金

---

## 10. 工具链

```
源代码 (pulp axi)
   ↓
[unified_tracer] → SignalGraph
   ↓
[新 module-extractor] → ModuleNode, Connection (instance port 边)
   ↓
[visualize module] → L1 DOT (1 box/module)
   ↓
[visualize dataflow] → L2 DOT (reg-level, 重写)
   ↓
[visualize pipeline] → L3 DOT (stage-level, 重写)
   ↓
DOT → PNG/SVG (graphviz render)
```

每一步的中间结构都是 **JSON**, 可以:
- 跟 golden diff
- 给 LLM 反查
- 给文档生成器用
