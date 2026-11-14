# HANDOFF — 当前交接状态

**日期**: 2026-11-15
**仓库**: `/Users/fundou/my_dv_proj/sv_query`
**HEAD**: 以 `git log -1` 为准
**旧会话快照**: [HANDOFF_2026-11-12.md](HANDOFF_2026-11-12.md)（历史，不要当当前状态）

> 计划树唯一真相源：[PLAN.md](../../PLAN.md)。
> 本文件只回答“现在是什么状态、从哪里接手”。

---

## 1. 一句话状态

```text
主线 query + verify 健康；
当前在做 P173：清理 review 发现的状态文档 / CLI truth / zombie tests / 旧示例。
```

## 2. 基线

```text
canonical:  2737 passed / 0 failed / 123 deferred / 0 unexecuted
opensource: 112 passed / 11 skipped / 0 failed
mutation:   20/20
```

- 123 deferred 是 opensource suite，不是 unexecuted；
- 11 skip 中 2 个是 SPI snapshot 外部 fixture 缺失；
- 计数只信 [docs/INDEX.md](../INDEX.md) 的“当前基线”。

## 3. 当前主线

```text
39 core commands:
  semantic 24 / verify 3 / scope 1 / locate 7 / state 4
```

稳定、只读、JSON、schema v1。代表命令：

```text
drivers / loads / paths / dataflow / controlflow
verify consistency / verify claim / verify structural
trace profile / evidence / lookup / manifest
scope / instances / hierarchy / ports / params / connections
class / constraints / covergroups / graph / snapshot
```

## 4. exp（6 个，hidden）

```text
audit / diagnose / trace impact / trace overview
review render / architecture graph
```

- 没有 `svq exp` 统一入口；
- 默认不进 help/capabilities；`--include-exp` 才列；
- 无 schema/claim 承诺，只修 bug。

## 5. 历史/退役

| 功能 | 状态 |
|---|---|
| coverage generate / coverage suggest | 历史 POC；workflow 已退役；不恢复 CLI |
| rng / randomize | 退役；仅剩 fixtures/旧文档 |
| visualize / cdc / timing / sva / risk | 退役；部分逻辑只在 audit |
| 全设计图 | 退役 |
| interactive debug（P62.2） | gate 评估 no-go；不做 UI/REPL |
| constraint SAT 分析 | 不在本仓库；见独立项目 `constraint_diagnoise` |

## 6. 当前 P173 清理

1. **P173.1 CLI/exp truth**
   - `trace impact` 已 hidden；
   - 注册表不再宣传 `svq exp`；
   - CLI_SURFACE / AGENT_FEATURE_MAP / EXP_NAMESPACE 对齐 39 core、6 exp。

2. **P173.2 status docs**
   - CURRENT_TODO 重写；
   - HANDOFF 重写；
   - PLAN/契约/README 计数与旧“下一步”清理。

3. **P173.3 examples/tests hygiene**
   - 退役 zombie tests；
   - 修 README/USER_GUIDE/FILELIST/PRIMARY 的不可运行示例；
   - 处理 coverage POC 与 canonical test 的耦合。

## 7. 已知风险

- 公开文档仍有旧命令/旧 import，不能直接照抄；
- `trace impact` 是未标定启发式，不能当绝对风险；
- coverage POC 不是当前产品；若重启要单开项目；
- `check_crap` 依赖 crapper；缺失时是 exit 3，不是 pass。

## 8. 接手命令

```bash
bash tools/run_gates.sh
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly
python3 -m pytest sim/tests/ -m "opensource" -q -p no:randomly
python3 tools/run_mutation_gate.py
```
