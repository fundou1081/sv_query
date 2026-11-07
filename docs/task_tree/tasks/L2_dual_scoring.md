# Task: 统一双评分（P86）

**状态**: 已完成
**目标**: strict canonical + semantic 两套评分统一到一处，long-range 和
neighborhood benchmark 共用。

## 设计

- `canonical`：ID/path/count 精确匹配；
- `semantic`：只对 neighborhood 任务，允许 instance/signal alias；
- direct 结构查询没有独立语义表示 → `semantic=None`，不伪造。
- `score_long_range.py` 输出两套汇总；
- `run_neighborhood.py` 使用共享 scorer。

## 边界

- semantic 不是人工审计；
- 不改变 ground truth；
- direct 任务仍以 canonical 为主。
