# P136.2 architecture --from-snapshot

**日期**: 2026-11-09
**问题**: `architecture graph` 每次重新 parse，I2C 约 16.3s；没有 snapshot 模式
**结果**: 支持 `--from-snapshot`，架构图从已保存 SignalGraph 直接构建

---

## 1. 实现

新增：

```bash
sv_query architecture graph \
  --from-snapshot opentitan_i2c \
  --module i2c.i2c_core --depth 1 \
  --json / --svg
```

数据来源：

```text
snapshot SignalGraph
  INSTANTIATED_MODULE → 架构节点
  PORT_IN/OUT/INOUT    → 端口方向
  CONNECTION edges     → 真实 net 连接
```

不再调用 parser / MIG。

## 2. 结果

I2C snapshot：

```json
{
  "instances": 5,
  "connections": 37,
  "boundaries": 189,
  "source": "snapshot"
}
```

节点：

```text
i2c.i2c_core
u_fifos
u_i2c_bus_monitor
u_i2c_controller_fsm
u_i2c_target_fsm
```

## 3. 语义边界

snapshot 模式没有 MIG：

- 节点/端口来自图中已存在的 INSTANTIATED_MODULE / PORT_*；
- 不从 MIG 补端口；
- 不重新解析源码；
- 旧的 snapshot 仍可用，但其中没有后来新增的 FIFO 边。

live 模式仍使用 MIG ports + CONNECTION；两种模式的 `stats.source` 区分。

## 4. 验证

```text
test_from_snapshot: snapshot save + architecture --from-snapshot
4 architecture tests passed
```

## 5. 边界

- snapshot 中缺失的端口不会凭空补；
- 不是 cache：snapshot 需要预先构建；
- live 模式仍是最完整的端口来源。
