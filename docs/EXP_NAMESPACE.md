# exp 命名空间政策 (降级区)

> **创建**: 2026-09-09 (iter_230 P0)  |  **依据**: 方豆决策 "验证域命令统一降级处理" + "总线结构域也降级"
> **一句话**: `exp` 里的命令**能用、但没有任何承诺**；不投新功能，只修 bug，到期复审。

---

## 1. 哪些命令在 exp

| 域 | 目录 | 命令 (数量) | 降级理由 |
|---|---|---|---|
| **bus** 总线结构域 | `exp/bus/` | protocol detect/show/list/semantics, handshake scan/analyze/pair, backpressure analyze/deadlock (9) | 方豆决策: 总线域也降级 (无真实项目验证 / 语义未定稿) |
| **verif** 验证域 | `exp/verif/` | sva extract/coverage/timing, coverage suggest/gap/generate/analyze, verify gap, risk analyze, randomize list/extract/trace/reachability (13) | 方豆决策: 验证域统一降级 |
| **struct** 结构算法待定 | `exp/struct/` | cdc analyze, timing analyze (2) | **算法可靠性不足** (方豆: "这两个现在主要缺可靠的算法，先待定") |

**不在 exp**: `core` (只读事实与语义) / `view` (人眼图与叙述) / `dev` (内部调试) / `out` (会写文件, 移出 CLI)。

## 2. exp 的五条硬约束 (缺一不可, 否则"降级"只是改名)

1. **不进 `capabilities` 默认输出** —— 必须 `svq capabilities --json --include-exp` 才列出
2. **无 schema 版本承诺** —— 输出字段可随时改; `LayerSpec.schema_version = None`
3. **只修 bug, 不加功能** —— 修复须保持现有测试绿; 新功能需求先立项转正再写
4. **不得被 core/view 依赖** (含间接) —— 由 `tools/check_cli_layers.py` R2 强制
   (历史问题: `verify gap` 会去调 coverage/sva)
5. **命名不得出现在 core/view 的帮助文本里** —— 由 R5 检查 (防止误导 agent 选错工具)

## 3. 晋升门槛 (从 exp → core)

一个 exp 命令要转正, **三条齐备**:

| # | 门槛 | 判定方式 |
|---|---|---|
| 1 | **真实项目验证**: ≥3 个真实项目 (picorv32 / darkriscv / NaplesPU / C200 等) 上结果与参考实现或人工判定一致 | 记录在迭代文档, 附语料与命令 |
| 2 | **锁定回归**: 判定语义的测试 (不是"能跑"), 且含反例 | 测试文件 + 数量 |
| 3 | **失效场景清单**: 明确写出已知不适用场景 | 写进 `docs/KNOWN_LIMITATIONS.md` |

**复审期限**: 下个 minor 版本。到期未达标 → 按文档卫生纪律**归档** (移 `docs/archive/` 与代码 `_archived/`), 不是删。

### cdc / timing 的专项门槛 (算法待定)

| 项 | 现状 | 达标要求 |
|---|---|---|
| CDC 判定 | `cdc analyze` 有 16 个测试文件引用, 但**无真实项目交叉验证**; 判定规则未与参考实现对齐 | 与 (a) 手工标注 或 (b) 成熟工具输出 对比一致率可量化 |
| 时序深度 | `timing analyze` 基于 reg depth 启发式; generate/function 覆盖不全 | 补 generate/function 用例 + 真实项目路径与人工核对 |

**判定责任**: 方豆拍板 (算法可靠性是工程判断, 不由 AI 决定)。

## 4. 相关

- 分层总览 (生成物): [`CLI_SURFACE.md`](CLI_SURFACE.md)
- 机械检查: `python3 tools/check_cli_layers.py`
- 任务: [`task_tree/tasks/L1_cli_layering.md`](task_tree/tasks/L1_cli_layering.md)
