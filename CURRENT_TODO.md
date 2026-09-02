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

**门级原语 (Gate Primitive) 提取支持 — leaf cell 建模** (✅ 完成, iter_112)
> KoggeStone 摸底缺口: xor16.S[0..15] 全无 DRIVER + and/xor 触发 connection 无限递归
> (`and0.and0...` ×21)。方案 A: 原语建模为 leaf cell。
> [iter_112](docs/task_tree/iterations/iter_112_gate_primitive_support.md) / [任务文件](docs/task_tree/tasks/L2_gate_primitive_support.md)

| sub-task | 状态 |
|---|---|
| 1. adapter 层过滤 PrimitiveInstance (native/recursive 同步, parity 不破) | ✅ |
| 2. DriverExtractor: 原语输出 DRIVER 边 (输入端子→输出, 位选宿主作用域解析) | ✅ |
| 3. ConnectionExtractor: 不展开原语 + get_path 防自环兜底 | ✅ |
| 4. 测试: unit test_gate_primitive (8) + truth test_gate_primitive_truth (6, golden_dataflow_40 = 真实 xor16.v) | ✅ 14 passed |
| 5. 回归: **2869 passed / 0 failed / 7 skipped** (基线 2849 无损) + KoggeStone xor16.S/xor16_1.S 全部可达驱动 | ✅ |
| 6. 文档: iter_112 + iter_111 补记 + overview (rows 30-33) + 本表 | ✅ |

**当前**: ✅ **CLA 嵌套 generate 实例缺口修复完成** (iter_113, 方豆 "修这个新发现的generate")
> [iter_113](docs/task_tree/iterations/iter_113_cla_nested_generate_fix.md) /
> [任务文件](docs/task_tree/tasks/L2_cla_nested_generate_fix.md)
> 双根因: ① graph_builder.walk 不下钻 generate (driver paths 无 generate 实例 —
> cordic 同受其害, "rotator DRIVER 100" 实为 connection 端口自环) → walk 用
> child.hierarchicalPath 下钻; ② connection inst_module_name 在 inst==type 时回落
> parent → 自环递归 (iter_112 原语同根因型) → type token 权威, 去 '!= inst_name' 守卫。
> 验证: 合成复现两命名风格 recursive=0 + 内部 DRIVER 全提取; 真实 CLA
> (golden_dataflow_41, inst==type 真身) generators[0..3] 内部逻辑可达。

| sub-task | 状态 |
|---|---|
| 1. 诊断: 双根因定位 (walk 不下钻 + inst_module_name 回落) | ✅ |
| 2. 修根因: walk hp 下钻 + connection type token 权威 | ✅ |
| 3. 测试: unit test_nested_generate_instance (4) + truth test_cla_generate_truth (6, 真实 CLA fixture) | ✅ 10 passed |
| 4. 回归: 受影响 47 passed 零回归; 全量结果见 commit | ✅ |

**backlog (未启动)**: 1. gate 遗留改进 G-1~G-3 (端子方向 ports[].direction / drive strength+delay / UDP table) — tasks/L2_gate_primitive_support.md; 2. cvfpu 全量覆盖 (vendor common_cells + PACE override) — 家族已由 fpnew 覆盖, 低优先

**backlog (未启动)**: 2. gate 遗留改进 G-1~G-3 (端子方向 ports[].direction / drive strength+delay / UDP table) — tasks/L2_gate_primitive_support.md; 3. cvfpu 全量覆盖 (vendor common_cells + PACE override) — 家族已由 fpnew 覆盖, 低优先

## ✅ 最近完成 (保留 3 条汇总, 逐项细节看 git log + docs/task_tree/iterations/)

| 完成时间 | 任务 | 产出 |
|---|---|---|
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
