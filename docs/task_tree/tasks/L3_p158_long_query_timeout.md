# Task: P158.11.2b 通用长查询 timeout

**状态**: 已完成（2026-11-11）
**日期**: 2026-11-11
**契约**: [SEMANTIC_CONTRACTS §3](../../dev/SEMANTIC_CONTRACTS.md) — 任何路径枚举必须有 work budget + 可选 wall-clock timeout，超限显式 `truncated`

## 问题（可观察后果）

```text
paths 有 budget/deadline（P158.2）；
dataflow._find_paths(cutoff=50) 无 budget：
  - `list(nx.all_simple_paths(...))` 先物化全部简单路径 → 分支图指数爆炸
  - 无路径时 all_simple_paths 仍会遍历指数级死胡同（没有 has_path 前置检查）
  - analyze() 之后 `paths[:max_paths]` 静默截断，JSON 无任何截断字段
dataflow analyze 的 CLI 也没有 --timeout / --max-expansions
```

后果：大图 `dataflow analyze` 可能长时间不返回，且“没有路径”与“没查完”在输出上不可区分。

## 验收（可执行）

```bash
# 1. 有界：极小预算必须显式 unknown，而不是 found:false
python3 run_cli.py dataflow analyze <src> <dst> --filelist <f> \
  --max-expansions 3 --json
#    -> is_reachable: null, truncated: true,
#       truncation_reason: "max_expansions_reached",
#       machine.unknown_kind: "search_budget_exhausted"

# 2. 正常路径不受影响
python3 run_cli.py dataflow analyze top_minimal.valid_i top_minimal.sa1.valid_i \
  --filelist sim/tests/fixtures/minimal_3module/filelist.f --json
#    -> is_reachable: true, truncated: false, search_status: "complete"

# 3. timeout 可生效（timeout=0 -> deadline_reached）
# 4. max_paths 收满必须标 max_paths_reached（不是静默 slice）
```

## 反例 / 不能被骗过

- `is_reachable: false` 只在**搜索完成后**确认无路径时出现；预算耗尽必须是 `null`；
- `truncated: true` 时顶层不得暗示"完整"；
- 新增测试必须能红：把 budget 检查删掉 → 预算测试失败。

## 设计（单一实现）

- 复用 `PathResolver` 的预算记账器（抽出为 `graph/search_budget.py::SearchBudget`），
  **不写第二份** budget 逻辑；
- `_find_paths` 用与 `nx.all_simple_paths` **同遍历序**的有界 DFS 替换 `list(...)`，
  每次考察一条出边记 1 次 work；
- 默认 `max_expansions=200_000`（与 PathResolver 一致），`--timeout` 可选。
