# Iteration 298: 整数类型位宽提取（PLAN P10）

**Metadata**:
- **Iteration #**: 298
- **Task Tree Level**: L2（[L1_integer_width](../tasks/L1_integer_width.md) / PLAN `P10`）
- **Created**: 2026-10-26 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续做这个"）
- **Outcome**: ✅ 完成（integer/int/byte/shortint/longint/time 宽度正确；2471 passed）

## 🎯 问题

P9 修好了 signedness，但 `integer i;` 的**宽度**仍是 `(1,0)`（假 1 位）：

```
integer i;   // 实际 32-bit signed
```

后果：位查询/表达式映射把 integer 当 1 位（加宽判断、零扩展、位坐标全错）。

## 🔧 P10.1 位宽映射

`extract_data_width` 的 syntax 路径新增整数类型关键字（`DataDeclarationSyntax.type.keyword`）：

| 类型 | 宽度 | signed |
|---|---|---|
| `byte` | 8 | True |
| `shortint` | 16 | True |
| `int` / `integer` | 32 | True |
| `longint` | 64 | True |
| `time` | 64 | False |

同时修 `extract_data_signed` 的 syntax 回退：之前只认 `integer`（`int`/`byte`/`shortint`/`longint`
被误判 unsigned）；现在按类型矩阵返回，`time` 保持 unsigned。

## 🔧 P10.2 懒建节点回填

`integer` 常被 `always_ff` 先引用 → 节点以 `(1,0)` 懒建；变量声明阶段现在**回填**
声明宽度（与 net 的 width 回填同规则），不再"已存在就跳过"。

缓存 `CACHE_VERSION` 1.1 → 1.2（旧图的 integer 宽度是错的，必须重建）。

## 📊 效果

| 声明 | 修复前 | 修复后 |
|---|---|---|
| `integer i;` | `(1,0)` | `(31,0)` signed |
| `int j;` | `(1,0)` | `(31,0)` signed |
| `byte b;` | `(1,0)` | `(7,0)` signed |
| `shortint si;` | `(1,0)` | `(15,0)` signed |
| `longint li;` | `(1,0)` | `(63,0)` signed |
| `time t;` | `(1,0)` | `(63,0)` unsigned |

`logic [7:0]` / 端口宽度不变；6 个图基线无差异（fixture 未含整数类型声明）。

## 🧪 测试（`test_integer_width.py`，7 个）

- integer 32-bit signed / 类型矩阵（int/byte/shortint/longint/time/logic）
- 端口宽度不变 / JSON 往返
- **懒建回填**（always 先引用 integer）
- integer 位查询回落总线（不崩、不空答）
- for 循环变量宽度

## 📌 边界（KNOWN_LIMITATIONS §3.6）

- integer 的**算术逐位**（`i <= i + 1` 的进位链）仍无 per-bit 节点 → 位查询回落总线
- packed struct/union 的宽度/signedness 未建模

## 🔗 相关

- 计划: [PLAN.md P10](../../../PLAN.md)
- 前序: [iter_297 signedness](iter_297_signedness.md)
