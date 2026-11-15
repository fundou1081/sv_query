# P179 control alias + evidence source text

**日期**: 2026-11-16
**状态**: ✅ 完成

## 1. `graph subgraph --edge-kinds control`

旧的 `control` 只匹配带条件的 DRIVER 边，不包含 P158.1 的
`BRANCH_*`/`CASE_*` 边，所以 mux/ternary 子图会返回 0 边。

现在：

```text
control = legacy conditional DRIVER + branch/ternary edges
```

`--edge-kinds branch` 仍是显式精确选择。

## 2. evidence fallback source_text

edge fallback 过去返回 edge expression（如 `data`），现在优先读取
source_location 对应的真实源码行：

```text
dout <= data;
```

读不到文件（snapshot/legacy）时回退到 expression。

## 3. 测试

- `test_subgraph_control_includes_branch_edges`；
- `test_reset_branch_falls_back_to_functional_assignment` 改为断言完整赋值行。

canonical: 2748 passed / 0 failed / 123 deferred；full gate green。
