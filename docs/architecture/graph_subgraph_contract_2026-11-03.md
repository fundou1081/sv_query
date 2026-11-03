# `graph subgraph` 契约（P60.1/P60.2）

**日期**: 2026-11-03
**状态**: 已实现（P60）
**计划**: [structural_review_plan_2026-11-02.md](structural_review_plan_2026-11-02.md) §5

---

## 1. 命令

```bash
svq graph subgraph <seed...> \
  --depth 2 \
  --direction in|out|both \
  --edge-kinds driver,connection \
  --max-nodes 80 \
  --max-edges 160 \
  --evidence \
  --json
```

- seed 先经 `resolve_signal`（exact/relative/ambiguous/not_found）；
- 只接受 canonical graph 节点进入 core；
- 部分 seed 无法解析时：至少一个有效 seed → `ok=true`，`errors` 记录失败项；
- 全部失败 → `ok=false`。

## 2. 边类型

| `--edge-kinds` | 匹配 |
|---|---|
| `driver`（默认） | `EdgeKind.DRIVER`（含条件驱动） |
| `connection`（默认） | `EdgeKind.CONNECTION` |
| `control` | 带 `condition`/`condition_chain` 的 DRIVER |
| `clock` / `reset` | `CLOCK` / `RESET` |
| `bit_select` / `member_select` | 聚合/成员边（**不默认**） |
| `branch` | BRANCH_* / CASE_* 条件分支边 |

默认排除 clock/reset 和聚合边，避免 review 图被结构边淹没。

## 3. 返回

```json
{
  "ok": true,
  "command": "graph_subgraph",
  "params": {...},
  "seeds": [
    {"requested": "top.u.addr", "resolved": "top.u.addr", "status": "exact"}
  ],
  "result": {
    "nodes": [...],
    "edges": [...],
    "boundary": ["..."],
    "truncated": {"nodes": false, "edges": false, "depth": false},
    "stats": {"visited": 42, "returned_nodes": 42,
              "returned_edges": 61, "max_depth": 2}
  },
  "errors": []
}
```

### node

`id/kind/module/width_msb/width_lsb/width/precision/parent/bit_range/is_signed`；
`--evidence` 追加 `file/line`。

### edge

`src/dst/kind/expression/condition/bit_slice/assign_type`；
`--evidence` 追加 `file/line`。

## 4. 预算与截断

- `max_nodes` 含 seed；
- `max_edges` 只计算两端都在结果内的边；
- 到达 `depth` 或预算时，未纳入的邻居进入 `boundary`；
- `truncated.depth/nodes/edges` 显式；
- 不返回图外邻居的边。

## 5. 确定性

- 节点按 id 排序；
- 边按 `(src,dst,kind,condition,expression,bit_slice)` 排序；
- 两次同参数结果一致（测试锁定）。

## 6. 边界

- seed 的位回退解析若目标节点不存在，按 not_found 处理；
- 不做路径枚举（那是 `paths`/`dataflow`）；
- 不做布局/着色/HTML；
- 不修改图。
