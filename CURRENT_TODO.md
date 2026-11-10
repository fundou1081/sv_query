# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **可视化计划**: [structural_review_plan_2026-11-02](docs/architecture/structural_review_plan_2026-11-02.md) — 全设计图退役；动态子图 + 局部 review。
> **最后更新**: 2026-11-09 GMT+8 (P139 frontier)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P62.2 交互式 debug（gate）** `<待做>`（deferred；无活跃开发）
- **P126** 文档/运维刷新 ✅（iter_433）
  - P126.1 CURRENT_TODO 刷新 ✅
  - P126.2 TESTING 刷新 ✅
  - P126.3 EXTRACTION_COVERAGE / KNOWN_LIMITATIONS 刷新 ✅

### 长期挂起 / 已放弃（不再作为"下一步"）

| 项 | 状态 | 原因 |
|---|---|---|
| P62.2 交互式 debug | `<待做>`（**保持 gate**） | 不是核心 query/verify；保持 gate，不主动排期 |
| P69.7 硬隔离 12×2 fixed 全矩阵 | `<放弃>` | 环境成本高，产品问题未定 |
| P88 外部 VeriBug 验证 | `<放弃>` | 成本/环境；已改用 OpenTitan 真实 block + independent intake 替代 |

---

## 📦 仓库状态

- **分支**: `main`；最新提交以 `git log -1` 为准
- **全量基线**: 见 [docs/INDEX.md 当前基线](docs/INDEX.md#-当前基线-单一真相源--计数只写在这里)（单一真相源，本文不写死计数）
- **命令面**: 43 命令 = core 38 + exp 5（class/constraint/covergroup/architecture）
- **当前重点**: 文档/运维刷新完成（P126）；核心 query/verify 已在真实项目闭环，下一步不是加功能

---

## ✅ 最近完成（P124~P126）

| 项 | 内容 | 结果 |
|---|---|---|
| P124 | Independent task intake（worker） | 从 OpenTitan DV testplan/checklist 提取 3 个任务 + 人工 ground truth |
| P125 | 执行 independent intake 任务 | 6/6 exact；0 false-confident；0 false-found；结论：核心 query/verify 已够，不加 search |
| P126 | 文档/运维刷新 | CURRENT_TODO / TESTING / EXTRACTION_COVERAGE / KNOWN_LIMITATIONS 刷新；check_docs/check_plan 通过 |
| P127 | 两个新增 DV 任务 | 初次 2/4；T1 alias schema 修正后 4/4；0 false |
| P128 | Freeze v0.3.0-agent-query | tagged baseline；规则见 freeze doc |
| P129 | clean-clone smoke | tag checkout + docs/plan + Node + snapshot/query/verify |
| P130 | 长任务回归 + TB 角调查 | 12 tasks 24/24；TB 候选 2/3 层可答，coverage 阻塞 |
| P131 | coverage limitation schema | 保持严格；schema 标注 pyslang 限制 + 源码位置 |
| P132 | constraint neighborhood | 跨 block 变量关系图 + 重要度指标 |
| P133 | architecture graph | 模块实例级真实 net 连接图 + SVG |
| P134 | real-use pilot | 3 场景；verify 生产级；FIFO 跨边界断链 |
| P135 | FIFO/bus connectivity | 父总线聚合；FIFO 边 + `--through-fifo`；I2C 端到端通过 |
| P136.1 | false missing-file warning | source-known 判定；I2C warning=0 |
| P136.2 | architecture snapshot | `--from-snapshot`；5/37/189 |
| P136.3 | TB→RTL join | `trace tb-join`；candidate/multiple_candidates 显式 |
| P136.4 | unknown machine flag | `machine.unknown_kind`；verified/contradicted 不变 |
| P136.5 | solve/dist extraction | `solve_before` + `dist` schema |
| P137 | discipline remediation | 门禁恢复；F1–F15 |
| P138 | project adaptation policy | 删除自动 FIFO 推断；外部 adapter 模板 |
| P139 | boundary-aware guided trace | `trace frontier`；不分类 FIFO |

详见 [P125 intake results](docs/validation/OPENTITAN_INTAKE_RESULTS_2026-11-09.md)。

---

## 📌 上一阶段已完成主线（摘要，详见 PLAN.md）

| 阶段 | 内容 | 结果 |
|---|---|---|
| P118~P120 | OpenTitan UART 首个真实 block + edge evidence 修复 + answer schema | 建图成功；edge evidence 缺口已修；T5 schema 固定 |
| P121~P123 | 连续 run + canonical path + I2C 第二 block | canonical path 成立；I2C 建图成功 |
| P98~P117 | 受限工具化与盲测 | 工具调用闭环；false-confident 0 / false-found 0；unknown/abstain 合同分离 |

---

## 🔜 当前状态

**无活跃开发 item**。P126 文档刷新已完成，P125 intake 6/6 通过。

下一阶段按 [待做盘点](docs/architecture/PENDING_INVENTORY_2026-11-09.md) 的优先级决定；
当前不自动开新功能。计数只写在 [docs/INDEX.md 当前基线](docs/INDEX.md#-当前基线-单一真相源--计数只写在这里)。
