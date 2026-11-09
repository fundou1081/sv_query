# Iteration 439: Coverage limitation schema（P131）

**状态**: ✅
**日期**: 2026-11-09

## 决定

不为了提取 coverage 破坏 Semantic AST 严格性；保留 pyslang 局限。

## 实现

- `trace covergroups` / `covergroup` / `coverpoints` 失败时输出
  `coverage_limitation`（reason/status/codes/source_locations/agent_action）；
- 默认仍是严格失败，不 partial；
- agent 根据源码位置自己读 covergroup/bins。

## 验证

- 新测试 3 passed；
- coverage regression 87 passed；
- CLI 15 passed；
- I2C 20 errors + 10 locations。

## 未来

pyslang 修复后重跑 `i2c_env_cov`，再打开 coverage 语义。
