# Bit-select discoverability hints — P191.1 contract

> **状态**: P191.1 contract + P191.2/P191.3 output wiring 已完成；P191.4 regression 锁定。
> **原则**: 只加路标，不改真相层；bus 级 `false`/空仍是原语义。

## 1. drivers / loads

每个 `signals[]` row 可选附加：

```json
{
  "has_bit_select_drivers": true,
  "bit_nodes": [
    {
      "id": "top.bus[PPNWMin:12]",
      "parent_bus": "top.bus",
      "bit_range": {"msb": "PPNWMin", "lsb": "12"}
    }
  ]
}
```

- `drivers` 用 `has_bit_select_drivers`；`loads` 用 `has_bit_select_loads`；
- `bit_nodes` 只列直接 `parent_bus[...]` 后代，不合并成 bus 结论；
- 字段只在存在 bit 后代时出现；无 bit-select 时默认键不变；
- `has_*` 分别表示该 bit 节点有入边（drivers）/出边（loads）。

## 2. dataflow

`dataflow analyze` 在 bus 端点结果为 false/0 时，可选附加：

```json
{
  "bit_node_paths_exist": true,
  "bit_node_paths": [
    {"from": "top.bus[63:38]", "path_count": 1}
  ]
}
```

- `is_reachable` 仍保持 `false`，不改成 `unknown`；
- 只有 bus endpoint 的直接 bit 后代存在路径时才出现；
- 这是“还有位级路径”的路标，不是 bus 级可达结论。

## 3. 不变量

- 既有 key/type 不变；
- 不默认展开/合并 bit 结果；
- `--bits` / 自动展开是后续 opt-in，不属于本 contract；
- 无 bit-select 的普通信号不产生 hint。
