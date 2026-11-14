# P172.1 Coverage Gen workflow 收口

**日期**: 2026-11-14
**状态**: ✅ 完成

## 1. 问题

`Coverage Gen CI` 在 `4d58d7fb` 仍失败，不是产品回归：

```text
ERROR: file or directory not found:
  sim/tests/usage/test_coverage_generate.py
  sim/tests/usage/test_coverage_gen_demo.py
```

这些测试已归档到：

```text
docs/archive/2026-10-20-exp-attic/tests/
```

workflow 仍按旧路径运行，导致每次 push 必红。

## 2. 决策

Coverage Gen 测试已归档；没有可重复的当前 gate。

**退役** `.github/workflows/coverage-gen.yml`，不伪装成“修复绿”。

`tools/coverage_gen_demo.py` 保留为历史 POC 工具，但不再作为 CI 门禁；
如果未来恢复，需要先恢复/重写当前测试，再登记新 workflow。

## 3. 结果

- 不再有 Coverage Gen 红叉；
- Tests / Benchmark 仍是有效 workflow；
- C-16 更新为 Tests+Benchmark green；Coverage Gen 已退役，不是“通过”。

## 4. 边界

- 这不是把失败测试删掉；测试本来已归档；
- 不是把 Coverage Gen 标成已验证能力；
- 没有修改 `tools/coverage_gen_demo.py` 的行为。
