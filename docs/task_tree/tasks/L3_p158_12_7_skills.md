# Task: P158.12.7 skills docs drift

**状态**: ✅ 完成
**日期**: 2026-11-12

## 问题

`skills/sv-query` 仍按旧命令面描述（cdc/risk/sva、40+5、旧 error code、旧 flag 叙事）。

## 处理

- 基于 `replay/agent-3530f163` 的校正内容重做（**不 merge 该分支**）；
- 当前真实命令面：**39 core + 6 exp**；
- `trace impact` / `audit` 归 exp（默认不出现在 capabilities，但可直接调用）；
- 更新 `SKILL.md` / `references/*` / `examples` / `scripts/sv_analyze.py` / `tools/llm_schema.json`；
- 新增 `test_skill_surface.py`：
  - max/misfit counts 不能回退；
  - 不能把 retired cdc/risk/sva 直接写成示例；
  - schema/helper smoke。

## 验收

```text
4 passed (test_skill_surface)
schema tests 17 passed
```

## 边界

skills 是 agent-facing 文档，不是产品代码；不改变 CLI 行为。
