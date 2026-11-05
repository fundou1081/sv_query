# Iteration 374: 4-task seed2 + 软隔离（PLAN P69.6）

**Metadata**:
- **Iteration #**: 374
- **Task Tree Level**: L2（PLAN `P69.6`）
- **Created**: 2026-11-05 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 4-task seed2；软隔离；未做完整 12×3

## 🎯 动作

- 工作目录切到 `/tmp/lr_pilot`，source 臂从该目录启动；
- 临时移走全局 `sv_query` 二进制；
- 清空缓存 JSON/err；
- 4 个代表任务 × 2 模型 × 2 臂，seed 2；
- Pico T2 首跑再次混用 `full.f`，用 `--file` 重跑修正。

## 📊 结果

| 模型 / 臂 | seed1 | seed2 |
|---|---:|---:|
| MiniMax source | 2/4 | 1/4 |
| MiniMax svq | 4/4 | 4/4 |
| DeepSeek source | 2/4 | 4/4 |
| DeepSeek svq | 4/4 | 4/4 |

## 🔍 结论

- T2 两 seed 稳定 4/4；
- source 臂方差大（DeepSeek 2→4，MiniMax 2→1）；
- 小样本不能证明模型排名；
- 软隔离仍不是 OS 硬隔离。

## 🔜 下一步

P69.7：12 题 × 3 seed + 容器/沙箱硬隔离。
