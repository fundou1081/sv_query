# svq_query evidence intent（P105）

**日期**: 2026-11-08
**状态**: 完成
**目标**: 让 agent 在失败/歧义时能复核源码，而不是只拿到 ID

---

## 1. 设计

新增：

```json
{
  "intent": "evidence",
  "snapshot": "deep",
  "signal": "top.u_mid.u_stage.mixed"
}
```

返回：

```json
{
  "file": "examples/.../deep_chain.sv",
  "line": 18,
  "source_line": "leaf u_leaf(...);",
  "source_context": [
    {"line": 17, "text": "logic [7:0] mixed;"},
    {"line": 19, "text": "assign mixed = leaf_q ^ 8'hA5;"}
  ]
}
```

为什么需要 `source_context`：

- snapshot 的 node `line` 指向声明行；
- 真正表达式可能在下一行；
- 只给 `file:line`，agent 无法读取，无法确认；
- 给 ±2 行上下文，agent 能确认 XOR/mux。

## 2. 实现

- tool 读取 `$SVQ_SNAPSHOT_DIR/<tag>.json` 的节点 `file/line`；
- 用 `$SVQ_SOURCE_ROOT` 解析相对源码路径；
- 只读取返回节点所在的少量行；
- 最多 80 个节点，单行 160 字符；
- 默认不返回 evidence；只有 `intent=evidence` 或 `evidence=true`。

## 3. deep_chain 验证

3 个固定调用：

```text
path din -> dout
neighborhood u_leaf.d depth2
evidence mixed
```

结果：

| 字段 | 期望 | 实际 |
|---|---|---|
| path | 12 nodes / 11 hops | ✅ |
| register | `...u_leaf.q` | ✅ |
| xor_node | `...mixed` | ✅ |
| mux_control | `...u_stage.sel` | ✅ |
| mux_node | `...u_leaf.d.ternary_sel` | ✅ |
| combinational | false | ✅ |

evidence 的关键行：

```text
19: assign mixed = leaf_q ^ 8'hA5;
```

这是之前 `xor_node=null` 的直接修复。

## 4. 当前状态

```text
Node tests: 23/23
deep_chain: 7/7 字段正确
mux: 结构 + 条件正确
3-cell direct: 6/6
```

## 5. 边界

- `SVQ_SOURCE_ROOT` 必须指向源码根；未设置时只有 file/line；
- snapshot/源码可能过期，tag 由调用方管理；
- evidence 只读返回节点，不允许任意路径读取；
- source_context 是 ±2 行，不是完整语义分析；
- `evidence` intent 不调用 `sv_query`，是 trusted metadata read；
- 未做正式评分；这是人工对照 ground truth。
