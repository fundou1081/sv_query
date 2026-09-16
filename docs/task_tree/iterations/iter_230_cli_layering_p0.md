# Iteration 230: CLI 分层专注化 P0 — 注册表 + capabilities + 两个机械检查器

**Metadata**:
- **Iteration #**: 230
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_cli_layering.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ P0 完成 (纯新增: 不改任何现有命令行为; 全量门禁 3317 passed / 0 failed 不变)

## 🎯 本次目标

方豆: **"我们现在做的命令太多了，不够专注… 应该有取舍，至少分层"** +
随后逐条拍板: 不改 RTL / 验证域降级 / 总线域也降级 / agent 是主消费者但人眼可视化后续重点开发 /
**从目录结构体现命令分层** / 不拆仓 / cdc-timing 待定 / snapshot-diff 进 core /
capabilities 默认含 view / **fanin-fanout 改名**。

P0 = 把"分层"从**讨论**变成**可机械校验的代码事实**: 注册表 + 能力清单命令 + 两个检查器。
**不改任何现有命令的行为** (所以 3317 测试不受影响)。

## 🔬 实际产出 (4 件)

### 1. `src/cli/_registry.py` — 单一真相源

- `LayerSpec`: 每层的承诺 (consumer / stability / readonly / json_required / schema_version / in_capabilities)
- `CommandSpec` + 65 条分类: `key`(现状名) / layer / group / kind / cost / json / stateful / recommended / **planned_name**
- `to_json(include_exp, recommended_only)`: capabilities 与生成器共用, 避免两处各算一遍
- 层: `core`(23) / `view`(13) / `exp`(24) / `dev`(3) / `out`(2)
- core 内分组: `semantic`(8) / `locate`(7) / `state`(6) / `diagnose`(2)
- `NEW_PLANNED`: instance 查询 4 个新命令 (instances / instance / connections / hierarchy) + 复用哪个已有 API

### 2. `svq capabilities [--json] [--recommended] [--include-exp]`

agent 的工具面真相源: 先读清单再决定调什么, 而不是猜 64 个命令名。
默认列 **core + view** (方豆决定); `--recommended` 给最小集 (11 个); exp 需显式 `--include-exp`。

### 3. `tools/check_cli_layers.py` — R1~R6 机械检查

| 规则 | 内容 | 首次运行发现 |
|---|---|---|
| R1 | 每个命令必须登记 | 1 条 (自查 bug: callback-only 组被漏, 已修) |
| R2 | 层间依赖方向 (core ⊥ view/exp/dev …) | 0 (待 P1 分目录后才有效) |
| R3 | CLI 内禁止**隐式改文件** | **3 处 mutation**: `fix.py` ×2 (原地改 RTL) + `fix_imports.py` (写 filelist) |
| R4 | core 必须 `--json` | **3 条**: `search` / `snapshot save` / `snapshot delete` |
| R5 | exp 名不得污染 core/view 帮助 | 0 |
| R6 | exp 不进 capabilities 默认 | 0 |

**已知基线机制**: 6 条现状违规记为 `KNOWN` (每条写明消除批次), 不阻塞提交;
**新增违规立即失败** → 检查器现在就能当"防新增"门禁, 不用等 P2 清完。

### 4. `tools/gen_cli_surface.py` + `docs/CLI_SURFACE.md` (生成物)

命令清单不再手写: 数据来自 `_registry.py` + typer introspection, `--check` 检测漂移。
(动机: 本仓库的 `ARCHITECTURE.md` 就烂过 —— 写"23 commands"实际 21 组 64 命令,
写 `driver_extractor` 3987 行实际 1445 行。清单必须是生成物。)

## ❌ 过程中我自己的两个错误 (如实记录)

1. **检查器第一版误报 20+ 条**: `WRITE_METHODS` 里放了 `replace`, 与 `str.replace()` 同名 →
   把字符串替换全判成写文件。**检查器本身也要经得起抽查** —— 我逐条看了输出才发现。
2. **R3 判据第一版太粗**: 用"函数有输出类选项"一刀切 → 把 `visualize teach` / `design show`
   的**产物输出**(用户 `--svg/--graph-dir` 指定的路径) 误判成违规。
   修正为三分类: `mutation`(原地改源文件/工程文件 → 违规) / `artifact`(写产物路径 → 允许) /
   `helper-review`(helper 内无法静态判定 → INFO 人工复核)。
   判据: 参数含 `apply/write/backup/in_place`, 或写目标带 `.sv/.v/.f` 后缀 ⇒ mutation。

**教训**: 检查器的判据必须能被抽查 (每一条都能指出代码行), 否则"绿灯"没有意义 ——
这与 iter_190(`check_except_pass.py`) 和 iter_227(`ast.dump` 等价闸) 是同一条经验。

## 📊 验证

| 项 | 结果 |
|---|---|
| 全量 canonical (`-m "not opensource"`) | **3317 passed / 0 failed** (与 iter_228 持平, 0 退化) |
| `svq capabilities` / `--json` / `--recommended` | rc=0, JSON 可解析 (65 命令, 分层统计正确) |
| `tools/check_cli_layers.py` | rc=0 (0 新增违规 / 6 已知基线 / 54 INFO) |
| `tools/gen_cli_surface.py --check` | ✅ 与代码一致 |
| `stats` 冒烟 | rc=0 |

## 💡 关键发现 / 决策

1. **"分层"必须落到可执行检查, 否则等于没分**: 注册表声明 + R1~R6 强制 + capabilities 过滤,
   三者缺一, 下一个人就会把新命令直接加在平铺层上 (本项目已有两次同类教训)。
2. **只读约束要区分"写产物"与"改文件"**: 渲染产物是产品职责 (`--svg out.svg`),
   原地改 RTL 是禁止的。混为一谈会让检查器要么全放行、要么全禁止。
3. **目录体现承诺等级, 属性体现副作用**: 不为"是否 JSON / 是否 stateful / 成本"各建目录,
   而是 `LayerSpec` + `CommandSpec` 声明 —— 避免组合爆炸, 也让 capabilities 能自动生成。
4. **P0 不改行为是刻意的**: 先把"事实与规则"固化, 再动命令面 (P1)。这样每一批都能单独回退,
   且全量门禁始终是绿的。

## 📎 产物

- 新增代码: `src/cli/_registry.py`, `src/cli/commands/capabilities.py` (+ main.py 注册 1 行)
- 新增工具: `tools/check_cli_layers.py`, `tools/gen_cli_surface.py`
- 新增文档: `docs/CLI_SURFACE.md` (生成物), `docs/EXP_NAMESPACE.md` (降级政策 + 晋升门槛),
  `docs/task_tree/tasks/L1_cli_layering.md`
- 下一步 (P1): 目录分层 + alias + 补 3 条 `--json` + `fanin→drivers` / `fanout→loads`
