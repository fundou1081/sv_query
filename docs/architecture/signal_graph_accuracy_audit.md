# Signal Graph 准确性审计清单 (2026-09-03, 声明版 2026-09-05)

> **维护**: 在语义边界前提 (Semantic-only 限 RTL 顶层域; SVA/procedural/inline =
> hybrid 例外域, 见 `inline_constraint_semantic_unavailable.md`) 下, 逐条验证
> signal graph 结果不准确处。**每条 = 可复现现象 + 源码位置**。
> **规则**: 修复后把条目移到"已修复"并注明迭代; 新发现在此登记。
> **对外答案**: 先看下方 `📜 Accuracy Claim` (分层声明), 本文件其余部分是它的证据。

---

## 📜 Accuracy Claim — 分层准确性声明 (2026-09-05, 方豆问询落档)

> **问题**: "能否说 signal graph 产生的图一定是代码的准确映射?"
> **一句话答案**: **不能无限制地说**。图是建模决策的产物、受范围限定、
> 且有已知反例。可核查的说法是下面的**分层声明** — 每层能承诺什么、
> 在什么范围内、反例是什么, 逐项对照。

### 1. 为什么不是"字面准确": 建模决策 (刻意抽象, 非 bug)

| 抽象点 | 决策 | 语义影响 |
|---|---|---|
| 粒度 | A2 = 总线粒度 (位查询空答 → 提升父总线; 位对位 = backlog) | 查询答案可能粗于位级 |
| 端口边界 | fanin 停在"有内部逻辑的模块端口" (iter_132); 纯直通 wrapper 穿透 (iter_134) | 答案粒度 = 端口/实例级, 不塌缩到 assign 操作数 |
| 自环 | internal 标记自环排除出驱动源 (iter_127); nonblocking 真自环保留 | 驱动源集合不含"模块内部驱动"标记 |
| 时钟/复位 | CLOCK/RESET = 采样关系, 非数据驱动源 (iter_128) | 数据 fanin 不含时钟链 (assign out=clk 例外, 走 DRIVER) |
| 顶层输入 | 空 fanin = 预期 (外部驱动在图外) | 图内无源, 查询返回 uncertain |
| 双向/共享 | inout / interface 成员 = 单向建模, 方向拍板 (iter_129) | 多驱动归属不承诺 (见 L3) |

### 2. 分层声明

| 层 | 承诺内容 | 状态 |
|---|---|---|
| **L1 结构层** | 节点/边存在性正确: 实例路径、端口连接 (CONNECTION)、驱动 (DRIVER) 不缺失、不造假节点 | ✅ **已验证设计域内可宣称** — iter_117~134 修复后 (假节点/假驱动清零均有可复现证据), 3048 tests 锁定 |
| **L2 查询层** | fanin / 驱动答案正确 | ✅ **限"建模粒度语义"内可宣称**: 总线粒度 (A2)、端口/实例粒度 (iter_132/134 停靠规则)、自环/时钟排除规则。超出粒度的问题 (如要位级归属) 不承诺 |
| **L3 深层语义层** | 多驱动归属 / 双向 / 共享合并语义 | ❌ **不承诺** — 命中下方反例即图在该点不准 |

### 3. 范围限定 (声明仅在以下前提成立)

- **语义域**: RTL 组合/时序连接、generate 各形态 (for/if/case/嵌套)、bus/位选、
  inout/interface 单向、门级端子方向。SVA / procedural / inline 约束 = hybrid
  例外域, 不在 signal graph 承诺内。
- **验证语料**: 3048 pytest (fixture 抽取自真实项目模式) + 真实设计抽查
  (aes 4834 节点 / cordic / serv / verilog-axi / minimal_3module)。
- **上游依赖**: 正确性上限受 pyslang elaboration 影响; strict 编译受阻的设计
  (CVA6 / coralNPU / vortex) 图无法建立。

### 4. L3 已知反例 (命中 = 图在该点不准; 逐项 = backlog, 修一项移一项)

