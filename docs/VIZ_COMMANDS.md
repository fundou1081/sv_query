# 画图命令完整参考 (VIZ_COMMANDS)

> **状态**: V6.3 (2026-07-25), 文档 sync 2026-08-26 (--dot → --svg) — 含 `teach` (V6.0), `--show-source` (V6.2 / V6.2.1), edge conditions (V6.3).
> **目标读者**: 想快速知道 "我要画 X, 用哪个命令" 的人.
> **测试基础**: 文档中的所有示例都在 `sim/tests/fixtures/golden_mini/*.sv` 上验证过 (commit `2c3183b`).

---

## 📚 命令全景

sv_query 的可视化能力分散在 3 个命令族:

| 族 | 用途 | 子命令数 |
|----|------|---------|
| `visualize *` | 单 module 内的信号/数据流/模块级视图 | 7 |
| `arch show` | 项目级架构视图 (L1+L2 跨模块) | 1 |
| `* analyze` (verify / timing / cdc / backpressure) | 各自领域的分析报告, 部分带图 | 4 |
| `design show --graph` | 自动批量出图 | 1 |

**底层输出格式**: 所有图都是 `DOT` (graphviz 标准) 或 `Mermaid` 或 `HTML` (内嵌 SVG). 用 `dot -Tpng file.dot` 或 mermaid-live / GitHub 渲染.

---

## 1️⃣ `visualize` (7 个子命令)

### 速查表

| 子命令 | 一句话 | 适用场景 | 输出 |
|--------|--------|---------|------|
| **`graph`** | 完整信号图 (所有 edge kind) | 想看模块里**全部**信号连接 | DOT/Mermaid/HTML |
| **`dataflow`** | 数据流图 (data path + control) | 想看**运算路径**和 mux 选择 | DOT |
| **`pipeline`** | Pipeline 流图 (按 time stage 排) | 想看**寄存器链**和 stage 数 | DOT (3 种 layout) |
| **`gap`** | 验证缺口图 (高亮无 SVA/Coverage) | 想找**待补的验证点** | DOT |
| **`chain`** | input → output 全链路 data path | 想看**最长路径** | DOT |
| **`module`** | L1 module-level (1 box = 1 instance) | 看**项目架构** | DOT |
| **`teach`** | 教学视图 (重点推荐) | 想**速懂**陌生模块 | DOT/HTML (含 SUMMARY) |

### 通用选项

```bash
-f <file>          # 单文件
--filelist <f.f>   # 多文件 (项目模式)
-I <dir1,dir2>     # include 路径
--no-strict        # 部分 AST 也跑 (默认 strict, 大项目用 --no-strict)
--svg       # 输出 DOT
--mmd OUT.mmd      # 输出 Mermaid  
--html OUT.html    # 输出 HTML (SVG 内嵌)
```

---

### 1.1 `visualize graph` — 完整信号图

**做什么**: 画出模块里**所有信号**和它们之间的所有关系 (DRIVER / CLOCK / RESET / ENABLE / BIT_SELECT / MEMBER_SELECT).

**什么时候用**: 
- 第一次看一个模块, 想看全貌
- 想知道某个信号到底有多少输入和输出 (in/out degree)
- 想看模块整体拓扑

**示例**:
```bash
sv_query visualize graph \
  -f sim/tests/fixtures/golden_mini/case_demo.sv \
  --no-strict \
  --module-only \
  --svg 
```

**输出特点**:
- 节点 = 信号/端口
- 边 = 数据流方向 (有向, 箭头指向被驱动方)
- 颜色 = 风险等级 (红/黄/绿)
- 节点标签 = name + kind + fan-in/out 计数

**额外选项**:
- `--layout LR|TB`: 左右 vs 上下布局
- `--cluster-modules`: 按模块聚类
- `--max-edges N`: 限制边数 (默认 200)
- `--exclude-clock` / `--exclude-reset`: 排除时钟/复位边
- `--show-source`: 加 file:line 标注 (V6.2.1+)
- `--module-only`: 只画顶层模块

---

### 1.2 `visualize dataflow` — 数据流图

**做什么**: 把边按类型分类着色 — **蓝色实线 = data 路径**, **橙色虚线 = control 信号** (enable/valid/select).

**什么时候用**:
- 想区分"算术/逻辑路径" vs "控制路径"
- 看 MUX 怎么被 select 选通
- 看哪个 valid 信号控制哪个数据搬运

**示例**:
```bash
sv_query visualize dataflow \
  -f sim/tests/fixtures/golden_mini/if_demo.sv \
  --no-strict --with-clk-rst \
  --show-source \
  --svg 
```

