# Iteration 312: 层次化条件作用域（PLAN P18.1）

**Metadata**:
- **Iteration #**: 312
- **Task Tree Level**: L2（PLAN `P18.1`）
- **Created**: 2026-10-29 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按顺序做1 2 3"）
- **Outcome**: ✅ 完成（层次条件解析；2558 passed）

## 🎯 两个层次化缺口

```systemverilog
sub u(.q(w));                    // w 只是连线名
if (u.q > 0) y = a; else y = b;
```

1. **单层**：条件文本 `u.q`，旧解析只试 `top.u`/`top.q`，`top.u.q` 解析不到 →
   动态依赖丢失（实测即使端口接不同线名，y 仍 `precision=bus`）。
2. **深层**：`if (u.u2.q > 0)` 在条件字符串里被抽成 `q`（`get_signal` 的
   HierarchicalValue 分支按“当前 module 的实例端口”匹配，深层不匹配时退回叶名），
   图上存在 `top.u.u2.q`，但条件里只剩 `q`。

## 🔧 修复（`_mark_dynamic_provenance` 解析层）

| 规则 | 说明 |
|---|---|
| 层次路径解析 | `u.q` / `u.u2.q` / `top.u.q` → `{module}.{ref}` 或绝对节点 id |
| 令牌切分 | 先匹配带点的层次路径，再匹配简单标识符（避免把 `u.q` 拆成 `u`+`q`） |
| 退化兜底 | 简单名直接解析失败、且**不在 `[...]` 内**时，按叶名找同 module 后代（`q` → `top.u.q`/`top.u.u2.q`） |
| 防误报 | 括号内不做后代兜底（`a[P-1:0]` 的参数 P 不会命中其它模块端口 `top.u.P`） |

条件目标映射仍是 `cond_targets[ref] → dst`：只要某个候选节点 dynamic，条件目标就 dynamic。

## 📊 效果

| 写法 | 修复前 | 修复后 |
|---|---|---|
| `if (u.q)`（端口接 `w`） | `precision=bus, dynamic=false`（错） | **`unknown, dynamic=true`** |
| `if (u.u2.q)`（深层） | bus（条件退化成 `q`） | **unknown, dynamic=true** |
| `if (top.u.q)`（绝对路径） | bus | **unknown, dynamic=true** |
| `if (a[P-1:0])`（参数，其它模块有 P 端口） | bus | bus（不误报） |

## 🧪 测试

`test_trace_dynamic_index.py` +3：
- 实例端口条件（`u.q`，端口接不同线名）
- 深层层次条件（`u.u2.q`，条件字符串退化）
- 绝对路径条件（`top.u.q`）
原有参数条件防误报、动态条件/时钟/复位测试保持通过。

## ✅ 验证

- 全量：2555 → **2558 passed / 0 failed**
- 图结构不变（仅 dynamic 标记）；缓存算法未变（1.7）
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 边界（已知、暂不做）

- 条件**显示文本**里的深层层次名仍可能退化成叶名（controlflow 输出同样）；
  本次只保证 dynamic 解析保守正确，不改 `get_signal` 的全局行为
- 叶名兜底可能把同名后代都视为候选（multiple candidates → 只要一个 dynamic 就标 unknown，偏保守）
- 包/宏/转义标识符仍可能解析不到

## 🔗 相关

- 计划: [PLAN.md P18.1](../../../PLAN.md)
- 前序: [iter_311 动态条件](iter_311_dynamic_condition.md)