| # | 反例 | 出处 |
|---|---|---|
| ~~1~~ | ~~inout 双向多驱动归属 (i2c 开漏)~~ — **✅ 定性闭环 (iter_138/139)**: ①语义澄清 — 开漏总线"谁在驱动"依赖运行时 en, 静态只能给**可能驱动方集合** (fanin 已实现, 正确语义; 归属单点超出承诺域); ②真缺陷已修 — 三态使能 en 经 BRANCH 链混入数据 fanin 的不对称杂音 (iter_139: BRANCH_*/CASE_* 与 CLOCK 同规则排除, en 保留在 DRIVER.condition) | iter_138/139 |
| 2 | interface master+slave 同线多写共享语义 (多实例同驱成员) | CURRENT_TODO backlog |
| ~~3~~ | ~~A2 位对位折算: 跨实例桥为总线粒度~~ — **✅ 同构直连已通 (iter_137)**: bus↔bus 同宽直连的位查询贯通到位级 (顶层位 == 模块内位查询一致); **残留 (更窄)**: 切片/非零 base 位偏移映射 (.y(y[7:4]) 型) 仍 bus 粒度 | 本文件 A2 后续项 |
| 4 | gate G-2/G-3: drive strength/delay 未进图, UDP table 可视化缺 | tasks/L2_gate_primitive_support.md |
| ~~5~~ | ~~slang generate-entry 合并枚举 (iter_119 观察)~~ — **✅ 闭环 (iter_136)**: 复现证明观察真身 = input 端口位宽不匹配时 Conversion 壳未剥 → 连接静默丢 (y 侧 iter_120 已修 / a 侧 iter_136 修), 非 slang 合并 | — |
| 6 | iter_121 SVA 补丁 = syntax 症状修, semantic 消歧重构未做 | 决策文档 D3 |
| 7 | CVA6/coralNPU/vortex strict 编译受阻 — 图建不出来 | ARCHITECTURE_TODOLIST §#7 |

---

## ✅ 已修复 (iter_126/127, 2026-09-04)
| 条目 | 修复 | 位置 |
|---|---|---|
| A1 无 target 盲区 | **CLI 设计视图入口** (build_viz_tracer, 无 `--module` 时) 自动单 top target: 库默认 `build_graph()` 保持无 target 类型级多模块契约 (cross_module/boundary 等测试锁定 mixed-namespace 语义), 需要的调用方显式传 `auto_target_single_top=True` | `_viz_common.py` build_viz_tracer + `unified_tracer.py` build_graph 新参数 (≈435); 证据 cordic CLI 无 module 365→542 节点 / 667 rects, `genblk1[0].U.x_shifter` 出现 |
| A2 总线直连位查询空答 | query/signal.py: 位节点不存在 → 提升父总线 (总线粒度); 存在位节点无驱动 → BIT_SELECT 出边提升 | `_trace_drivers_recursive` (≈74-165) |
| A2 粒度说明 | iter_126: 结果总线粒度 (top.y[3] → u_sub.y)。**iter_137 位对位 (同构直连)**: bus↔bus 同宽 CONNECTION 补位桥边 (仅两侧位节点存在) + 查询位桥出口递归 → fanin(top.y[3]) 贯通到 sub 内部位逻辑源 (== fanin(top.u_sub.y[3])); 纯 bus 直通 (无位节点) 保持总线粒度 (不造假节点)。**残留**: 切片/非零 base 位偏移映射 (.y(y[7:4])) | `graph_builder._expand_bus_conn_bit_bridges` + query/signal.py CONNECTION-SIGNAL 分支 |
| A3 端口 DRIVER 自环计入源 | 查询层跳过 `assign_type=="internal"` 自环 (实例输出端口标记, 恒 src==dst); nonblocking 真自环 (`state<=state+1`) 保留 | query/signal.py `_trace_drivers_recursive` + `_find_drivers`; fanin(top.u_sub.y) `[a, 自身] → [a]` |

## 🐛 未修复

### A1. (✅ iter_126 收窄: CLI 入口启用) 无 target_module 时 generate 实例内部逻辑缺失 (严重)

**现象**: `build_graph(target_module=None)` (CLI `--module` 缺省) 时, generate-for
实例内部的 assign/always 不提取 — 实例内部信号只在 connection 层 (端口自环)。
**证据** (cordic fixture `golden_dataflow_39`):
- `target=None`: 365 节点 (auto 后 542), rotator 实例内部信号整块缺失
  (auto 后出现 `cordic.genblk1[0].U.x_shifter.D` 等实例路径节点)
**源码位置**:
- `src/trace/core/graph_builder.py:68` — `_configure_instance_paths` 仅在
  `if self.target_module:` 下跑; None 时 driver 无实例路径
