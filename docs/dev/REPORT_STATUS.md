# REPORT_STATUS — “绿色”口径统一（P158.12.6 / R-028，2026-11-12）

> 依据：[REVIEW_2026-11-11 §5.5](../validation/REVIEW_2026-11-11.md)
> 「指标重新定义」、P160 §7 CI 策略。机器实现：
> `tools/report_status.py`；机械 gate：
> `sim/tests/unit/test_p158_12_6_report_status.py`（8 项）。

## 1. 问题

canonical 与 opensource 长期各自报一个 `0 failed`：

```text
canonical:   2746 passed / 0 failed / 123 deselected
opensource:  112 passed / 11 skipped / 0 failed        (P161 口径)
```

两个 `0 failed` 容易被读成“全绿”，但 canonical 有 **123 deferred**
（opensource suite 执行），opensource 有 **11 个显式 skip**。
`deferred` 不是 `unexecuted`；`0 skipped` 更不是 KPI（P157 教训）。
R-028 要求：报告必须分离状态，不许把未执行揉进“通过”。

## 2. 七类状态（唯一定义）

| 状态 | 含义 | 典型来源 |
|---|---|---|
| `passed` | 执行且符合预期 | pytest passed；benchmark task `exact=true` |
| `failed` | 执行且不符 | pytest failed/error；task `exact=false` |
| `unknown` | 执行但无有效结论 | task 无解析答案（`parsed=false`）；**不得计入 passed** |
| `truncated` | 被预算/时限截断 | timeout、budget exhausted、`rc=124` |
| `unexecuted` | 未执行 | task 异常未跑（`rc=130`）；pytest 里没有显式对应项 |
| `skipped_with_reason` | 显式 skip 且带 reason | retired exp 测试、环境 skip |
| `external_not_run` | 外部依赖缺失未跑 | openrtl corpus 缺失（`SVQ_OPENRTL_ROOT`） |

另外 `deferred` 是**非七类计数**：pytest `deselected`，表示本轮未选、由互补 suite 执行。
`is_fully_green` 只有在除 `passed` 外 7 类全部为 0 **且 `deferred=0`** 时才返回真。
**只看 failed 数不构成全绿判定。**

## 3. 两套跑法怎么读

```text
canonical (-m "not opensource")  : 核心门禁, 阻塞合并; 123 计入 deferred
opensource (-m "opensource")     : 非阻塞报告; 11 个显式 skip 计入
                                   skipped_with_reason, 不得从报告里消失
合并视图                          : 7 类相加 + deferred 单独显示, VERDICT 基于 TOTAL
```

生成合并视图（机器可读，避免人工抄数口径漂移）：

```bash
python3 tools/report_status.py --runs runs.json     # {"runs":[{name,passed,failed,skipped,deselected},...]}
python3 tools/report_status.py --tasks results.json # benchmark {"results":[...]}
```

`score_long_range.py` 的分组 summary 同步暴露 `statuses` 七类 +
`false_confident_denominator`。

## 4. false_confident 分母口径（R-027，**当前默认，待方豆确认**）

- 分母 = `answered_n` = `passed + failed`（**实际作答行数**）；
- `unknown / truncated / unexecuted / skipped / external_not_run` 既不进分子
  也不进分母——它们不是“答对了”，也不是“自信地答错了”，既不能算通过
  也不能稀释风险率；
- 无人作答时 `false_confident_rate = None`（不伪造 0%）；
- 旧实现把 `n`（含未执行行）当分母，会系统性低估风险率。

该口径是**合理默认而非拍板结论**：若决定“无答案也算一次冒进”，
改 `tools/report_status.py::summarize` 一处即可，测试
`test_unexecuted_does_not_dilute_false_confident_rate` 会变红提醒。

## 5. 维护规则

1. 汇报/文档写测试数字时至少给 `passed / failed / unexecuted /
   skipped_with_reason` 四项；禁止裸写 “0 failed 全绿”；
2. 新增跑法（如 9 skip 处置后的新套件）必须纳入合并视图；
3. INDEX「当前基线」行的 deselected 数字记入 `deferred`，不是 `unexecuted`；
   `deferred` 表示另一 suite 会执行，不等于“通过”，但也不等于“从未执行”。
