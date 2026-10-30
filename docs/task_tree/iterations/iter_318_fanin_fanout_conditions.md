# Iteration 318: fanin/fanout 条件输出（PLAN P22.1）

**Metadata**:
- **Iteration #**: 318
- **Task Tree Level**: L2（PLAN `P22.1`）
- **Created**: 2026-10-30 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先1 后2"）
- **Outcome**: ✅ 完成（直接边条件进 JSON；2591 passed）

## 🎯 问题（实测）

```systemverilog
always_comb if (sel) y = a; else y = b;
```

`fanin(y)` 只返回 `a, b`，`conditional_drivers=true` 但**没有条件文本/条件信号**；
agent 想知道“y 在什么条件下取 a”，必须再调 `controlflow` —— 不能连续追问。

## 🔧 实现

新增 `attach_edge_conditions`（`trace_common.py`）：

| 字段 | 含义 |
|---|---|
| `signal.conditions` | 查询端点**直接边**条件并集（去重，保持出现顺序） |
| `node.condition` | 该结果节点直接边条件；多条边用 `" \| "` 连接 |
| `node.conditions` | 原始列表 |

- fanin: 结果节点 → 查询端点（`[sig, _root]`）
- fanout: 查询端点 → 结果节点
- 条件取 `edge.condition`；为空退化 `condition_chain`（` && `）/`effective_condition`
- 跳过 `BIT_SELECT`；无条件的普通连接仍输出空字段（契约稳定）
- **不吞异常**：图接口异常直接失败（纪律：禁 silent fallback）

## 📊 效果

```
fanin y (if/else):
  conditions = ["sel", "!sel"]
  a: condition="sel",  conditions=["sel"]
  b: condition="!sel", conditions=["!sel"]

fanout a (if (sel) x=a):
  conditions = ["sel"]; x.condition="sel"

无条件的 y=a:
  conditions=[]; driver.condition=""; driver.conditions=[]
```

## 🧪 测试

新增 `test_trace_conditions.py`（5）：
if/else、ternary、fanout、嵌套 if 条件、无条件字段存在。
3 个 CLI golden **有意重生成**（新增 condition/conditions 字段）。
全量：2586 → **2591 passed / 0 failed**。

## 📌 边界

- 只给**直接边**条件；`depth>1` 的深层 driver 没有直接边 → 条件为空（不猜测路径条件）
- 条件文本来自语义树显示，`!sel`/`!(sel)` 两种写法都可能出现；agent 应按文本识别，不做字符串规范化
- 多条同向边用 `" | "` 连接，精确语义看 `conditions` 列表

## 🔗 相关

- 计划: [PLAN.md P22.1](../../../PLAN.md)
- 前序: [iter_317 真实工程 smoke](iter_317_real_project_smoke.md)
