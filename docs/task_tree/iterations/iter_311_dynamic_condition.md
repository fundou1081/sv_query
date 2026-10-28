# Iteration 311: 动态条件传播（PLAN P17）

**Metadata**:
- **Iteration #**: 311
- **Task Tree Level**: L2（PLAN `P17`）
- **Created**: 2026-10-29 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "动态条件传播？这个深挖一下"）
- **Outcome**: ✅ 完成（条件/时钟/复位/控制依赖传播；2555 passed）

## 🎯 背景

P16 的传播只看 `edge.expression`，而条件写在 **`edge.condition` / `condition_chain`**：
```systemverilog
if (mem[i] > 0) y <= a; else y <= b;      // y 的 DRIVER 边 expr='a'，cond='mem[i] > 0'
case (mem[i]) ...                          // cond="mem[i] == 8'd0"
```
P16 实测：`y` 的 dynamic=false，precision=bus —— 漏标。

## 🔧 实现

扩展 `_mark_dynamic_provenance`：

| 项 | 规则 |
|---|---|
| 种子 | 表达式**或条件**（condition/effective_condition/condition_chain）含运行期索引 → 目标 dynamic |
| 条件依赖 | 条件引用了已标记 dynamic 的信号（如 `t=mem[i]; if (t)`）→ 目标 dynamic |
| 分支/选择 | 传播沿 `BRANCH_*`/`CASE_*`（动态值作 `?:` /case 选择） |
| 时钟/复位 | 传播沿 `CLOCK`/`RESET`（动态值当 clock/reset，时序行为运行期决定） |
| 多边同对 | 用 `get_edges` 判任一边类型（旧实现 `get_edge` 只取第一条） |

条件里的**参数/常量**（`a[P-1:0]`）仍按同 module 作用域解析，不误报。
缓存版本 **1.7**（算法变化，旧 1.6 图缺条件标记）。

## 🐛 深挖时找到的坑

1. **条件字段完全没扫**：if/case/clock 的 `mem[i]` 只存在于 `edge.condition`。
2. **`mem[i][0]` 的占位节点**：图上出现 `mem[?]` / `mem[?][?][0]`（`?` 不是标识符），
   靠节点 id 识别不到，必须扫条件文本。
3. **计算后的动态条件**：`t=mem[i]; if (t)` 条件里没有 `mem[i]`，
   需要"条件引用了 dynamic 节点"的二次传播。
4. **动态 clock/reset**：`posedge t`（t 动态）此前 q 不标 unknown；已加 CLOCK/RESET。
5. **多边同对只取第一条**：`get_edge` 在 CLOCK+DRIVER 同对时可能漏判；改 `get_edges`。

## 📊 效果（全部 unknown + dynamic=true）

| 写法 | 修复前 | 修复后 |
|---|---|---|
| `if (mem[i] > 0) y<=a` | bus | **unknown** |
| `case (mem[i])` | bus | **unknown** |
| `if (mem[i][0])`（`mem[?]` 占位） | bus | **unknown** |
| `t=mem[i]; if (t)` | bus | **unknown** |
| `posedge t`（t 动态） | bus | **unknown** |
| `negedge t`（t 动态复位） | bus | **unknown** |
| `if (a[P-1:0])`（参数） | bus | bus（不误报） |

## 🧪 测试

`test_trace_dynamic_index.py` +8：if 条件 / case / `mem[i][0]` / 计算条件 /
动态 clock / 动态 reset / 参数条件防误报 / 静态条件不标记。
（P16 深链/depth=1/fanout/动态写/序列化测试保持通过。）

## ✅ 验证

- 全量：2547 → **2555 passed / 0 failed**
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿
- 缓存 1.6 → **1.7**

## 📌 边界

- 条件里的层次化引用（`u.q`）按短名可能漏判；包/宏/转义名同理
- 动态值作为普通 `always @(a or b)` 敏感列表（非 clock/reset）未传播
- 只标记"运行期依赖"，不区分分支是否实际被选中

## 🔗 相关

- 计划: [PLAN.md P17](../../../PLAN.md)
- 前序: [iter_310 动态传播](iter_310_dynamic_provenance_deep.md)
