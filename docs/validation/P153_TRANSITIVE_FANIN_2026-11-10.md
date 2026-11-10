# P153 transitive fanin wrapper PORT_OUT

**日期**: 2026-11-10
**状态**: ✅

## 1. 问题

P152 worker 发现：

```text
u_fsm.sck_o 是 u_spi_core.sck_o 的 wrapper_passthrough 源
但 trace_fanin(cio_sck_o, depth=None) 不含 u_fsm.sck_o
```

因此：

```text
verify claim driver ... --transitive
→ contradicted（假）
```

## 2. 根因

`_handle_port_out_source` 对 wrapper 源只 `_recurse_if_unseen`，
没有先把该 PORT_OUT 源 append 到 drivers；该节点进入 `seen_ids` 后
再也不会被追加。

## 3. 修复

对 wrapper_passthrough 源使用 `_append_source`：

```text
先 append 源节点
再递归继续
```

## 4. SPI 结果

```text
drivers spi_host.cio_sck_o --depth 5
→ 包含 spi_host.u_spi_core.u_fsm.sck_o

verify claim driver ... --transitive
→ verified
```

## 5. 测试

```text
test_transitive_wrapper_fanin.py: 1 passed
```

## 6. 边界

这是 fanin 节点保留修复，不改变 direct driver 语义；
T4 的 depth=1 contradicted 仍然正确。