**输出特点**:
- 数据边: 蓝色实线 (`#226699`)
- 控制边: 橙色虚线 (`#ff9900`)
- MUX 汇聚点: 粗边框
- 寄存器: 粗边框
- `--show-source` (V6.2.1+): 加 file:line

**额外选项**:
- `--with-clk-rst`: 包含 clock/reset 节点 (默认排除)
- `--split-by-module`: 大图按 instance 拆成多个 DOT

---

### 1.3 `visualize pipeline` — 流水线图

**做什么**: 自动**检测 register chain**, 把图按 time cycle / stage 排版.

**什么时候用**:
- 想看流水线有几级 latency
- 看每个 stage 包含哪些 combinational 节点
- 看 control 信号在哪个 stage 有效

**示例**:
```bash
sv_query visualize pipeline \
  -f sim/tests/fixtures/golden_mini/pipeline_demo.sv \
  --no-strict \
  --svg 
```

**3 种 layout 模式**:
| Layout | 触发 | 用途 |
|--------|------|------|
| **stage flow** (默认) | `--unfold` 关闭 | 按 stage 折叠, 适合大流水线 |
| **timing** | `--timing` | 平行 lanes × cycles, 适合画时序图 |
| **load-path** | `--load-path` | 按输入端口路径分组, 适合数据并行 |

**额外选项**:
- `--max-comb-per-stage N`: 每 stage 最多 combinational 节点 (默认 8, 防 PNG 爆炸)
- `--max-control-nodes N`: 控制信号区最多节点 (默认 12, 0 = 隐藏)
- `--unfold`: 不折叠, 全部 stage 单独画
- `--fold-every N`: 超过 30 stage 时每 N 个一组折叠

---

### 1.4 `visualize gap` — 验证缺口图

**做什么**: 高亮**有风险但没 SVA 没 Coverage** 的信号 (🚨).

**什么时候用**:
- 想知道 RTL 里哪些信号值得加 SVA
- code review 时找盲区
- 跑完 `verify gap` 后想可视化

**示例**:
```bash
sv_query visualize gap \
  -f sim/tests/fixtures/golden_mini/coverage_demo.sv \
  --no-strict \
  --min-risk 20 \
  --svg 
```

**输出特点**:
- 节点颜色 = 风险等级 (红🚨 > 黄⚠ > 绿✓)
- 节点标签尾部: ✓ (有 SVA) / 🟡 (有 cov) / ✓🟡 (都有) / 🚨 (都没有)

**额外选项**:
- `--min-risk N`: 只显示风险 ≥ N 的 (默认 20)

---

### 1.5 `visualize chain` — input → output 全链路

**做什么**: 从 input 端口一路追到 output 端口, 画**最长 data path**.

**什么时候用**:
- 想看某条 input 数据怎么流到某条 output
- 计算 critical path latency

**示例**:
```bash
sv_query visualize chain \
  -f sim/tests/fixtures/golden_mini/pipeline_demo.sv \
  --module pipeline_demo \
  --no-strict \
  --svg 
```

---

### 1.6 `visualize module` — L1 module-level

**做什么**: 1 个 box = 1 个 sub-module instance. 按 instance 层级分 cluster.

**什么时候用**:
- 第一次看一个 IP 的架构
- 看模块怎么被实例化
- L2 模式: 看 instance-to-instance 的 port 边

**示例**:
```bash
sv_query visualize module \
  -f sim/tests/fixtures/golden_mini/case_demo.sv \
  --no-strict \
  --depth 2 \
  --svg 
```

**额外选项**:
- `--depth N`: 包含几层 instance (1 = 只看顶层直接 children)
- `--mig / --no-mig`: 用 ModuleInstanceGraph 画跨 instance port 边 (默认 ON)
- `--edges / --no-edges`: 是否显示 instance-to-instance port 边
- `--max-edges N`: 限制边数

---

### 1.7 `visualize teach` ⭐ — 教学视图 (V6.0+, 推荐)

**做什么**: 综合视图, 针对"我刚拿到一个陌生模块, 5 分钟想搞明白"的场景. 4 个 use case (A/B/C/D) 都支持.

**什么时候用**:
- 第一次看一个模块, 想要**5 分钟搞清楚**
- 想知道某条信号被谁驱动 (--focus + --upstream)
- 想知道某条信号驱动谁 (--focus + downstream 默认)
- 想看 MUX 选通条件 (--focus + 边上的 label)
- 想知道哪些信号没 SVA 没 Covergroup (--show-coverage)

#### 4 个 use case

