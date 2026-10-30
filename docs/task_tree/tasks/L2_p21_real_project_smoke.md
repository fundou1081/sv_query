# L2 — P21 真实工程查询 smoke

**Created**: 2026-10-30 GMT+8
**方豆指令**: "先1 后2"（先真实工程 smoke，再做 fanin/fanout 条件输出）。

## 目标

P13~P20 改动了图语义、动态/函数标记、缓存 key；全量门禁主要是 fixture。
用真实多文件工程验证：

1. 构建不回归（节点/边规模合理、无异常）
2. agent 常用查询可执行（fanin/fanout、位查询）
3. 精度标记可信（strict_uart 动态读 → unknown/dynamic；普通位查询 → bit）
4. 缓存复用不丢标记（图缓存 key v9）

## 工程与查询

| 工程 | 类型 | 查询 |
|---|---|---|
| strict_uart | 仓库内多文件 fixture | `rx_data_o`（动态 memory 读）、`rx_data_o[3]`、fanout mem |
| verilog-axi | 外部真实 RTL（56 文件） | `axi_adapter...m_axi_araddr[0]` fanin |
| picorv32 | 外部真实 RTL（单文件） | `picorv32_axi.mem_rdata[16]` fanin |

外部路径不存在时 smoke 标记 skipped，不算失败。

## 验收

- `tools/smoke_real_projects.py --project all --json` 返回 0
- 每项查询 `ok=true`，字段 `precision/coarse_fallback/dynamic_index/function_call` 齐全
- strict_uart 动态标记为 true；picorv32 位查询 precision=bit
- 输出含 graph nodes/edges、dynamic/function 节点数、查询摘要
- 仓库内 smoke 测试（strict_uart）进全量门禁
