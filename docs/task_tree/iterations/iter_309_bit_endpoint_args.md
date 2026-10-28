# Iteration 309: `--bits` 位级端点归一化（paths/dataflow/impact，PLAN P15）

**Metadata**:
- **Iteration #**: 309
- **Task Tree Level**: L2（PLAN `P15`）
- **Created**: 2026-10-28 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "位级 paths/impact 便捷入口"）
- **Outcome**: ✅ 完成（三个命令支持 `--bits`；2540 passed）

## 🎯 问题

`paths` / `dataflow analyze` / `trace impact` 只接受**图中已存在的节点 id**：
要查位级关系必须手写 `top.a[1]`；位节点不存在时只能失败，没有"回落总线"的显式语义。

## 🔧 实现

新增 `cli/core/semantic/_bit_args.py`：

| 函数 | 作用 |
|---|---|
| `parse_bits(raw)` | 解析逗号分隔位索引；负数/空值/非整数 → 明确报错 |
| `normalize_endpoint(graph, signal, bit)` | 位节点存在 → `signal[bit]`（precision=bit）；缺失但总线存在 → 总线（precision=bus, coarse_fallback=true）；都没有 → 原样（后续未知错误） |

命令接入：

| 命令 | `--bits` 形态 | 输出 |
|---|---|---|
| `paths SRC DST` | `src_bit,dst_bit` | `src_resolved`/`dst_resolved`/`bits{src,dst,coarse_fallback}` |
| `dataflow analyze FROM TO` | `src_bit,dst_bit` | `from_resolved`/`to_resolved`/`bits` |
| `trace impact SIG` | 单位（单信号）或逗号列表（batch 对齐） | 每信号 `resolved_signal`/`requested_bit`/`precision`/`coarse_fallback` |

错误处理：数量不匹配、信号已带 `[n]` 再给 `--bits`、非法索引 → 非零退出（不静默）。

## 📊 效果

```
svq paths top.a top.y --bits 1,5 --directed
→ src_resolved=top.a[1], dst_resolved=top.y[5], path=[top.a[1], top.y[5]]

svq paths top.a top.y --bits 1,3    # y[3] 不存在（切片是 [7:4]）
→ dst_resolved=top.y, precision=bus, coarse_fallback=true

svq trace impact top.a --bits 1
→ resolved_signal=top.a[1], precision=bit, total_paths>=1

svq trace impact --batch top.a,top.y --bits 1,5
→ 两个信号各自解析到 a[1]/y[5]
```

## 🧪 测试

新增 `test_bit_endpoint_args.py`（7 个）：
- paths 位端点路径命中 / 位节点缺失回落 / 数量不匹配失败 / 已带位索引冲突
- dataflow 位端点可达 + resolved 字段
- impact 单位 / batch 对齐

## ✅ 验证

- 全量：2533 → **2540 passed / 0 failed**
- 无图结构变化；无缓存版本变更
- check_docs / check_plan / check_cli_layers / check_except_pass / gen_cli_surface --check 全绿

## 📌 边界

- `--bits` 只做**端点归一化**：路径/影响本身仍是节点级（位节点存在时天然按位）
- 不支持的位形态（位节点缺失）显式 `coarse_fallback=true`，回答退化为总线级
- `paths` 的未知 id 仍按原逻辑报错（提示 `graph nodes --json`）

## 🔗 相关

- 计划: [PLAN.md P15](../../../PLAN.md)
- 前序: [iter_308 动态索引](iter_308_dynamic_index_unknown.md)
