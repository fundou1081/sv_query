# Iteration 423: Constrained verify claim（P117）

**状态**: ✅
**日期**: 2026-11-08

## 完成

- `verify claim --from-snapshot`；
- tool `intent=verify`；
- 3 claims ×2 模型 6/6，单次 verify。

## 过程

首轮 4/6 是 prompt 把 verify unknown 改写成 not_found；修 prompt 后 6/6。

## 边界

仅 driver claim；未做 connection/bit/path agent 验证。
