# Iteration 422: Answer JSON repair（P116）

**状态**: ✅
**日期**: 2026-11-08

## 实现

- `tools/benchmark/answer_json.py`：strict → 单引号修复；
- runner 记录 `json_repaired`；
- 4 个 parser tests。

## 结果

P115 raw 39/40 valid JSON；重放 40/40 exact，1 repaired。
false-confident / false-found 仍为 0。
