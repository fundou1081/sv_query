# CURRENT_TODO — 当前正在做的事

> **唯一入口**: 本文件是"此刻在做什么"的**唯一稳定追踪点**。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-09-03 GMT+8 (门级原语 leaf cell 建模进行中, iter_112)

---

## 📍 分工 (避免和其他文件重复)

| 文件 | 职责 | 时间尺度 |
|---|---|---|
| **CURRENT_TODO.md** (本文件) | **此刻**在做的 1 个任务 + 它的 sub-task 勾选 | 小时 ~ 天 |
| `docs/ARCHITECTURE_TODOLIST.md` | 架构改造 7 项的长期追踪 (ROI / 工作量 / 状态变更日志) | 周 ~ 月 |
| `docs/TODO.md` | 版本级功能待办 (V6.8 / V6.9 / V7.0 ...) | 月 ~ 季 |
| `docs/task_tree/` | 任务迭代记录 (每次迭代一个文件, 详见 AGENTS.md) | 每次迭代 |

**规则**: 本文件**只写当前**。任务做完 → 归档到 `docs/task_tree/` + 更新对应长期 todolist → 从本文件移走。

---

## 🔥 当前任务

**等待方豆指示** (最近完成: iter_126~129 审计修复 + iter_130 真实验证零副作用)

**iter_134 (2026-09-05)**: 嵌套 generate 深层重复段假节点清理 — gen_block
只取直接宿主 generate 段 (hp 紧邻实例名前段 name[N]); aes 假节点
279/1116→0, cordic 105→0 (truth 更新); 连带修 wrapper cross get_edges
全查 + PORT_OUT 内部驱动自递归 (test_deep 回归)。unit +3; 全量
2937 passed。
[iter_134](docs/task_tree/iterations/iter_134_nested_gen_dup_cleanup.md)

**iter_133 (2026-09-05)**: iter_131/132 真实项目复验 (aes 4834 节点/272
实例) — fanin 位隔离零跨 entry 生效; dataflow 已知限制区分。复验暴露
**嵌套 generate 深层重复段假节点 backlog** (aes 型 351/4834: ROUND[1].
U_ROUND.ROUND[1].U_SUB, 内层重复外层段; baseline 既有, fanin 主链 0 污染)
已登记 audit 🐛 区。
[iter_133](docs/task_tree/iterations/iter_133_real_verify.md)

**iter_132 (2026-09-05)**: generate per-entry fanin 位隔离 — fanin(top.y[3])
串入 G[0..2] 双根因修: A2 提升加 incoming-CONNECTION 守卫 (有实例输出源不
提升) + wrapper cross 加"无内部驱动才跨" (注释意图漏实现)。fanin(y[i]) 恰
[G[i].u_leaf.y], bus 聚合/wrapper/纯直通/xor 全保; unit +3; 全量 2934 passed。
[iter_132](docs/task_tree/iterations/iter_132_genfor_fanin_isolation.md)

**iter_131 (2026-09-04)**: usage 4 失败深挖 — 1 个真回归 + 3 测试债务。
真回归: dataflow _find_paths bus 查询首个非空候选组合即 return (iter_118
per-entry 后丢 req_i[1..7], arbiter 40→8→1) — 修复为合并所有候选组合,
8 paths 恢复; golden 40→8 同步 (usage + subfunction)。测试债务: p6 计数
断言过时 / m12 目录依赖 / factory 单文件 grep。unit +3; 主全量 2928 passed。
[iter_131](docs/task_tree/iterations/iter_131_dataflow_bus_agg_fix.md)

**iter_130 真实验证结论 (2026-09-04)**: iter_126~129 改动在真实设计
(aes 11292 nodes / CORDIC / minimal_3module CLI) 零副作用; usage 套件
4 失败当时判定基线既有 (后经 iter_131 深挖: 1 真回归 + 3 债务)。
push 12 commits 至 backup 完成。
[iter_130](docs/task_tree/iterations/iter_130_real_verify_wrapup.md)## 🔥 当前任务

**当前**: 等待方豆指示 (最近完成: iter_121 SVA 6 缺口 / iter_122 covergroup cross /
iter_125 inline 约束决策 — 见 overview rows 42-44)

**#7 inline 约束: 已决策暂缓不做** (iter_125, 方豆拍板) — semantic 侧确认不可达:
pyslang 语义模型对"声明级约束有符号 / 调用点 randomize-with 无符号"是固有不对称
(ConstraintBlock 只计 named; 语句是 StatementKind 非 SymbolKind); syntax 唯一入口
但受 pyslang import-order env bug 制约。维护:
[决策文档](docs/architecture/inline_constraint_semantic_unavailable.md) (含未来改善观察)

