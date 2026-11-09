# P135 FIFO / bus connectivity

**日期**: 2026-11-09
**状态**: P135.1/P135.2 完成
**结果**: 跨 FIFO 现在需要显式 `--through-fifo`；默认结构查询不变

---

## 1. 背景

P134 中 `nakok.q -> fmt_flag_nak_ok` 在 FIFO 边界断开：

```text
drivers(fmt_fifo_wdata) = 0
paths(nakok.q, fmt_flag_nak_ok) = not found
```

两个问题：

1. 父总线没有聚合 bit-slice driver；
2. FIFO 是时序存储，不能当普通结构边。

## 2. P135.2 父总线聚合

`drivers(fmt_fifo_wdata)` 现在返回 6 个字段 driver：

```text
fdata.fbyte.q
fdata.start.q
fdata.stop.q
fdata.readb.q
fdata.rcont.q
fdata.nakok.q
```

实现：

```text
父总线无直接 driver 且无 incoming bit-select
→ 递归它已有的 bus[bit] 子节点
→ 只做 fanin 查询聚合，不新增图边
```

这保持了 path 语义不变，避免把 bit-select 聚合污染到所有路径。

## 3. P135.1 FIFO 边界

新增：

```text
EdgeKind.FIFO
assign_type = "fifo_state"
```

FifoBridgeBuilder 对 module type/instance 名含 `fifo` 的模块：

- 识别 write/read 端口：
  ```text
  fifo_wdata_i / wdata_i / wdata / wr_data / din
  fifo_rdata_o / rdata_o / rdata / rd_data / dout
  ```
- 加 `write -> read` 的 FIFO 边；
- 同时为已存在的 bit 节点加对应 FIFO 边。

默认 `paths` **不跨 FIFO**；显式：

```bash
sv_query paths <write> <read> --through-fifo
```

## 4. 实测 I2C

默认：

```text
paths nakok.q -> fmt_flag_nak_ok
→ found = false
```

`--through-fifo`：

```text
nakok.q
→ fmt_fifo_wdata[12]
→ u_fifos.fmt_fifo_wdata_i[12]
→ u_fifos.fmt_fifo_rdata_o[12]
→ fmt_fifo_rdata[12]
→ fmt_flag_nak_ok
→ found = true
```

4 个 FIFO 方向都已建模：

```text
u_fifos 的 acq/fmt/rx/tx
adapter 的 inp/oup buffers
```

## 5. 语义

FIFO 边不是组合路径：

```text
write -> read 是 sequential state boundary
```

因此：

- `verify claim` 默认仍按结构路径，不会把 FIFO 当组合连接；
- `drivers/loads` 默认仍只走 DRIVER/CONNECTION；
- 只有显式 `--through-fifo` 才会跨边界；
- 未来 `dataflow` 可复用同一 FIFO 边并标注 latency/state。

## 6. 测试

```text
test_fifo_bridge.py: 2 passed
  default not found
  --through-fifo found
test_bus_bit_aggregation.py: 1 passed
path semantics/directed: 32 passed
```

## 7. 边界

- FIFO 识别是端口命名/模块名启发式，不是通用 memory model；
- 旧 snapshot 没有 FIFO 边，需要重建；
- `drivers/loads` 不跨 FIFO；
- 不是 FIFO 深度/满空/延迟分析；
- `dataflow` 尚未显式输出 FIFO latency。

## 8. 下一步

P134 剩余：

```text
#3 false missing-file warning
#4 architecture --from-snapshot / cache
#5 TB random -> RTL snapshot join
#7 solve…before / dist weights
#8 unknown machine-readable flag
```
