# P181 discipline remediation

**日期**: 2026-11-16
**状态**: ✅ 完成

## 1. 审计结论

worker 对 `cf0d8850` 判 FAIL，见主会话复现记录。P181 逐项修复。

## 2. 修复项

- active-high reset 极性：`if (rst)` / `if (rst == 1)` 为 reset，else 为 functional；
  active-low `rst_n`/`rst_ni`/`rst_no`/`rstn` 反向；sized literal `1'b0`/`1'd0` 正确解析。
- `trace profile.source.line` 由 printer source 是否注入 timescale 决定，不再无条件 -1。
- class property evidence 改用 `ClassPropertySymbol.syntax`，删除 regex 扫描；
  `check_semantic_regex` 覆盖 `trace_evidence.py`。
- verify consistency 抽出 `_coverage_complete`，hermetic 单测 unknown/truncated。
- `fsm_analyzer` reset 判断复用 `source_assignment.is_reset_condition`；
  subgraph branch kinds 从 `CONTROL_EDGE_KINDS` 派生；
- `trace_profile` 与 core 共用 `compiled_line_shift`；
- virtual class property 也走 `ClassPropertySymbol`；
- `_coverage_complete` 增加 command wiring 测试；
- 修正 overview/CURRENT_TODO/blank-line EOF 等审计 doc nit。
- `run_gates.sh` 增加 lint（base = SVQ_GATE_BASE/HEAD~1），不再 no-op。
- 补 iteration 530-533、task 文件、P180 worker review artifact、CLAIMS C-17..C-20。

## 3. 验证

- targeted: 81 passed（evidence/profile/verify/subgraph/credibility/class）
- canonical: 2775 passed / 0 failed / 123 deferred
- full gate: green（含 lint）
- lint base 5bbbcdf5: all checks passed
- mutation gate: 20/20

## 4. worker 复核

- `ada6c5c2` 复核：PASS WITH NITS（无 HIGH/MEDIUM）。
- 剩余 LOW：profile `active_low` 的 sized-literal 条件解析已共享 `reset_literal_value`，
  `_declaration_line` 不再猜测 -1；新增 profile 单测。
- 最终 canonical 2775 / gate + lint green；worker 最后只审到 `ada6c5c2`，
  其后 LOW 修复由本地 gate 验证，不再声称新的 worker APPROVE。