**准确性审计 (2026-09-03/04)**: [signal_graph_accuracy_audit.md](docs/architecture/signal_graph_accuracy_audit.md)
- ✅ A1 无 target_module → generate 嵌套实例内部缺失 (iter_126, 收窄后):
  库默认保留无 target 类型级多模块契约; CLI 可视化入口 (build_viz_tracer 无
  --module) 自动单 top target — cordic 365→542 节点/667 rects, genblk
  实例内部真实 assign 出现。`build_graph(..., auto_target_single_top=True)`
  供库调用方 opt-in
- ✅ A2 子模块输出总线直连顶层位 → 位查询空答 (iter_126): 位节点不存在/无驱动
  → 提升父总线 (总线粒度; 位对位折算 = 后续项)
- ✅ A3 端口 DRIVER 自环计入源 (iter_127): 查询层跳过 assign_type="internal"
  自环 (实例输出端口标记); nonblocking 真自环 (state<=state+1) 保留
- ✅ 待验证候选 5 项全闭环 (iter_128/129): struct 字段正确; 派生时钟域
  CLOCK 提取正确 + fanin CLOCK 假驱动修复; 顶层输入空 fanin = 预期锁定;
  inout 跨模块连接修复 (output 式同线 CONNECTION); interface 成员级桥修复
  (单向按驱动方向: writer/slave) + fanin 假驱动消除 (A2 提升目标限 data 类)
- ⏳ 更深语义 backlog (iter_129 记录): inout 双向多驱动归属 (i2c 开漏) /
  interface master+slave 同线多写共享语义 — 当前单向链逐层可追, 多驱动
  归属需专项拍板

**backlog (未启动, 按序)**:
1. gate 遗留改进 G-2 (drive strength/delay 进图) + G-3 (UDP table 可视化) —
   tasks/L2_gate_primitive_support.md (G-1 ✅ iter_115)
2. iter_121 补丁 semantic 消歧重构 (syntax 取标识符 + symbol kind 消歧) —
   见决策文档 D3 (业务改善信号触发)
3. slang generate-entry 合并枚举观察 (iter_119 记录)
4. A2 位对位折算 (总线粒度 → 位粒度跨实例桥) — 审计文档后续项
5. inout 双向多驱动归属 (i2c 开漏: 外部+实例同时驱动哪边算源) —
   iter_129 单向链已通, 多驱动归属专项
6. interface master+slave 同线多写共享语义 (多实例同时驱动 interface 成员
   的归属/合并) — iter_129 成员桥已建, 共享语义专项
7. cvfpu 全量覆盖 (vendor common_cells + PACE override) — 家族已由 fpnew 覆盖, 低优先
## ✅ 最近完成 (保留 3 条汇总, 逐项细节看 git log + docs/task_tree/iterations/)

