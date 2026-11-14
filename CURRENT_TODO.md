# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **交接状态**: [docs/dev/HANDOFF.md](docs/dev/HANDOFF.md) — 剩余工作、环境、worker 协议；
> [会话交接快照](docs/dev/HANDOFF_2026-11-12.md) — 本次会话交付、设计裁决、待拍板、踩坑。
> **最后更新**: 2026-11-14 10:10 GMT+8 (交接文档就绪)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P171.4.2 full fanin/fanout merge** `<待做>`
  - 剩余：P171.4.2 full merge（已尝试回退）；opensource 112/11/0
  - 待方豆确认（不阻塞）：`false_confident` 分母口径当前默认
    = answered_n（实际作答数），见 [REPORT_STATUS](docs/dev/REPORT_STATUS.md)

### 已完成（本轮 P158.12.6，iter_495）

- **7 类状态统一**：`tools/report_status.py` 分类 passed / failed / unknown /
  truncated / unexecuted / skipped_with_reason / external_not_run；
  canonical+opensource 合并视图与 VERDICT（"只看 failed 数不代表全绿"）
- **分母语义**：`false_confident` 分母 = answered_n；`score_long_range.py`
  summary 暴露 statuses + 新分母；真实历史数据兼容验证通过
- **口径文档**：`docs/dev/REPORT_STATUS.md`（已登记 INDEX）；机械 gate 8 项

### 已完成（本轮 P158.12.2~12.5，iter_494）

- **12.2 硬编码路径清零**：26 个测试文件 → 仓库相对推导 +
  `SVQ_OPENRTL_ROOT`（默认 `~/my_dv_proj/openrtl`）+ 缺失显式 skip
  （实测 `/nonexistent` → 14 skipped 0 failed）
- **12.3 no:randomly**：pytest-randomly 5.1.0 入 dev 依赖，addopts 默认禁用随机；
  auto-bless 核查为非问题（graph_snapshot 本就显式拒绝）
- **12.4 空 expression 自环清除（R-026）**：connection_extractor 对实例 output port
  恒加同串自环边（408 条模式）→ 跳过；真实自依赖不受影响；
  `test_p158_12_selfloop.py` 4 项回归；**golden fanin_2signals 重生成
  （cycles_detected true→false，原 true 即假自环伪装）**；
  drivers_dominate 阈值 30%→25%（原值靠假自环虚增）
- **12.5 R-027 最小面**：benchmark runner task 异常留行计数（rc=130 + task_error），
  不再让单任务异常挂整轮

### 长期挂起 / 已放弃（不再作为"下一步"）

| 项 | 状态 | 原因 |
|---|---|---|
| P62.2 交互式 debug | `<待做>`（**保持 gate**） | 不是核心 query/verify；保持 gate，不主动排期 |
| P69.7 硬隔离 12×2 fixed 全矩阵 | `<放弃>` | 环境成本高，产品问题未定 |
| P88 外部 VeriBug 验证 | `<放弃>` | 成本/环境；已用 OpenTitan 真实 block + independent intake 替代 |

---

## 📦 仓库状态

- **分支**: `main`；HEAD 以 `git log -1` 为准（不要依赖文档里的哈希）
- **全量基线**: 见 [docs/INDEX.md 当前基线](docs/INDEX.md#-当前基线-单一真相源--计数只写在这里)（单一真相源，本文不写死计数）
- **命令面**: 45 命令 = core 39 + exp 6（audit / diagnose / trace overview / review render / architecture graph /
  trace impact——**2026-11-11 降级**：未标定启发式不得伪装稳定，见 KNOWN_LIMITATIONS §3.4）
- **环境**: `python3` 必须是装了 typer/pyslang 的解释器（本机 `~/miniconda3/bin/python3`），
  否则 CLI 子进程测试会成片假失败；外部 corpus 在 `SVQ_OPENRTL_ROOT`
  （默认 `~/my_dv_proj/openrtl`），缺失时相关测试显式 skip
- **当前重点**: P158.12.6 已完成（7 类状态口径统一）；下一步 P158.12.7 skills 文档漂移

---

## ✅ 最近完成

| 项 | 内容 | 结果 |
|---|---|---|
| P158.11.2b | 通用长查询 timeout（iter_491） | SearchBudget 唯一实现；dataflow 有界 DFS + CLI 预算参数 + truncated 契约 |
| P164 | 文档状态校准（接手） | PLAN/CURRENT_TODO/HANDOFF/契约/基线/限制对齐；check_plan + check_docs 加固 |
| P162/P163 | 交接文档 + 会话记录 | 可交接、可追溯 |
| P160/P161 | opensource 分诊与修复 | 38 failed → 0 failed；17 个显式 skip |
| P158.1~11.2a | 语义契约波次 1~3 | 数据边/有界/确定性/corpus/写入/verified/snapshot/MIG/CI |
| P152/P153/P155/P156 | SPI 收口 | 9-task corpus；transitive fanin；reciprocity 误报 128→0 |

详见 [PLAN.md](PLAN.md)、[P158 remediation](docs/validation/P158_REMEDIATION_2026-11-11.md)、
[P161 remediation](docs/validation/P161_OPENSOURCE_REMEDIATION_2026-11-11.md)。

---

## 🔜 下一步（按顺序，未开工）

```text
1. P158.12.7  skills 文档漂移（按 39+6 命令面校正）  <- 当前 item
2. 9 个 opensource skip 的最终处置（归档 retired exp / 补 fixture / 保留显式 skip）
3. P165.1     signal.py 全图扫描 pred/succ 化（O(V×E)→O(度)，小改动）
4. P165.3/4   外部故障集 + filelist 闭包自动化（开源前）
5. P165.2     packaging 重命名（随开源破坏性窗口）
```

未决讨论项（等方豆拍板）：真实项目依赖闭包是否固化进 repo。
已拍板（2026-11-11）：`trace impact` 降 exp（已落地，P158.12.1）；方案 B 拒绝、方案 C 暂缓（见 PLAN P165）。
