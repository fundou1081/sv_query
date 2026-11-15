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

## 3. 后续修正

- evidence fallback 的 `source_text` 现在读真实源码行；
- 多语句 always 分支通过 LHS 扫描选择非 reset 赋值行：
  - `sync_fifo.data_out` → line 33；
  - `sync_fifo.reg_stage1` → line 32；
  - `top.dout` → line 19；
- `trace profile.source.driver` 同步改为 functional assignment；
- snapshot evidence 也走 LHS 扫描，source 路径可跨 cwd 回退；
- 支持 reset-in-else；不再取最后一个 reset 赋值；
- assignment 扫描只接受真正 LHS（排除 `==`/`<`/行注释/块注释）；
- filelist 模式按 basename 找真实源文件，不再只读 expression；
- plain else / 多行 if 条件按分支头选择 functional assignment；
- class/constraint evidence 不做模块 LHS 覆盖；
- reset 条件用 word boundary，避免 `first` 误命中 `rst`；
- 读取失败不再 `except: pass`，改为 logger.debug。

## 4. 测试

- `test_subgraph_control_includes_branch_edges`；
- `test_reset_branch_falls_back_to_functional_assignment` 改为断言完整赋值行。

canonical: 2758 passed / 0 failed / 123 deferred；full gate green。
