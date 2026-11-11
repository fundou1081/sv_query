# iter_490 — P164 文档状态校准（接手第一轮）

**日期**: 2026-11-11
**任务**: [L3_p164_doc_state](../tasks/L3_p164_doc_state.md)
**触发**: 方豆「1. 按照 handoff 建议。2. 然后先修文档状态。」

---

## 1. 动作

只改**状态类文档** + 两个文档检查器；未改 `src/**`、未改测试。

| # | 文件 | 改动 |
|---|---|---|
| 1 | `PLAN.md` | current item → P158.11.2b；P158.9 拆 9.2；4 处 `---- ` 改 `--`；P164 登记；变更记录 |
| 2 | `tools/check_plan.py` | P5 允许任意层级父项（深度 ≤3）；新增 P9（≥3 短横线 = 不可见项）；id 允许 `2a/2b` 字母后缀 |
| 3 | `tools/check_docs.py` | 基准只取 INDEX「当前基线」章节且只认 `N passed`；文件名带日期 = 时点快照 |
| 4 | `CURRENT_TODO.md` | 重写：当前 item、P164 完成、环境说明、下一步 |
| 5 | `docs/dev/HANDOFF.md` | HEAD 改为以 `git log -1` 为准；dataflow 实际缺口；26 个硬编码路径；解释器说明；建议顺序加 0 |
| 6 | `docs/dev/SEMANTIC_CONTRACTS.md` | §2.3 改为「已修复的历史违反」+ 复测证据；§11 状态表按 P158.1~12 实际收口重写 |
| 7 | `docs/INDEX.md` | 基线表规模计数实测值；删除过期子集计数（2129/810）；exp 说明；登记 arch_eval |
| 8 | `README.md` | 去掉 `2571 passed`，改为引用 INDEX；exp 命令补 `architecture graph` |
| 9 | `docs/KNOWN_LIMITATIONS.md` | §4「54 个已知失败」标为 2026-07-29 历史快照 |
| 10 | `docs/ARCHITECTURE.md` | 顶部过期声明（23→45 命令、VizData 退役、11 步 DAG、contracts） |
| 11 | `docs/lessons/2026-11-11_pitfalls.md` | §6.1 状态按收口更新；§6.2 标完成/未做；附录 PATH 说明 |
| 12 | `docs/sessions/2026-11-11_sv_query_session_log.md` | HEAD 不再写死 |

## 2. 关键发现（改文档前不知道）

1. **`---- ` 四级缩进项不被 `check_plan` 解析**：P158.9.1 / P158.11.2a / P158.11.2b 4 项长期"隐身"，
   所以 `current item` 指过去会报「不在计划树中」。根因是 P5 只允许顶层父项，
   于是用 4 个短横线绕过；已修检查器 + 统一缩进（577 项，原 567 项）。
2. **计数漂移检查恒过的根因**：`base_nums` 从整份 INDEX 提取，INDEX 里一条历史条目
   `2571 passed` 把旧数字"背书"了；同时 `N 测试` 把文件规模当通过数。
   改为只取「当前基线」章节 + 只认 `N passed` 后，README 的 2571 立刻暴露。
3. **HANDOFF 的 20 个硬编码路径不准**：实测 26 个文件。
4. **默认 `python3` 缺 typer**：P158 契约测试子集 12 failed → PATH 指向 miniconda 后 30/30 passed。

## 3. 证据（命令与结果）

```text
python3 tools/check_plan.py            ✅ 577 个计划项
python3 tools/check_docs.py            ✅ 死链 0 / 越界 0 / 未登记 0 / 漂移 0
python3 tools/check_docs.py --strict   ✅ 退出 0
python3 tools/check_except_pass.py     ✅ 计数 0
python3 tools/check_semantic_regex.py  ✅ 9 files
python3 tools/check_cli_layers.py      ✅ 退出 0（只有 informational 提示）
python3 tools/gen_cli_surface.py --check ✅
python3 -m pytest ... -k "p158 or determinism"（PATH 修正后） ✅ 30 passed
```

## 4. 未做 / 边界

- 未跑 canonical 全量：本机启动后 **28 分钟未结束**（已终止），2678 仍是**文档记录**，
  不是本次独立复核；建议后续给套件记 wall-time 预算。
- `arch_eval_2026-11-11.md`（21:07 出现的未跟踪讨论稿，非本会话产出）只做了 INDEX 登记，
  未改其内容，也未采纳其结论。
- `trace impact` 降 exp、依赖闭包固化：等方豆拍板，未动。
