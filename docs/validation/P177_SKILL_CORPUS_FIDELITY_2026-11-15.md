# P177 skill/corpus fidelity fixes

**日期**: 2026-11-15
**状态**: ✅ 完成

第三轮独立 review 对照 51 个外部短/长任务后，仍发现 skill 与语料不一致：

- `paths --canonical` 被当成通用默认：P111 `bvalid→xfer_done` 默认 2 hops，
  canonical 13 hops；skill 会引导错误答案。
- `driver_count` 不是 `len(drivers)`：CONNECTION/PORT、ternary/branch、
  clock/reset、constant 不计入；`drivers[]` 仍包含它们。
- `trace evidence` 对 bus/array 可能 null，且 UART `rx_val_q` 指向 reset branch；
  功能赋值在 `trace profile.source.driver`。
- `class --member` 接成员名，不是实例限定 id；candidates 才是实例路径。
- mux 场景不能直接以 `top.q` 做 branch subgraph seed；先 `graph nodes --kind OP_TERNARY`。

## 修复

- paths 三种模式分开写：默认单路径 / `--canonical` / `--all`；新增 P111 反例；
- driver_count 语义改为“仅 DRIVER-edge 源”，补反例；
- evidence fallback 写清 profile.driver / null / reset branch；
- class member 语义修正；
- mux seed 改为 OP_TERNARY 节点；
- UART empty-side 注释区分 current 1 vs old expected 2；
- 新增可执行 skill 测试：class member、OP_TERNARY nodes、deep_chain default path。

## 验证

- skill surface: 8 passed
- canonical: 2742 passed / 0 failed / 123 deferred
- full gate: green
