# svq_query details / mux probe（P100）

**日期**: 2026-11-08
**状态**: details 完成；bounded neighborhood 未做
**范围**: 受限工具 + mux snapshot

---

## 1. 新增 details

`svq_query` 增加：

```json
{"details": true}
```

fanin/fanout/neighbors 现在可返回：

```json
"driver_details": [
  {"id": "...", "kind": "SIGNAL|REG|OP_TERNARY", "condition": "sel[0]", "distance": 1}
]
```

不开启 details 时，输出保持原来的 ID-only schema。

Node tests：14/14 通过。

---

## 2. mux probe

snapshot：`mux`（`examples/interactive_debug/mux_neighborhood.sv`）

agent 只用 `svq_query` + details，递归 fanin 后返回：

```text
mux_nodes:
  top.u.lo.ternary_sel[0]
  top.u.hi.ternary_sel[0]
  top.u.y.ternary_sel[1]

data_sources:
  top.u.a / b / c / d

conditions:
  sel[0] / !(sel[0]) / sel[1] / !(sel[1])
```

结构识别基本正确。

### 仍存在的问题

- selects 返回了 `top.sel[0]/[1]`，而 canonical 期望是 `top.u.sel[0]/[1]`；
- conditions 返回 4 条分支条件，而任务 ground truth 是 2 条 select 条件；
- 说明工具还需要 **canonical alias / condition 语义**，不能只加 details；
- 这次没有做自动评分，不应写成 mux 任务通过。

---

## 3. 结论

```text
details 解决了“看不到 kind/condition”的问题；
但没有完全解决 alias 和条件语义。
```

## 4. 下一步

P100.3：

```text
intent: "neighborhood"
```

由工具自己做 bounded fanin BFS，返回：

```text
nodes [{id, kind, depth}]
edges [{src, dst, kind, condition}]
selects []
```

而不是让模型手工递归和推断 alias。
