# iter_492 — P158.12.1 `trace impact` 降级 exp

**日期**: 2026-11-11
**任务**: P158.12.1（挂 [P158.12 P2 清理](../tasks/L3_p164_doc_state.md) 下；决策来源方豆 + KNOWN_LIMITATIONS §3.4 / HANDOFF §5.3-3 / R-025）
**触发**: 方豆「降 exp，我记得之前文档里就提过了」——确认：HANDOFF §5.3、pitfalls R-025、KNOWN_LIMITATIONS §3.4 三处早已建议

---

## 1. 动作

| # | 位置 | 改动 |
|---|---|---|
| 1 | `src/cli/_registry.py` | `trace impact` 从 `_c("trace impact", "semantic", recommended=True)` 改为 `CommandSpec(layer="exp", group="semantic", kind="experimental", recommended=False)`，与 `audit` 同款；note 记录降级依据（铁律 9 / R-025） |
| 2 | `docs/CLI_SURFACE.md` | `gen_cli_surface.py` 重新生成（45 命令总数不变） |

## 2. 效果（实测）

```text
capabilities 默认:   core 39 / exp 6（原 core 40 / exp 5）；impact 不在默认列表
capabilities --include-exp: impact 出现，layer=exp, mode=exp, recommended=false
命令仍可调用:       trace impact diamond_top.a --json → ok:true
                    （exp 只影响可见性/承诺，不摘除命令）
json_contract:      静态表含 impact 条目，契约测试不受影响
```

## 3. 证据

```text
pytest test_json_contract.py + test_include_control.py + test_trace_schemas.py
  → 54 passed / 0 failed（registry 改动后跑）
gen_cli_surface --check ✅；capabilities 冒烟见上
```

## 3.1 预存在失败（与本次无关，已用 stash 在 HEAD 复现）

`sim/tests/cli/test_known_limitations.py` 3 个失败：函数内直接
`from trace.unified_tracer import UnifiedTracer` → `ModuleNotFoundError: 'trace' is not a package`
（被 stdlib `trace` 遮蔽）。这与 arch_eval P2.5 指出的 packaging 债是同一根因，
是 **P165.2 的现场证据**，不混入本次修复。走 subprocess 的契约测试不受影响。

## 4. 文档同步

KNOWN_LIMITATIONS §3.4 加处置注记（保留降级依据）；EXPERIMENTAL_FEATURES 顶部加
2026-11-11 更新（exp 层 6 命令）；README exp 列表补 impact；CURRENT_TODO 命令面
39+6 且 impact 从未决讨论项移入已拍板；HANDOFF §5.3-3 划线标已解决 + 40→39；
pitfalls R-025 → 已修；PLAN 登记 P158.12.1 + 变更记录。

## 5. 边界

- `recommended=True` 消失意味着 agent 默认工作流不再推荐它——这是**有意的**：
  未标定启发式进入推荐位就是 R-025 说的"伪装稳定"。
- 风险分本身（权重、HIGH 偏置）未改——标定属于 P165.3 外部故障集的前置工作，不混入本次。
- semantic group 计数 25→24（capabilities core_by_group 实测）。
