# CURRENT_TODO — 当前正在做的事

> **唯一入口**: 本文件是"此刻在做什么"的**唯一稳定追踪点**。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-09-02 GMT+8 (测试资产与缺陷修复归档; 下一步: 工业算法模块调研)

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

**(无 — 2026-09-02 测试资产与缺陷修复工作已全部完成并归档, 见下方最近完成;
下一步方向: 工业算法模块开源项目调研, 见"下一个候选")**

## ✅ 最近完成 (保留 3 条汇总, 逐项细节看 git log + docs/task_tree/iterations/)

| 完成时间 | 任务 | 产出 |
|---|---|---|
| **2026-09-02** | **测试资产扩充 + 缺陷修复收尾 (iter_086~108)** | truth 层 32→130 测试 (T1-T12 扩充 + A-F 修复断言); 缺陷 A-F (expression 字节切片 / net-decl 位宽 / LHS concat zip / ternary 常量 / part-select 宽度 / generate-if always) + ELK dangling + #23/#24 generate 单块 wire 全修; integration 419+0 历史首次全绿; 全量 2843 passed. 迭代记录 iter_086~108 |
| **2026-09-02** | **Truth 层扩充 T1-T12** | 12 文件 + 5 fixture, 集合相等断言; assign/clock-reset/case/位选/concat/function-task/parameter/alias/class/generate-if-case/SVG 布局/查询精确集. [iter_100 汇总](docs/task_tree/iterations/iter_100_t1_t12_wrapup.md) |
| **2026-09-02** | **B 组复查 + cli 3 失败修复** | iter_082 误分类纠正 (darkriscv SVG 断言 + 删 --no-strict); models.py width=None 序列化根因; unit+cli 1484 passed. [iter_086](docs/task_tree/iterations/iter_086_group_b_recheck_real_project_viz.md) / [iter_087](docs/task_tree/iterations/iter_087_cli_3_failures_fix.md) |

---

## 📋 下一个候选 (未启动, 不要自己开工 — 先问方豆)

- **工业算法模块开源项目调研** (方豆 2026-09-02 计划): 找典型工业算法模块
  (CORDIC / 加法器族 / 乘法器族 / 同级别 DSP 算法) 的开源 RTL 项目,
  作为 sv_query 之后的潜在测试项目。调研结果待记录 (候选清单)。
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
