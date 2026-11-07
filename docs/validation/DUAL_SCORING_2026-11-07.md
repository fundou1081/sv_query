# 统一双评分（P86）

**日期**: 2026-11-07
**模块**: [tools/benchmark/scoring.py](../../tools/benchmark/scoring.py)

---

## 1. 为什么需要

同一个答案可能有两种正确：

- **canonical**：精确 canonical ID / path / count；
- **semantic**：关系内容对，但使用 instance alias / 信号 alias。

source 臂天然难产出 synthetic ID（如 `top.u.lo.ternary_sel[0]`），
strict-only 会把“结构关系对”误判成不会分析。

---

## 2. API

```python
from scoring import score_answer
s = score_answer(task, answer)
# {
#   "canonical": bool,
#   "canonical_checks": {...},
#   "semantic": bool | None,
#   "semantic_checks": {...} | None,
# }
```

规则：

- `canonical`：ground truth 字段精确匹配；
- `semantic`：
  - 仅 `complex_constraints` / `mux_neighborhood`；
  - 接受 instance/type alias、信号名 vs OP node 名；
  - 不是人工审计；
- direct 结构查询没有独立语义表示 → `semantic=None`，不伪造。

---

## 3. 接入

`score_long_range.py`：

- 逐行输出 `exact`（canonical）；
- 汇总增加 `semantic` / `semantic_n`；
- direct 任务 `semantic=n/a`。

`run_neighborhood.py`：

- 使用共享 `score_answer`，不再维护本地两套检查。

---

## 4. P85 修正后的数字

使用统一 scorer 重算 P85：

| 模型 / 臂 | canonical | semantic |
|---|---:|---:|
| MiniMax-M3 / source | 0/4 | 3/4 |
| MiniMax-M3 / T2 | 1/4 | 4/4 |
| M3.1-Flash / source | 0/4 | 4/4 |
| M3.1-Flash / T2 | 0/4 | 4/4 |
| DeepSeek / source | 0/4 | 4/4 |
| DeepSeek / T2 | 3/4 | 3/4 |

合计：

```text
canonical: source 0/12, T2 4/12
semantic:  source 11/12, T2 11/12
```

之前的 `T2 strict 6/12` 是旧本地检查，已被共享 scorer 修正为 **4/12**。

---

## 5. 边界

- semantic checker 是规则近似，不是人工逐项审计；
- direct 任务仍不能语义评分；
- 额外字段会导致 canonical 失败；
- 不会改变 ground truth。
