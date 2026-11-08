# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **可视化计划**: [structural_review_plan_2026-11-02](docs/architecture/structural_review_plan_2026-11-02.md) — 全设计图退役；动态子图 + 局部 review。
> **最后更新**: 2026-11-08 GMT+8 (iter_420: fresh blind 10/10)

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
- **P84** constraint/mux 邻域场景 ✅（iter_388）
- **P85** neighborhood source/T2 pilot ✅（iter_389）
- **P86** 统一双评分 ✅（iter_390）
- **P87** 12-task fixed protocol ✅（iter_391）
- **P88** 外部 VeriBug 验证 ⏭️ 放弃（成本/环境）
- **P89** 最终验证摘要 ✅（iter_392）
- **P90** agent 查询成本归因 ✅（iter_393）；session telemetry 修正 ✅（iter_394）
- **P91** 大 filelist top-aware 裁剪 ✅（iter_395）；fallback ✅
- **P92** snapshot 预构建 D ✅（iter_396）
- **P93** A/D 充分测试 ✅（iter_397）
- **P94** A+D vs 原版模型对比 ✅（iter_398）
- **P95** 严格 A/D agent 协议 ⏭️ 放弃（无法强制工具使用）
- **P96** sv_query skill pilot ✅（iter_400）：模型未加载 skill，无收益
- **P97** inline skill prompt pilot ✅（iter_401）：无稳定收益
- **P98** 受限 svq_query 工具 ✅（iter_403）：48/48，MiniMax 9.0s / DeepSeek 4.7s
- **P99** Worker 辅助工具硬化 ✅（iter_404）：compact.js + 12 Node tests
- **P100** svq_query details + neighborhood ✅（iter_406）
- **P101** neighborhood condition schema ✅（iter_407）
- **P102** Worker 辅助 BFS 测试 ✅（iter_408）
- **P103** deep_chain tool probe ✅（负结果）
- **P104** granular path ✅（iter_410）：deep 除 xor 外正确
- **P105** evidence intent ✅（iter_411）：deep 7/7
- **P106** evidence 默认关闭回归 ✅（iter_412）：24/24
- **P107** Worker evidence tests ✅（36 Node tests）
- **P108** evidence 成本 ✅（+2.1%）
- **P109** 默认决策 ✅（opt-in）
- **P110** Blind realistic validation ✅：fresh 9/10，false-confident 0
- **P111** Snapshot/evidence 一键化 ✅：新 snapshot 10/10
- **P112** unknown/abstention 合同 ✅：空 vs not_found 分离
- **P113** contract regression ✅：10/10，false-found 0
- **P114** fresh untouched blind ✅：10/10，false 0

> P71/P72 已完成；P62.2 交互式 debug 保持 gate；外部 VeriBug 明确 deferred/放弃。

---

## 📦 仓库状态

- **分支**: `main`；最新提交以 `git log -1` 为准
- **全量基线**: **2571 passed / 0 failed**（`sim/tests/`, `-m "not opensource"`；
  7 skipped / 119 deselected；iter_397 实测）
- **命令面**: 40 命令 = core 36 + exp 4（class/constraint/covergroup）
- **当前重点**: 收尾；成本归因显示模型生成主导（P90）

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
