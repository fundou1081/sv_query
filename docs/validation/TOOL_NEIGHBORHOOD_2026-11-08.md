# svq_query bounded neighborhood（P100.3）

**日期**: 2026-11-08
**状态**: 完成，mux 结构验证通过；条件语义仍有边界
**范围**: `svq_query intent=neighborhood`

---

## 1. 实现

```json
{
  "intent": "neighborhood",
  "snapshot": "mux",
  "signal": "top.q",
  "depth": 5
}
```

工具内部做 bounded fanin BFS（最多 100 节点，depth 1..8），返回：

```json
{
  "nodes": [{"id": "...", "kind": "REG|SIGNAL|OP_TERNARY", "depth": 1}],
  "edges": [{"src": "...", "dst": "...", "kind": "...", "condition": "..."}],
  "op_ternary": ["..."],
  "conditions": ["..."],
  "count": 12,
  "truncated": false
}
```

每次 BFS 用 `sv_query drivers --from-snapshot`，不读 source。

## 2. mux 结果

`top.q` depth 5：

```text
mux_nodes:
  top.u.y.ternary_sel[1]
  top.u.lo.ternary_sel[0]
  top.u.hi.ternary_sel[0]

selects:
  top.u.sel[0]
  top.u.sel[1]

data_sources:
  top.u.a / top.u.b / top.u.c / top.u.d
```

与 mux ground truth 的三个 OP_TERNARY、两个 select、a/b/c/d 一致。

### 条件字段

工具现在同时返回：

```text
conditions:
  !(sel[1]) / sel[1] / sel[0] / !(sel[0])

condition_atoms:
  sel[1] / sel[0]
```

- `conditions`：图事实，4 条分支条件；
- `condition_atoms`：去掉极性后的条件原子，2 条 select 条件。

mux 复测输出：

```text
conditions: ["sel[1]", "sel[0]"]
```

与任务要求的两个 select 条件一致（顺序不同，语义一致）。

所以不再把两种粒度混成一个字段。

## 3. 深度

depth 4 时 `top.u.sel[0]` 在第 5 跳，未返回；depth 5 才完整。  
这说明 BFS 深度必须由工具/任务明确，不能默认太小。

## 4. 边界

- fanin-only；
- 每个节点一次 `sv_query` 调用，大邻域会慢；
- 100 节点截断；
- 无 MIG；
- `condition_atoms` 是展示层归一化，不是布尔求解；
- 未做正式评分；
- 未加纯 BFS 单元测试（BFS 依赖真实 `sv_query`）。

## 5. 结论

```text
bounded neighborhood 可用；
mux 的 mux_nodes/selects/data_sources 已正确；
condition_atoms 解决了条件粒度。
```

下一步：
1. 给 neighborhood 加 Node 层纯 BFS 单元测试（worker 可做）；
2. 明确 `conditions` vs `select_conditions` schema；
3. 用 deep_chain 再做一次。
