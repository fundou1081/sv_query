# Iteration 411: svq_query evidence（P105）

**状态**: ✅
**日期**: 2026-11-08

## 实现

- `intent=evidence` 读取 snapshot 节点 file/line；
- 通过 `SVQ_SOURCE_ROOT` 读取 ±2 行 source_context；
- 只针对指定节点，不开放任意文件读取；
- deep_chain 用 mixed 行确认 XOR。

## 结果

deep_chain 7/7 字段正确，包括 xor_node 和 combinational=false。

## 边界

snapshot/source 可能过期；source_context 不是完整语义分析。