**A) 速懂陌生模块** (默认, 无 --focus)
```bash
sv_query visualize teach \
  -f sim/tests/fixtures/golden_mini/case_demo.sv \
  --target case_demo \
  --no-strict \
  --html /tmp/case_teach.html
```
HTML 包含: 模块端口 + FSM + pipeline + coverage summary + 结构总图.

**B) 查 1 条信号路径** (--focus)
```bash
sv_query visualize teach \
  -f sim/tests/fixtures/golden_mini/case_demo.sv \
  --target case_demo --focus y --upstream --depth 2 \
  --no-strict --show-source \
  --svg 
```
- `--upstream`: 找前驱 (谁驱动 --focus)
- 默认 downstream: 找后继 (--focus 驱动谁)
- `--depth N`: 几跳邻域 (默认 2)

**C) 看控制关系** (--focus + --show-drives)
```bash
sv_query visualize teach \
  -f sim/tests/fixtures/golden_mini/fsm_demo.sv \
  --target fsm_demo --focus state_q --show-drives --depth 2 \
  --no-strict \
  --svg 
```
焦点信号作为 driver 的边被标橙加粗 (告诉你"如果你改 state_q, 影响哪些下游").

**D) 看覆盖缺口** (--show-coverage)
```bash
sv_query visualize teach \
  -f sim/tests/fixtures/golden_mini/coverage_demo.sv \
  --target coverage_demo --show-coverage \
  --no-strict \
  --html /tmp/cov_teach.html
```
无 SVA 无 Coverage 的信号标 🚨.

#### 边上的 guard condition (V6.3+)

每个 DRIVER 边自动带 `label=...` 显示 guard:
- `if (sel) y <= a; else y <= b;` → `a → y [label="sel"]`, `b → y [label="!sel"]`
- `case(op) 2'd0: y<=d0; ...` → `d0 → y [label="op == 2'd0"]`, `d3 → y [label="op == default"]`
- `assign y = sel ? a : b;` → `a → y [label="sel"]`, `b → y [label="!(sel)"]`

CLOCK / RESET / ENABLE 边不带 label (那是 always-块守卫, 不是 per-edge 条件).

#### --show-source (V6.2+)

每个节点标签自动带 `file:line`, DOT 输出同时带 `tooltip=` 和 `URL=` 属性, 浏览器可直接跳转到 `code -g <file>:<line>`.

```bash
sv_query visualize teach ... --show-source
```

节点标签示例:
```
"case_demo.d0" [label="d0\nPORT_IN\ncase_demo.sv:2"
               tooltip="case_demo.sv:2"
               URL="case_demo.sv#2"]
```

---

## 2️⃣ `arch show` — 项目级架构

**做什么**: 跨模块的 L1+L2 架构图. 一个 IP 的所有 sub-instance 之间的关系.

**什么时候用**:
- 第一次拿到一个 RTL 项目, 看顶层结构
- 看 instance 怎么互连
- 想把架构图发给同事

**示例**:
```bash
sv_query arch show \
  -f project_top.sv --depth 3 \
  --no-strict \
  --format dot \
  --output /tmp/arch.dot
```

**支持的格式**:
- `dot` (默认) — graphviz
- `mermaid` — markdown 友好
- `json` — 程序化访问

**额外选项**:
- `--depth N`: 跨几层 instance (默认 2)
- `--summary`: 只输出统计 (无图)
- `--show-anomalies`: 检测并显示异常 instance (无 def / 未使用)
- `--cluster-by-type`: 按 instance 类型分 cluster (AXI / clock-gen / fifo)

---

## 3️⃣ `* analyze` — 各自领域分析 (部分带图)

| 命令 | 文本报告 | 可视化 | 触发选项 |
|------|---------|--------|---------|
| `verify gap` | ✅ | DOT / Mermaid | `--svg` 或 `--mmd OUT.mmd` |
| `timing analyze` | ✅ | DOT | `--svg` (P1 fix 2026-07-10) |
| `cdc analyze` | ✅ | ❌ (仅文本) | — |
| `backpressure analyze` | ✅ | Mermaid | `--output OUT.mmd` (默认 stdout) |

### verify gap

**做什么**: 综合分析"高风险但无验证"的信号. 输出**风险评分 + DOT/Mermaid 图**.

```bash
sv_query verify gap \
  -f sim/tests/fixtures/golden_mini/coverage_demo.sv \
  --no-strict \
  --svg  \
  --evidence
```

输出 DOT 包含: 高风险信号 (红色) + 它们的数据流边.

### timing analyze

**做什么**: 时序关键路径分析 (register depth, DAG longest path, SCC 检测).

```bash
sv_query timing analyze \
  -f sim/tests/fixtures/golden_mini/case_demo.sv \
  --no-strict --max-paths 5 \
  --svg 
```