| 完成时间 | 任务 | 产出 |
|---|---|---|
| **2026-09-05** | **嵌套 generate 假节点清理 (iter_134)** | gen_block 直接宿主判定修深层嵌套假路径 (aes 279/1116→0, cordic 105→0); wrapper cross get_edges + PORT_OUT 自递归连带修; unit +3; 全量 **2937 passed**. [iter_134](docs/task_tree/iterations/iter_134_nested_gen_dup_cleanup.md) |
| **2026-09-05** | **iter_131/132 真实复验 (iter_133)** | aes 4834 节点/272 实例复验: fanin 位隔离零跨 entry; dataflow 已知限制区分; 暴露嵌套 generate 深层重复段假节点 (351/4834, baseline 既有) 登记 audit backlog. [iter_133](docs/task_tree/iterations/iter_133_real_verify.md) |
| **2026-09-05** | **generate per-entry fanin 位隔离 (iter_132)** | fanin(top.y[3]) 串入 G[0..2] 双根因: A2 提升忽略 incoming CONNECTION + wrapper cross 无条件跨; 修后 y[i] fanin 恰 [G[i].u_leaf.y]; bus 聚合/纯直通/xor/wrapper 全保; unit +3; 全量 **2934 passed**. [iter_132](docs/task_tree/iterations/iter_132_genfor_fanin_isolation.md) |
| **2026-09-04** | **dataflow bus 聚合修复 + usage 债务清理 (iter_131)** | 真回归: _find_paths 首个非空候选组合即返 (iter_118 per-entry 后 bus 查询丢位, arbiter 40→8→1) → 合并所有候选组合, 8 paths 恢复; golden 40→8; 3 测试债务 (p6/m12/factory) 清理; unit +3; 主全量 2928 passed. [iter_131](docs/task_tree/iterations/iter_131_dataflow_bus_agg_fix.md) |
| **2026-09-04** | **inout + interface 建模 (iter_129)** | inout 跨模块连接修复 (connection_extractor inout 分支, output 式同线 CONNECTION, fanin 穿透实例三态链); interface 成员级桥 (收集 InterfacePortSymbol links + 后处理按驱动方向单向桥) + A2 提升目标限 data 类消假驱动; unit +7; 全量 **2928 passed**. [iter_129](docs/task_tree/iterations/iter_129_iface_inout_modeling.md) |
| **2026-09-04** | **审计待验证候选实测 (iter_128)** | 5 候选实测: 修 fanin CLOCK/RESET 假驱动 (跨模块时钟链) + A2 位提升条件双修 (struct 字段泄漏/位选 seen 污染); 登记 inout 跨模块连接 + interface 成员级缺口 (建模待拍板); 顶层输入空 fanin 预期锁定; unit +8; 全量 **2921 passed**. [iter_128](docs/task_tree/iterations/iter_128_audit_candidates_verify.md) |
| **2026-09-04** | **准确性审计 A3 修复 (iter_127)** | 实例输出端口 internal DRIVER 自环不计为 fanin 驱动源: 查询层 (主循环 + _find_drivers depth=1) 跳过 assign_type="internal" 自环, nonblocking 真自环 (state<=state+1) 保留; 图结构不改; unit +4; 全量 **2913 passed / 0 failed**. [iter_127](docs/task_tree/iterations/iter_127_accuracy_a3.md) |
| **2026-09-04** | **准确性审计 A1/A2 修复 (iter_126)** | A1 收窄: 库默认保留无 target 类型级契约 (8 回归恢复), CLI visualize 入口 (build_viz_tracer 无 --module) 自动单 top target — cordic 365→542 节点 genblk 内部真实 assign 恢复; A2 总线直连位查询提升非空; A1 测试弱断言 (self-loop) 重写为非自环; 全量 **2913 passed / 0 failed**. [iter_126](docs/task_tree/iterations/iter_126_accuracy_a1_a2.md) |
| **2026-09-02** | **测试资产扩充 + 缺陷修复收尾 (iter_086~108)** | truth 层 32→130 测试 (T1-T12 扩充 + A-F 修复断言); 缺陷 A-F (expression 字节切片 / net-decl 位宽 / LHS concat zip / ternary 常量 / part-select 宽度 / generate-if always) + ELK dangling + #23/#24 generate 单块 wire 全修; integration 419+0 历史首次全绿; 全量 2843 passed. 迭代记录 iter_086~108 |
| **2026-09-02** | **Truth 层扩充 T1-T12** | 12 文件 + 5 fixture, 集合相等断言; assign/clock-reset/case/位选/concat/function-task/parameter/alias/class/generate-if-case/SVG 布局/查询精确集. [iter_100 汇总](docs/task_tree/iterations/iter_100_t1_t12_wrapup.md) |
| **2026-09-02** | **B 组复查 + cli 3 失败修复** | iter_082 误分类纠正 (darkriscv SVG 断言 + 删 --no-strict); models.py width=None 序列化根因; unit+cli 1484 passed. [iter_086](docs/task_tree/iterations/iter_086_group_b_recheck_real_project_viz.md) / [iter_087](docs/task_tree/iterations/iter_087_cli_3_failures_fix.md) |

---

## 📋 下一个候选 (未启动, 不要自己开工 — 先问方豆)

- **工业算法模块开源项目调研** (进行中, 不在本任务内推进): 典型工业算法模块
  (CORDIC / 加法器族 / 乘法器族 / DSP 算法) 开源 RTL 摸底已 clone 至 `~/my_dv_proj/openrtl/`,
  REPOS.md 统一登记; 摸底缺口 → 逐个修复 (CORDIC iter_109~111, gate primitive 本任务)。
  剩余: fpnew/hardware/cvfpu 扫尾。
- ~~#7 — 迁 pyslang 11.0 native API~~ ✅ **已完成** (2026-08-29, iter_053-059)。
  遗留: CVA6/coralNPU/vortex 3 项目 strict 编译受阻 (pyslang↔项目语义不兼容),
  见 ARCHITECTURE_TODOLIST §#7。

---

## 📝 维护说明

1. **同时只有 1 个"当前任务"** — 多任务并行是错觉, 会导致两边都做不完
2. **切换任务前**, 把当前任务移到"已启动但暂停", 写清楚下一步是什么
3. **任务完成后**: 写 `docs/task_tree/iterations/iter_NNN_*.md` → 更新长期 todolist → 移到"最近完成"
4. **阻塞时必须写明**: 阻塞在什么、需要谁决策、有哪些选项和代价
5. **本文件必须和实际工作同步更新** — 文档更新和实际工作同等重要。
   任务开始前设为当前任务, 进行中逐项勾选, 完成后立即清出。
   完成判定 = **代码 ✅ + 测试 ✅ + 文档 ✅**, 只写完代码不算完成。
   详见 `AGENTS.md` → "📓 开发日志与迭代记录 → 任务前后必须更新文档"
