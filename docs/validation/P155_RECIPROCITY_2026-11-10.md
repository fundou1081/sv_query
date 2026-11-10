# P155 reciprocity BIT_SELECT false positives

**日期**: 2026-11-10
**状态**: ✅

## 1. 问题

P152 worker 观察到 SPI_HOST：

```text
verify consistency --checks reciprocity
sample: 9 violations
--full: 128 violations
```

全部落在 `prim_arbiter_tree` / `prim_alert_sender` 的 generate 层次，
不是 SPI_HOST 逻辑。

## 2. 根因

`trace_fanin` 会返回 **BIT_SELECT 结构边**（generate/struct child → parent），
而 `trace_fanout` 不把这种层次边当数据负载。 reciprocity 却拿两者直接比较，
于是出现假 `fanin_not_reciprocal`。

## 3. 修复

reciprocity 只比较 **DRIVER / CONNECTION** 数据边：

```python
def _has_data_edge(graph, a, b):
    return any(e.kind.name in ("DRIVER", "CONNECTION")
               for e in graph.get_edges(a, b))
```

BIT_SELECT/hierarchy 边不参与互逆检查。

## 4. SPI 结果

```text
sample 9  -> 0
--full 128 -> 0
```

## 5. 测试

```text
test_verify_reciprocity.py: 1 passed
```

构造只有 BIT_SELECT 的 pair，确认不报 reciprocity violation。

## 6. 边界

不是关闭 reciprocity；真实 DRIVER/CONNECTION 不互逆仍会报。
