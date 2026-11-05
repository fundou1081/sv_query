# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **可视化计划**: [structural_review_plan_2026-11-02](docs/architecture/structural_review_plan_2026-11-02.md) — 全设计图退役；动态子图 + 局部 review。
> **最后更新**: 2026-11-04 GMT+8 (iter_370: README 项目描述校准)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P69.6 多 seed + source 完全隔离** `<待做>`
- **P63** class / constraint / covergroup 语义增强 ✅（iter_365）
- **P64** constraint 继承链 + rand 标记 ✅（iter_366）
- **P65** UVM sequence/factory 静态关系 ✅（iter_367）
- **P66** 语义提取 regex 纪律（仅 UVM 宏例外）✅（iter_368）
- **P67** 可用性验证包：性能 + 反幻觉 walkthrough ✅（iter_369）
- **P68** README 项目描述校准 ✅（iter_370）
- **P69** 长程结构查询对照基准：12 题 + token/tool-call 完成；待多 seed/完全隔离

> P67/P68 已完成；P62.2 交互式 debug 保持 gate。

---

## 📦 仓库状态

- **分支**: `main`；最新提交以 `git log -1` 为准
- **全量基线**: **2529 passed / 0 failed**（`sim/tests/`, `-m "not opensource"`；
  7 skipped / 119 deselected；iter_369 实测）
- **命令面**: 39 命令 = core 35 + exp 4（class/constraint/covergroup）
- **当前重点**: README 已校准；P67 性能/walkthrough 已交付；下一步再评估 HWE/VeriBug 对照环境

---

## ✅ 最近完成（P50~P57）

| 迭代 | 内容 | 结果 |
|---|---|---|
| iter_351 | bit-level consistency | parent/range/width/edge 检查 |
| iter_352 | indexed part-select / multi-top / direct-edge | 越界 269→12 |
| iter_353 | parent width 元数据 | VariableSymbol width + 实例传播；三项目 pass |
| iter_354 | 取实例 width | 实例 body/port 优先，parameter 正确 |
| iter_355 | generate parameter width | generate-for 参数特化验证 |
| iter_356 | generate if/case | 活跃分支 width / inactive 不建节点 |
| iter_357 | generate 嵌套 generate-for | 嵌套 if/case 覆盖 |
| iter_358 | ub-mode 纪律合并 | 复杂度棘轮 + 术语表（非可视化） |

---

## 🔜 P59 清理清单（下一步）

1. 盘点 `visualize` / `arch` / `design` / VizData / ELK / 旧 DOT / 文档 / 测试；
2. 每项标 keep/archive/delete；
3. 先冻结全设计图命令，跑全量；
4. 删除/归档与 review 无关资产；
5. 更新 registry / capabilities / docs / tests；
6. 全量 + 真实项目 smoke 0 failed。

详见 [P59 任务](docs/task_tree/tasks/L2_visual_cleanup.md) 与计划 §8。
