# Iteration 409: deep_chain tool probe（P103）

**状态**: ✅（负结果）
**日期**: 2026-11-08

## 协议

3 个固定 `svq_query`：path / neighborhood leaf / neighborhood mixed。

## 结果

- 协议执行成功；
- path 绕过 ternary，10 hops；
- xor_node=null；
- combinational=true（错误）；
- register/mux node/mux control 正确。

## 结论

受限工具本身可用，但不能只靠 path+neighborhood 原始结果合成 deep_chain；需要 granular path 或 drive_chain intent。