- `src/trace/core/driver_extractor.py:1287` — `if self._instance_paths:` 为假 →
  else 旧路径按模块类型名提取 (generate 内实例从不作为 (path,module) 处理)
**触发**: CLI `visualize dataflow` 不传 `--module` (默认 None,
`src/cli/commands/visualize.py:260`)、或任何 API 调用不设 target。
**修复 (2026-09-04 定稿)**: 库 API 默认**不**自动 target — 无 target 类型级
多模块图是既有契约 (cross_module_tracking/boundary/module_synth/stats 等 8+
测试锁定 mixed-namespace: `top.u_tb.clk` 实例端口 + `tb.clk_out` 类型级并存)。
改为:
- `unified_tracer.build_graph(..., auto_target_single_top=False)` 新参数, 默认关
- CLI 用户入口 `build_viz_tracer` (src/cli/_viz_common.py) 在无 `--module` 时传
  `auto_target_single_top=True` — 单 top 设计自动聚焦, 多 top 库保持全图
- iter_113-120 已让**直接** generate 实例 (leaf 在 top 内 generate-for) 在无
  target 下也有实例路径; flag 补齐的是**嵌套实例内部真实 assign** (cordic 型)
**影响**: 真实项目无 module 参数跑 CLI 可视化时, 图不再缺整棵子实例内部逻辑
(darkriscv/picorv32 等)。库 API 调用方需要实例级视图时显式传 flag。

### A2. (✅ iter_126, 总线粒度) 子模块输出总线直连顶层总线位时, 顶层位无 DRIVER (中)

**现象**: `sub u_sub(.y(y))` 且 sub 输出总线位由内部 assign 驱动, 顶层 `y[3]`
查询"谁驱动" = ∅ (真源 `top.a[3]` 链: a[3]→u_sub.a[3]→(assign)→u_sub.y[3]→
(CONNECTION 总线)→top.y[3] 不贯通)。
**证据** (两模块 bus passthrough fixture):
- `top.y[0..3]` 位驱动全空; `top.u_sub.y ← {u_sub.a, u_sub.y(自环)}`; 只有
  `('top.u_sub.y','top.y')` 总线级 CONNECTION, 无位级 CONNECTION/DRIVER
**源码位置**:
- `src/trace/core/connection_extractor.py:567-577` (边2) — instance port →
  parent wire 只按**总线名** (inst_port_id/parent_signal 是 `...y` 非 `...y[3]`),
  不做位展开
- 位级查询依赖 bit nodes 的 BIT_SELECT + DRIVER, 跨实例位→位无桥
**修复方向**: 总线级 CONNECTION 两侧按端口位宽展开为位对位 CONNECTION
(或查询层把 bus CONNECTION + 位宽传播作为 fanin 一跳)。
**影响**: "顶层输出总线某位谁驱动" 回答为空 — 门级/总线直连真实设计 (KS 加法器等)。

### A3. (✅ iter_127) 端口 DRIVER 自环计入驱动源 (轻微, 设计标记)

**现象**: 实例输出端口节点自带 DRIVER 自环 (`...u_sub.y -DRIVER-> ...u_sub.y`,
"模块内部驱动"标记 [FIX 2026-07-08])。fanin(端口) 会把它自身列为一个源;
按 DRIVER 集合相等断言的场景需手动排除 (本项目 truth 测试都写了排除)。
**源码位置**: connection/driver 端口处理 — 自环标记 (connection_extractor output
边1 `src=child_signal_id dst=inst_port_id DRIVER internal`, 恒 src==dst —
connection_extractor.py:564-566)。
**修复 (iter_127)**: 查询层区分两类自环 —
- `assign_type=="internal"` DRIVER 自环 (实例输出端口标记) → **跳过**, 不计为
  驱动源 (真实驱动由同节点其他 DRIVER 边或 forward-lookup 提供)
- 其他自环 (nonblocking `state<=state+1` 等真操作数自环) → **保留**
位置: `query/signal.py` `_trace_drivers_recursive` (主循环) + `_find_drivers`
(depth=1 路径) 两处同规则。
**证据**: fanin(top.u_sub.y) `['top.a','top.u_sub.y'] → ['top.a']` (target 模式);
depth=1 `['top.u_sub.a']`; no-target `['sub.a']`; `state<=state+1` 自环保留。
图结构不改 (internal 自环边仍在图中, 供 out_edges/可视化使用)。

