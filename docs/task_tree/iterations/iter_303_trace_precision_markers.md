# Iteration 303: trace JSON 粒度标记 + 粗粒度回退标注（PLAN P13.2）

**Metadata**:
- **Iteration #**: 303
- **Task Tree Level**: L2（PLAN `P13.2`）
- **Created**: 2026-10-27 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（agent 可区分位精确/总线回退；2500 passed）

## 🎯 问题

位查询在"位节点缺失/不支持"时回落总线，输出与位精确结果**同形**：
`fanin(p.a[1])` 返回 `{p}` 到底是"总线粒度回退"还是"真的只有总线驱动"，agent 无法判断。

## 🔧 实现

### 结果字段

每个 driver/load 节点：

```json
{"id": "top.a[1]", "precision": "bit"}       // 位/1-bit 标量/1'b0/1'b1
{"id": "top.u.y",  "precision": "bus"}       // 总线/切片/成员聚合
{"id": "4'b0",     "precision": "constant"}  // 未分解的常量总线
```

每个 signal 条目：

```json
{"precision": "bit" | "bus" | "unknown", "coarse_fallback": false}
```

判定规则：
| 查询形态 | precision | coarse_fallback |
|---|---|---|
| 非位查询（总线/切片） | `bus` | false（查询本身就是总线粒度） |
| 位查询，结果全是位 | `bit` | false |
| 位查询，混入总线/常量总线 | `bus` | **true**（回落/混合） |
| 位查询，空结果 | `unknown` | false |

**关键**：判定在 `_apply_filters` **之前**做——过滤会删掉总线节点，若过滤后判定会把粗粒度伪装成 bit。

## 🐛 顺带修的真 bug

CLI 位查询"图中不存在的位"（F1/F2 回退路径的常见入口）之前直接失败：

```
sv_query trace fanin top.y[3] --file ... --json
→ ok:false, error: "The node top.y[3] is not in the digraph."
```

根因：`attach_distances` 对不在图里的 root 做 BFS（networkx 抛错）。
修复：root 不在图时跳过 BFS（distance 保持默认），trace 正常返回回落结果。
这个 bug 之前被"CLI 只用存在的位查询"掩盖；P13.2 的测试把它暴露出来。

## 🧪 测试

新增 `test_trace_precision_markers.py`（6 个，subprocess CLI 级）：
- 位精确（切片 fanin：`a[1]`/precision=bit）
- 粗粒度回退（纯总线 one 模式：`u.y`/bus/coarse=true）
- 总线查询不标 coarse
- 空位查询 unknown
- fanout 位精确
- **过滤不掩盖 coarse**（exclude 掉总线节点后仍 coarse=true）

更新 3 个 CLI golden（新增 `precision`/`coarse_fallback` 字段，有意重生成）：
`type_REG_width_min_2` / `fanin_2signals` / `snapshot_fanin_type_REG`。

## ✅ 验证

- 全量：2494 → **2500 passed / 0 failed**
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 边界

- `precision` 是**结果粒度标记**，不是"位级依赖完整证明"；
  粗粒度回退会标 `coarse_fallback=true`，agent 应降级解读。
- 常量总线（`4'b0` 等）标 `constant`；P8 已能分解的常量会返回 `1'bX`（bit）。

## 🔗 相关

- 计划: [PLAN.md P13.2](../../../PLAN.md)
- 评审: [trace_capability_review_2026-10-27](../../architecture/trace_capability_review_2026-10-27.md)
- 前序: [iter_302 缓存模式](iter_302_cache_bit_bridge_key.md)
