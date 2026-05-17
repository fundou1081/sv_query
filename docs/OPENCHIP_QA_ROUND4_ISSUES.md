# OpenChip QA Round 4 - 问题修复状态

**更新时间**: 2026-05-17
**问题**: Issue 17 (非ANSI位宽) / Issue 19 (top前缀) / Issue 20 (边数少)

---

## Issue 19: ✅ 已修复

**问题**: 实例节点前缀错误使用 "top" 而非模块名 "bs_mult"

**根因**: `graph_builder.py` 中硬编码 "top" 作为根模块前缀

**修复内容**:
1. 在 `ConnectionExtractor.__init__` 添加 `self.root_module_name = None`
2. 在 `extract()` 开始时动态获取第一个模块名
3. 将所有硬编码的 `"top."` 替换为 `f"{self.root_module_name}."`

**验证结果**:
```
修复前: top.I0.clk, top.I0.pout, ...
修复后: bs_mult.I0.clk, bs_mult.I0.pout, ...

top.* 前缀: 0 个 (期望 0) ✅
bs_mult.* 前缀: 379 个 (期望 > 0) ✅
```

**Commit**: `94ad7fa fix: Issue 19 - 动态获取根模块名而非硬编码 top`

---

## Issue 20: 🔍 已确认 - 非bug

**问题**: 边数只有 3，LOAD/CONNECTION 边为 0

**分析结果**:

当只解析 `bs_mult.v` 时：
- bs_mult_slice 模块不在解析范围内 (在单独的 bs_mult_slice.v 文件中)
- 无法获取 bs_mult_slice 的端口定义
- ConnectionExtractor 无法建立实例连接边
- 边数只有 3 (来自 assign 语句的 DRIVER 边)

**验证**:
```
解析 bs_mult.v 一个文件:
  节点数: 379, 边数: 3 (DRIVER: 3)

解析 bs_mult.v + bs_mult_slice.v 两个文件:
  节点数: 411, 边数: 708 (CONNECTION: 587, DRIVER: 118)
```

**结论**: Issue 20 不是 bug，是正常的解析范围行为。
- sv_query 设计为需要解析所有相关文件才能获取完整连接信息
- 用户需要确保传入所有相关的 Verilog 文件

**建议**: 在文档中说明 sv_query 需要完整解析所有相关文件

---

## Issue 17: 🔍 分析中

**问题**: 非ANSI端口 `p` 位宽丢失 (应该是 output [29:0])

**现象**:
```
p: output (msb=None)  # 位宽丢失
```

**分析**:

bs_mult 使用非ANSI端口声明：
```verilog
module bs_mult(clk, x, y, p, firstbit, lastbit);
    input clk;
    input x, y, firstbit, lastbit;
    output p;      // 位宽在 separate declaration 中定义
```

位宽 [29:0] 定义在 separate NetDeclaration：
```verilog
wire [29:0] pout;  // p 的位宽在这里定义
```

**问题**: p 没有单独的 NetDeclaration，它的位宽需要从实例连接推断

**从实例连接推断**:
- I0.pout -> p (output [29:0])
- pout 是 wire [29:0]
- 因此 p 也是 output [29:0]

**结论**: Issue 17 需要实现"从实例连接推断端口位宽"的功能

---

## 修复优先级

| Issue | 状态 | 说明 |
|-------|------|------|
| Issue 19 | ✅ 已修复 | 节点前缀使用动态模块名 |
| Issue 20 | ✅ 确认非bug | 解析范围问题，需解析所有相关文件 |
| Issue 17 | 🔍 待修复 | 需要实现从实例连接推断位宽 |

---

## 下一步

1. **Issue 17 修复**: 实现从实例连接推断端口位宽
   - 当 extract_port_width 返回 (0,0) 时
   - 查找连接到此端口的信号位宽
   - 使用该位宽作为端口位宽

2. **Issue 20 文档**: 说明 sv_query 需要完整解析所有相关文件

3. **继续 Round 4 测试**: 继续其他项目的测试