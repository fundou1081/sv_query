# iter_495 — P158.12.6 绿色口径统一（R-028 / R-027 分母）

- **日期**: 2026-11-12 上午
- **任务**: [PLAN] P158.12.6（current item）
- **依据**: [REVIEW_2026-11-11 §5.5](../../validation/REVIEW_2026-11-11.md)
  「指标重新定义」+ P160 §7 CI 策略
- **结果**: ✅ 完成

## 1. 问题

canonical 报 `2710 passed / 0 failed / 131 deselected`，opensource 报
`114 passed / 17 skipped / 0 failed`（P161 口径）。两个 `0 failed` 容易被
读成“全绿”，但 **148 个单元根本没执行**。`0 skipped` 也不是 KPI（P157 教训）。
此前没有任何机器可读的统一报告口径，全靠人工叙述，容易漂移。

## 2. 实现

### `tools/report_status.py`（新）

- 7 类状态唯一定义：passed / failed / unknown / truncated / unexecuted /
  skipped_with_reason / external_not_run
- `classify_task(row)`（优先级：异常 → 外部缺失 → skip → 截断 → 无答案 →
  exact → failed）、`classify_pytest_counts(counts)`、
  `summarize(rows)`、`is_fully_green`（除 passed 外全 0 才真绿）、
  `render_report`（合并视图 + VERDICT）
- CLI 双模式：`--runs`（canonical/opensource 摘要合并）、`--tasks`（benchmark
  results）。实测输出：
  ```text
  run=TOTAL: passed=2824 failed=0 ... unexecuted=131 skipped_with_reason=17
  VERDICT: NOT fully green — 只看 failed 数不代表全绿; 未通过/未执行/未知单元 = 148
  ```

### `tools/benchmark/score_long_range.py` 接入（R-027 分母）

- 分组 summary 新增 `statuses` 七类 + `answered_n` +
  `false_confident_denominator`；文本输出打印非零状态类
- 旧字段（`exact`/`semantic`/`n`/`mean_seconds`）全部保留，
  `verify_long_range.py` 兼容性验证通过（真实历史数据
  `long_range_12_2026-11-05.json` → 12 cells / 7 exact / 分母 12）

### `docs/dev/REPORT_STATUS.md`（新，登记 INDEX）

7 类定义 / 两套跑法怎么读 / 分母口径 / 维护规则。INDEX 基线行把
131 deselected 明确标为 `unexecuted`。

## 3. 口径决策（R-027，**当前默认，待方豆确认**）

`false_confident` 分母 = `answered_n = passed + failed`（实际作答行数）；
unknown/truncated/unexecuted/skipped/external_not_run 既不进分子也不进分母；
无人作答时 rate=None（不伪造 0%）。旧实现用 `n`（含未执行行）会系统性
低估风险率。改口径只需动 `summarize` 一处，测试
`test_unexecuted_does_not_dilute_false_confident_rate` 会变红提醒。

**这是合理默认而非拍板结论**，已在 REPORT_STATUS.md §4、HANDOFF §5.3-5、
CURRENT_TODO 三处显式标注。

## 4. 验证

- `sim/tests/unit/test_p158_12_6_report_status.py`：**8 passed**
  （7 类全覆盖 / 0 failed 不绿 / 两套跑法 7 类全打印 / 分母不被未执行稀释 /
  无作答 rate=None / score_long_range 集成）
- 近三轮新增测试合计 22 passed；CLI 两模式冒烟通过；
  真实历史数据 `score()` 兼容通过
- **canonical 全量独立复核：2718 passed / 0 failed / 131 deselected /
  35 subtests**（rc=0，36min，收口后干净工作树）；INDEX/TESTING/HANDOFF
  计数同步 2718
- 8 门禁：见提交信息

## 5. 边界

- 本轮全量已独立复核（2718/0，含新增 8 测试）；`src/` 未改动，
  仅新增报告模块/测试与 benchmark 评分脚本接入
- 17 个 opensource skip 的最终处置未做（下一步）
- `false_confident` 分母口径待确认

## 6. 交接

- current item → **P158.12.7 skills 文档漂移**（命令面 39+6；
  `replay/agent-3530f163` 旁路分支有现成内容可参考重做）
