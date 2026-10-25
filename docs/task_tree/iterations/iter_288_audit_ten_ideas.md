# Iteration 288: exp 10 条创意落地为 `svq audit`（PLAN P3.3）

**Metadata**:
- **Iteration #**: 288
- **Task Tree Level**: L2（PLAN `P3.3`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续吧，都做完。不要妥协，不要跳过。有些测试可能有问题，注意分辨。"）
- **Outcome**: ✅ 完成（10 条创意 → 1 个只读命令的 10 个检查；16 个新测试；2377 passed）

## 🎯 背景

`docs/EXP_IDEAS.md` 的 10 条创意当年被整体砍掉，理由是"demo 级、语义未锁定、输出可能错"。
本次**重新设计**，不是搬回旧代码。

## 🔧 设计原则（对应当年砍掉的原因）

| 当年问题 | 现在的做法 |
|---|---|
| 输出像"结论"，错了也看不出 | 每条检查带 `confidence`：`pattern` / `measured` / `heuristic` |
| 语义未锁定 | 每条检查写成**独立函数**，`sim/tests/regression/test_audit_checks.py` 锁定可观察输出 |
| 命令多、难记 | **一个命令** `svq audit`，`--checks` 选子集；agent 一次调用拿全量结构化结果 |
| 启发式冒充事实 | 启发式结果用 `candidates` / `suggested` 措辞；文档写明"不保证" |

## 📋 10 条创意 → 检查项

| # | 原创意 | 检查项 | 数据来源 | 置信度 |
|---|---|---|---|---|
| 1 | 总线协议识别 | `protocols` | 实例端口名模式（AXI4/AXIS/APB/AHB/Wishbone/TileLink） | pattern |
| 2 | valid/ready 握手对 | `handshakes` | 端口配对 + 图可达性（谁依赖谁） | heuristic |
| 3 | 反压/死锁候选 | `backpressure_cycles` | ready 依赖图找简单环（限长 6） | heuristic |
| 4 | SVA 抽取/覆盖 | `assertions` | `SVAExtractor` 的 assertions + signal_refs | measured |
| 5 | 覆盖缺口 + 生成 covergroup | `coverage` | `CovergroupExtractor` + 缺口建议片段（不落盘） | measured |
| 6 | 验证缺口报告 | `verification_gaps` | 关键信号（clk/rst/valid/ready）× 断言 × 覆盖 × 负载数 | measured |
| 7 | 改动风险分级 | `risk` | 角色权重 × log(1+入边+出边) | heuristic |
| 8 | 约束/随机化可达性 | `constraints` | rand 声明 + constraint 块提及（**不做可达性求解**） | pattern |
| 9 | CDC | `cdc` | `clock_domain` 沿 CONNECTION 传播 2 跳 + 同步器名称提示 | heuristic |
| 10 | 时序关键路径 | `timing` | 组合边最长链 DP（排除时钟/复位/自环） | heuristic |

> #8 明确只做"约束覆盖统计"，不做可达性求解（静态不可判定）——在输出 note 与文档里写明。

## 🧪 测试（16 个新增）

`sim/tests/regression/test_audit_checks.py`（14）+ `test_check_plan.py`（+2）：

- 协议识别：AXI4 从设备被识别，端口命中率
- 握手：`awready = ~awvalid` → `ready_depends_on_valid`
- 反压：本 fixture 无环 → 空
- 断言/覆盖：SVA 计数、covergroup 计数、建议片段存在
- 缺口：时钟/valid 被列出，且要求 loads ≥ 2（防噪声）
- 风险：时钟类排最前，时钟分数 > 数据分数
- 约束：`rand bit [7:0] addr` 解析正确，`data` 无约束被标出
- CDC：clk_a→clk_b 候选，`has_sync_hint=False`
- 时序：链长 ≥ 3 且无重复节点（自环已排除）
- 选择/未知检查：`--checks` 子集、非法名报错
- CLI JSON 形状

## 🐛 过程中修的两个实现问题

| # | 问题 | 现修 |
|---|---|---|
| 1 | CDC 首版只看节点自身边上的 `clock_domain` → 全空 | 域值沿 CONNECTION **双向传播 2 跳**，同一网络节点出现 ≥2 域才算候选 |
| 2 | `rand bit [7:0] addr;` 正则漏匹配（`bit` 后的位宽没吃） | 重写 `_RAND_RE` 覆盖 `rand/randc + 类型 + 位宽 + 变量` |

## 📊 量化

| 指标 | 值 |
|---|---|
| 命令数 | 34 → **35**（`audit` 进 core/semantic） |
| 全量门禁 | **2377 passed / 0 failed**（+16） |
| 新代码 | `analysis/audit.py` ~560 行 + CLI 100 行 |
| 检查耗时 | 小 fixture < 0.2s（SVA/covergroup 各编译一次，已复用 compiler 给 coverage） |

## 💡 与 `trace impact` 的关系

`trace impact` 的风险分（`risk_model=heuristic_v1`）是**改动影响面**；
`audit risk` 是**信号关键度**（时钟/复位/握手优先），两者互补，不重复实现。

## 🔗 相关

- 计划: [PLAN.md P3.3](../../../PLAN.md)
- 想法清单（已更新落地状态）: [docs/EXP_IDEAS.md](../../EXP_IDEAS.md)
- 命令清单: [docs/CLI_SURFACE.md](../../CLI_SURFACE.md)
