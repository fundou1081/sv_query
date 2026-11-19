# P186.1 — shadow-node 测量

> **状态**: 测量完成；**不做图清理**。
> **工具**: `python3 tools/measure_shadow_nodes.py [--json]`
> **日期**: 2026-11-19

## 1. 定义

shadow node = 图节点满足：

1. 不属于任何实例路径（top module + `get_instances()` 的 full_path）；
2. 不是 `NodeKind.CONST` / 字面量常量。

实例前缀包含 top（`get_instances()` 不含 top，因此显式加入），否则顶层端口会被误判。

## 2. 当前结果

| fixture | nodes | shadow | ratio | shadow edges | cross edges | reachable from top inputs |
|---|---:|---:|---:|---:|---:|---:|
| minimal_3module | 31 | 0 | 0.0000 | 0 | 0 | 0 |
| scheduler_minimal | 88 | 0 | 0.0000 | 0 | 0 | 0 |
| golden_mini | 55 | 0 | 0.0000 | 0 | 0 | 0 |
| generate_forms | 34 | 0 | 0.0000 | 0 | 0 | 0 |
| wrapper_chain | 34 | 0 | 0.0000 | 0 | 0 | 0 |

`shadow_by_module` 全部为空；`shadow_isolated=0`。

## 3. 与 2026-10-23 POC 的差异

旧 POC：

```text
minimal_3module: 17 shadow / 44 nodes = 38.6%
scheduler:       30 shadow / 98 nodes = 30.6%
```

当前测量：

```text
minimal_3module: 0 shadow / 31 nodes
scheduler:       0 shadow / 88 nodes
```

差异来自后续单一命名空间/实例级图清理（iter_276 及之后的图变更）；旧 POC 的
`1` 个 `0` 节点在本次分类中属于 CONST，不是 shadow。结论：**当前 fixture 上
shadow 已经是 0，不需要 P186.2 的 drop_shadows 清理**。

## 4. query path 影响

因为图中 shadow=0：

- `graph nodes` 不会枚举 shadow；
- `paths` 没有可返回的 shadow 端点；
- `dataflow`/drivers/loads 不会跨 shadow 命名空间；
- 没有 shadow 边或 cross-namespace 边。

这不是“把所有图都证明为无 shadow”，而是**当前 5 个 fixture 的实测结果**；
大工程/未来符号扩展仍需用同一工具复测。

## 5. 决策建议（P186.2）

```text
保留当前单一图/默认行为；
不新增 drop_shadows API；
不删除/重排 definition namespace；
P186 可关闭，保留 measurement 工具作为回归探针。
```

理由：

- 当前 shadow=0，清理无收益；
- 旧 POC 的 30~38% 已被后续图变更消除；
- 删除/过滤会改变图语义和 query 输出，风险大于收益。

## 6. 限制

- 5 个小 fixture，不代表大工程；
- `get_instances()` 不含 top，工具已显式加 top；若未来 MIG API 变化需复测；
- 常量/非法字面量按 `NodeKind.CONST` 排除，可能掩盖“非实例常量”分类问题；
- 不做路径质量/性能测量。

## 7. 复现

```bash
python3 tools/measure_shadow_nodes.py
python3 tools/measure_shadow_nodes.py --json
```
