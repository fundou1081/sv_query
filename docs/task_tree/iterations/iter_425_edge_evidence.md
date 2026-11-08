# Iteration 425: Edge-level source evidence（P119）

**状态**: ✅
**日期**: 2026-11-09

## 修复

- snapshot 保存 edge source_location/expression/bit_slice；
- tool `intent=evidence` 返回 edge_evidence；
- source basename fallback。

## OpenTitan

T3 复测：MiniMax/DeepSeek 都返回 `uart_core.sv:307` 和正确 assignment。

## 边界

旧 snapshot 无 edge evidence；T5 schema 歧义未解决。
