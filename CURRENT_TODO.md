# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **可视化计划**: [structural_review_plan_2026-11-02](docs/architecture/structural_review_plan_2026-11-02.md) — 全设计图退役；动态子图 + 局部 review。
> **最后更新**: 2026-11-06 GMT+8 (iter_383: P1 stability)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P62.2 交互式 debug（gate）** `<待做>`
- **P63** class / constraint / covergroup 语义增强 ✅（iter_365）
- **P64** constraint 继承链 + rand 标记 ✅（iter_366）
- **P65** UVM sequence/factory 静态关系 ✅（iter_367）
- **P66** 语义提取 regex 纪律（仅 UVM 宏例外）✅（iter_368）
- **P67** 可用性验证包：性能 + 反幻觉 walkthrough ✅（iter_369）
- **P68** README 项目描述校准 ✅（iter_370）
- **P69** 长程结构查询对照基准 ⏳（P69.7 全矩阵待环境）
- **P71** agent 查询可靠性修复 ✅（iter_376）
- **P72** filelist 编译失败分类 ✅（iter_377）
- **P73** 项目目标/计划/测试缺口审计 ✅（iter_378）
- **P74** 交互式 debug 场景 pilot ✅（iter_379）
- **P75** covergroup bin_details ✅
- **P76** interactive debug 后续修复 ✅（iter_380）
- **P77** port-map ternary expression 子图 ✅（iter_381）
- **P78** P0 deep_chain 行为验证 ✅（iter_382）
- **P79** P1 稳定性 ✅（iter_383）
- **P80** 实验资产盘点 ✅（iter_384）
- **P81** long-range 统一 runner ✅（iter_385）
- **P82** 4-task pilot ✅（iter_386）
- **P83** long-range 查询协议修复 ✅（iter_387）

> P71/P72 已完成；P62.2 交互式 debug 保持 gate；P69.7 全矩阵待环境。

---

## 📦 仓库状态

- **分支**: `main`；最新提交以 `git log -1` 为准
- **全量基线**: **2548 passed / 0 failed**（`sim/tests/`, `-m "not opensource"`；
  7 skipped / 119 deselected；iter_387 实测）
- **命令面**: 39 命令 = core 35 + exp 4（class/constraint/covergroup）
- **当前重点**: 审计结论是“功能已够用”；下一步外部小样本验证，其次 warm query service

---

## ✅ 最近完成（P63~P73）

| 迭代 | 内容 | 结果 |
|---|---|---|
| iter_365 | class/constraint/covergroup CLI | ✅ |
| iter_366 | constraint 继承链 + rand 标记 | ✅ |
| iter_367 | UVM sequence/factory 静态关系 | ✅ |
| iter_368 | 语义提取 regex 纪律 | ✅ |
| iter_369 | 性能基准 + CDC walkthrough | ✅ |
| iter_370 | README 项目描述校准 | ✅ |
| iter_371~375 | 12-task 对照 + seed2 + 硬隔离 PoC | ⏳ P69.7 全矩阵待环境 |
| iter_376 | --top / driver_count / bit_fallback | ✅ |
| iter_377 | filelist 编译错误分类 | ✅ |
| iter_378 | 项目目标/计划/测试缺口审计 | ✅ |

---

## 🔜 下一步（审计结论）

1. **外部小样本验证**：没有远程 Linux/Docker，优先 VeriBugBench Icarus 10–15 例；
2. **warm query service**：仅在外部 benchmark 显示多轮查询后进行；
3. **文档/测试债**：刷新 TESTING / EXTRACTION_COVERAGE / KNOWN_LIMITATIONS。

详见 [项目审计](docs/architecture/project_audit_2026-11-06.md)。
