# Issue 17 案例记录

**问题**: 非ANSI端口 `p` 位宽丢失
**状态**: 记录为源代码问题 (非 sv_query bug)
**日期**: 2026-05-17

---

## 案例概述

| 项目 | clacc/bs_mult |
|------|---------------|
| 文件 | bs_mult.v |
| 模块 | bs_mult |
| 端口 | p (output) |
| 期望位宽 | [29:0] |
| 实际位宽 | (0, 0) - 未识别 |

---

## 问题现象

```
sv_query 提取结果:
  p: output     # 位宽丢失，应为 output [29:0]
```

---

## 根因分析

### 源代码问题

bs_mult.v 的端口声明方式不符合标准 SystemVerilog 规范：

```verilog
module bs_mult(clk, x, y, p, firstbit, lastbit);  // 非ANSI端口列表
    input clk;
    input x, y, firstbit, lastbit;
    output p;         // ⚠️ 没有位宽声明
```

**问题**: `p` 是 `output` 类型，但没有声明位宽 `[29:0]`。

### 标准 SystemVerilog 写法

```verilog
module bs_mult (
    input clk,
    input x, y, firstbit, lastbit,
    output [29:0] p    // ✅ 标准写法：带位宽的输出声明
);
```

或者非ANSI格式：

```verilog
module bs_mult (clk, x, y, p, firstbit, lastbit);
    input clk;
    input x, y, firstbit, lastbit;
    output [29:0] p;   // ✅ 非ANSI但有位宽声明
```

### 实际源代码缺少的内容

```verilog
output p;             // ❌ 缺少 [29:0]
// 应该有: output [29:0] p;
```

---

## sv_query 行为说明

sv_query 正确识别了：
- `p` 是一个 output 端口
- 但由于源代码没有位宽声明，无法提取位宽信息

**这不是 sv_query 的 bug**，而是源代码不符合 SystemVerilog 标准。

---

## 修复建议

如果需要正确提取 `p` 的位宽，需要修复 bs_mult.v 源代码：

```verilog
output [29:0] p;      // 添加位宽声明
```

或者使用 ANSI 端口声明风格：

```verilog
module bs_mult (
    input clk,
    input x, y, firstbit, lastbit,
    output [29:0] p
);
```

---

## 总结

| 分类 | 内容 |
|------|------|
| **问题类型** | 源代码不符合 SV 标准 |
| **影响** | sv_query 无法提取端口位宽 |
| **解决方案** | 修复源代码，添加显式位宽声明 |
| **sv_query 状态** | ✅ 行为正确，无需修复 |

---

## 相关文件

- 问题文件: `/Users/fundou/my_dv_proj/clacc/bs_mult.v`
- 记录文档: `docs/ISSUE_17_CASE_BS_MULT.md`