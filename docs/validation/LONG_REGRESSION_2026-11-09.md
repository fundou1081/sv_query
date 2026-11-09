# 冻结后长任务回归（2026-11-09）

**范围**: 之前 12 个 direct long-range tasks ×2 模型
**状态**: 24/24 exact，0 false-confident

---

## 1. 结果

| 模型 | exact | mean wall |
|---|---:|---:|
| MiniMax-M3 | 12/12 | ~4.9s |
| DeepSeek-Flash | 12/12 | ~4.0s |

合计：

```text
24/24 exact
```

这是冻结后对原 12-task set 的回归，不是新任务。

## 2. 说明

- 使用冻结工具和原 pinned inputs；
- 没有 provider/infra 问题；
- 结果与冻结前工具基线一致。

## 3. 边界

- 仍是 direct structural query；
- 不代表 testbench/coverage/debug 能力；
- 不是用户研究。
