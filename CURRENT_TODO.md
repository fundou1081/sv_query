# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **可视化计划**: [structural_review_plan_2026-11-02](docs/architecture/structural_review_plan_2026-11-02.md) — 全设计图退役；动态子图 + 局部 review。
> **最后更新**: 2026-11-03 GMT+8 (iter_364: P62.1 review artifact 完成)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P62.2 交互式 debug（gate）** `<待做>`
- **P58** 可视化重定位计划 ✅（iter_359）
- **P59** 旧可视化资产清理：✅ 盘点/冻结 → ✅ 删除/归档 → ✅ 文档/测试/registry 收口
- **P60** `graph subgraph` core ✅（iter_362）
- **P61** `verify structural` findings（symmetry.port_set）✅（iter_363）
- **P62.1** 局部 review artifact ✅（iter_364）；**P62.2** 交互式 debug gate（待评估）

> **P61 已完成**；下一步 P62 局部 review artifact。

---

## 📦 仓库状态

- **分支**: `main`；最新提交以 `git log -1` 为准
- **全量基线**: **2518 passed / 0 failed**（`sim/tests/`, `-m "not opensource"`；
  7 skipped / 119 deselected；iter_365 实测）
- **命令面**: 39 命令 = core 35 + exp 4（class/constraint/covergroup）
- **当前重点**: 先清理旧可视化，再开发动态子图/结构审查

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
