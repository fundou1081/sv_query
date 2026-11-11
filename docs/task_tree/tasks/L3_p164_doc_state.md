# Task: P164 文档状态校准（接手后第一件事）

**状态**: 进行中
**日期**: 2026-11-11
**触发**: 方豆指示「1. 按照 handoff 建议。2. 然后先修文档状态。」

## 目标

把**状态类文档**与代码事实对齐，避免下一个 agent 按过期状态开工。
本轮**不改产品代码**，只改文档 + 计划树校验器。

## 验收（可执行）

```bash
python3 tools/check_plan.py                 # 0
python3 tools/check_docs.py                 # 0（含根 README/TESTING 的计数一致性）
python3 tools/check_except_pass.py          # 0
git diff --stat                             # 只含文档与 tools/check_plan.py、tools/check_docs.py
```

逐项：

1. `PLAN.md` current item = `P158.11.2b`（HANDOFF §12 的第一优先），P158.9 拆出 9.2，
   `---- ` 不可见项消失；
2. `CURRENT_TODO.md` 不再出现「P152 / 无活跃开发 item」，指向 P158.11.2b；
3. `SEMANTIC_CONTRACTS §2.3/§11`、`CLAIMS` 时间戳、`HANDOFF` HEAD/路径数/解释器、`INDEX` 基线、
   `README` 计数、`KNOWN_LIMITATIONS §4`、`ARCHITECTURE.md` 过期声明、`P159 §6.1` 状态；
4. `check_docs` 的计数漂移检查覆盖根 `README.md` / `TESTING.md`。

## 反例 / 不改的东西

- 不重写 P159 / REVIEW 的历史结论，只标「时点快照 + 现状见 PLAN」；
- 不为了「全绿」删除任何测试或 claim；
- 不动 `src/**`。
