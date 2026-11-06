# Iteration 383: P1 interactive stability（PLAN P79）

**状态**: ✅ 完成
**日期**: 2026-11-06

## 运行

- 3 场景 × 3 模型 × 2 seed；
- seed1 复用 P0/P74；seed2 新跑 9 个；
- seed2 三项 MiniMax 因 429 重跑（单并发 + backoff）。

## 结果

- deep：3/3 × 2 seed 稳定；
- coverage：3/3 × 2 seed 稳定；
- constraints：17/18 完整；M3 seed1 把 covergroup 当 block；
- P77 在三模型 deep 中均被使用。

## 工程

- 新增 `tools/benchmark/interactive_debug/run_seed.py`；
- 模型 patch 拆到 `patches/`；
- rate-limit 退避；
- 明确 answer shape。

## 边界

- 小样本，不是真实 bug benchmark；
- seed1 协议较松；不作模型排名。