### backpressure analyze

**做什么**: AXI/TL-UL ready/valid backpressure 拓扑. 自动产生 Mermaid 图.

```bash
sv_query backpressure analyze \
  -f axibus.sv --no-strict \
  --output /tmp/bp.mmd
```

### cdc analyze

**做什么**: Clock Domain Crossing 检测. ⚠️ **当前只有文本报告, 无图**. 要看 CDC 图用 `visualize graph` (信号级 CLOCK 节点会着色).

---

## 4️⃣ `design show --graph` — 一键批量出图

**做什么**: 自动跑 `dataflow + pipeline + backpressure` 三个子分析, 一键出 PNG/SVG.

**什么时候用**:
- 拿到新 IP, 想**最快速度看到 4 个角度的图**
- 给同事做 code review 时附图

**示例**:
```bash
sv_query design show \
  -f top.sv --target my_ip \
  --no-strict \
  --graph \
  --graph-dir /tmp/auto_graphs/
```

**输出** (默认 `/tmp/sv_query_design_graphs/`):
```
dataflow.png         dataflow.dot
pipeline.png         pipeline.dot
backpressure.svg     backpressure.mmd
```

**额外选项**:
- `--skip <name>`: 跳过子命令 (cdc/protocol/handshake/backpressure/dataflow/timing)
- `--json`: 程序化访问全部结果
- `--target M`: 指定目标 module

---

## 🎯 实战选择指南

| 我想... | 推荐命令 |
|---------|---------|
| **速懂陌生模块** | `visualize teach --html` (use case A) |
| **查某条信号被谁驱动** | `visualize teach --focus SIG --upstream --show-source` |
| **查某条信号驱动谁** | `visualize teach --focus SIG` (默认 downstream) |
| **看 MUX 怎么选通** | `visualize teach --focus OUT --upstream` (边上有 `sel` / `op == 2'd0` label) |
| **看流水线几级** | `visualize pipeline --unfold` |
| **看数据流分类** (data vs control) | `visualize dataflow --with-clk-rst` |
| **找验证缺口** | `visualize gap --min-risk 20` 或 `verify gap --svg` |
| **看项目架构** | `arch show --format dot --depth 3` |
| **跨模块追溯** | `visualize module --depth 2` |
| **一次出全套图** | `design show --graph --graph-dir /tmp/g/` |

---

## 🧪 测试与示例

文档里所有示例都在 `sim/tests/fixtures/golden_mini/` 验证过:

| Fixture | 演示什么 |
|---------|---------|
| `if_demo.sv` | if/else MUX (condition: `sel` / `!sel`) |
| `case_demo.sv` | case MUX 4 路 (condition: `op == 2'd0` 等) |
| `ternary_demo.sv` | 三目 MUX (condition: `sel` / `!(sel)`) |
| `pipeline_demo.sv` | 2 级寄存器链 |
| `fsm_demo.sv` | 4 态 FSM (IDLE/RUN/DONE/ERR) |
| `coverage_demo.sv` | 有 SVA + covergroup + 故意无覆盖的 other_q |

跑测试:
```bash
PYTHONPATH=src:tools python3 -m pytest \
  sim/tests/cli/test_visualize_teach.py \
  sim/tests/cli/test_visualize_teach_source.py \
  sim/tests/cli/test_visualize_teach_edge_condition.py \
  sim/tests/cli/test_visualize_graph_source.py \
  sim/tests/cli/test_backfill_source_locations.py \
  -v
```

(应有 48+ tests 全过)

---

## 📖 相关文档

- `docs/VISUALIZATION.md` — 旧版 API 总览 (V5 era, 仍可参考基础概念)
- `docs/VIZ_DESIGN_SPEC.md` — V6.0 `teach` 设计 spec
- `docs/VIZ_UNDERSTANDING_CRITERIA.md` — V6 self-eval 评分卡 (v6 怎么算"有用")
- `docs/CLI_COMMAND_CHEATSHEET.md` — 全部命令 cheat sheet
- `docs/ARCH_VISUALIZATION.md` — arch 命令专属文档

---

## 🔧 渲染输出

DOT 文件转图片:
```bash
dot -Tpng file.dot -o file.png           # PNG
dot -Tsvg file.dot -o file.svg           # SVG (可缩放)
dot -Tsvg_cairo file.dot -o file.svg     # 高质量 SVG
```

Mermaid 文件 (`.mmd`):
- 直接粘 GitHub markdown / issue
- 或上 https://mermaid.live 渲染

HTML 文件:
- 浏览器直接打开
- 包含 SVG (可缩放) + 总结文字 + 跳转链接