---

## 🐛 已知缺口 (待专项)

(当前无活跃缺口 — 最新登记项见下方 已修复/backlog 文档; 深层语义项
inout 双向多驱动 / interface 多写共享 见 iter_129 记录与 CURRENT_TODO)

## ✅ 已修复 (历史, 防止复发复登)

| 条目 | 修复迭代 | 位置 |
|---|---|---|
| input 端口位宽不匹配连接静默丢 (Conversion 壳未剥, iter_119 观察真身) | iter_136 | semantic_adapter `get_instance_connection` Conversion 剥壳 |
| 嵌套 generate 深层路径重复段假节点 (aes 型 ×351 / cordic ×105) | iter_134 | connection_extractor `_get_generate_block_name` 直接宿主判定 (hp 末段前一段 name[N]) + query wrapper cross 守卫 get_edges 全查 + wrapper_passthrough 自递归 |
| generate RHS 位选丢索引 (总线当源) | iter_118 | semantic_adapter `_extract_signals_from_expr` |
| 索引段加倍假节点 | iter_117 | connection_extractor `get_path` gen_block 去重 |
| generate 实例连接 per-entry 丢失 (legacy 覆盖/key 碰撞) | iter_119/120 | connection_extractor 逐实例路径 |
| RangeSelect (+:) 连接命名恒 '?' | iter_119 | semantic_adapter `_conn_expr_to_signal` |

---

## 🔭 待验证候选 (实测于 iter_128/129)

| 候选 | 实测结果 | 判定 |
|---|---|---|
| inout 双向端口 | **✅ 修复 (iter_129)**: PORT_INOUT kind 正确; connection_extractor 补 inout 分支 (output 式 CONNECTION inst_port→parent, 父↔实例同线无方向归属); fanin(顶层 inout) 穿透到实例内部三态驱动链 (top.sda 空答 → [u_io.data]) | ✅ 修复 |
| struct/union 字段 | 字段驱动正确 (p.addr←a + member→struct BIT_SELECT); **A2 提升条件 bug 已修**: 根查询有直接 DRIVER 误提升 → 兄弟字段泄漏 (fanin(p.addr) 含 p.data) | ✅ 修复 (iter_128) |
| interface/modport | **✅ 修复 (iter_129)**: 成员级桥 (实例端口成员 ↔ interface 实例成员, 单向按"实例内部是否驱动成员"定方向: writer 驱动 u_w.b.addr→bf.addr / slave 只读 bf.addr→u_s.b.addr); fanin 假驱动修 (A2 提升目标限 data 类节点, 禁模块实例 top.bf) | ✅ 修复 |
| 派生时钟/多时钟域 | CLOCK/RESET 边提取正确 (div2→cnt_b); **fanin 假驱动已修**: CLOCK/RESET 边被当数据源递归追 (跨模块链 div2←u_div.clk←top.clk 混入) | ✅ 修复 (iter_128) |
| 顶层输入 fanin | 空答 + confidence=uncertain = **预期语义** (外部驱动, 图内无源) | ✅ 预期, 测试锁定 |

### 新增修复 (iter_128, 候选验证连带发现)

- **fanin CLOCK/RESET 边守卫** (query/signal.py 主循环): CLOCK/RESET 是时序采样关系非数据驱动 — 不 append 不递归。此前"其他边类型递归"把时钟链当数据源 (多模块: cnt_b ←CLOCK div2 ←CONNECTION u_div.clk ←CONNECTION top.clk → fanin(cnt_b) 含 top.clk 假驱动)。数据用 clk (assign out=clk, DRIVER continuous) 不受影响。
- **A2 提升条件修正** (query/signal.py ~174): `not drivers` → `not has_driver_edge and not drivers`。原条件 drivers 在下方主循环前几乎恒空, 根查询有直接 DRIVER 也误提升 (struct 字段 p.addr←a 升到父 struct p → 泄漏兄弟 p.data); 加 has_driver_edge 后若只查此 (无 not drivers) 又会让中间递归位 (data[7] 作 y 源被追自身驱动, 顶层输入位) 误提升 → 父总线子节点探索 seen 污染兄弟位 data[0] (fanin(y) 丢源)。两条件都需: 有直接驱动不升 (字段), 递归中间不升 (输入位)。
