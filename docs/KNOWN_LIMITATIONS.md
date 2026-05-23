# 已知限制汇总

> 本文档记录 sv_query 项目中发现的所有已知限制，用于追踪和计划修复。

最后更新: 2026-05-23

---

## 一、失败测试（9 个 - 需要修复 tracer）

这些测试当前失败，需要修复 tracer 代码后通过。

| 测试文件 | 测试方法 | 限制描述 | 根本原因 |
|----------|----------|----------|----------|
| test_aliases.py | test_alias | `alias b = a` 应追踪到 a | alias 语句暂不支持 |
| test_operators.py | test_ternary | 三元运算符 `sel ? a : b`，sel 应为驱动源 | 条件选择信号未被识别为驱动源 |
| test_operators.py | test_complex_expression | 复杂表达式中 sel 应为驱动源 | 同上 |
| test_system_tasks.py | test_floor | `$floor(r)` 函数参数 r 应为驱动源 | 函数调用的输入参数未被识别为驱动源 |
| test_boundary.py | test_case_sensitive_signal | `Din` 和 `din` 应区分 | 大小写敏感暂未支持 |
| test_boundary.py | test_dollar_in_name | `$data` 美元符信号应支持 | 美元符信号名暂未支持 |
| test_boundary.py | test_parameterized_module | 参数化模块 `dout = din` 应追踪到 din | 参数化模块暂未完全支持 |
| test_boundary.py | test_signal_without_module_prefix | 不带模块名查询 `dout` 应找到 | 不带模块名查询暂不支持 |
| test_complex_conditions.py | test_case_inside_if | `case (1'b1) a: y<=1; default: y<=0;` 应返回 2 驱动 | priority case default 分支暂未追踪 |

---

## 二、失败测试详细说明

### 2.1 alias 语句不支持
```systemverilog
module top(input a, output b);
    alias b = a;  // 应追踪 b <- a
endmodule
```
当前返回 0 驱动，期望 1 个驱动 (top.a)

### 2.2 三元运算符 sel 未追踪
```systemverilog
assign y = sel ? a : b;  // sel 是控制信号，应参与驱动追踪
```
当前返回 2 驱动 (a,b)，期望 3 个驱动 (sel,a,b)

### 2.3 $floor() 函数参数未追踪
```systemverilog
assign f = $floor(r);  // r 是输入参数，应参与驱动追踪
```
当前返回 0 驱动，期望 1 个驱动 (top.r)

### 2.4 大小写敏感未支持
```systemverilog
module top(input Din, input din, ...);  // Din 和 din 是不同信号
```
当前返回 0 驱动，期望 1 个驱动 (top.Din)

### 2.5 美元符信号名未支持
```systemverilog
module top(input $data, output dout);
    assign dout = $data;
endmodule
```
当前返回 0 驱动，期望 1 个驱动 (top.$data)

### 2.6 参数化模块未支持
```systemverilog
module #(parameter WIDTH = 8) top(...);
    assign dout = din;  // din 宽度使用 WIDTH 参数
endmodule
```
当前返回 0 驱动，期望 1 个驱动 (top.din)

### 2.7 不带模块名查询未支持
```systemverilog
tracer.trace_signal('dout')  // 应自动查找 dout 信号
```
当前返回 0 驱动，期望 1 个驱动 (top.din)

### 2.8 priority case default 分支未追踪
```systemverilog
always_ff @(posedge clk)
    if (sel)
        case (1'b1)  // priority case
            a: y <= 1;
            default: y <= 0;
        endcase
```
当前返回 1 驱动 (1)，期望 2 个驱动 (1, 0)

注意: case (1'b1) 是 priority case，按顺序评估条件。default 分支可到达。

---

## 三、修复优先级

### P1 - 高优先级（9 个失败测试）
| 测试 | 优先级 |
|------|--------|
| test_ternary (三元 sel) | P1 |
| test_complex_expression | P1 |
| test_floor (函数参数) | P1 |
| test_parameterized_module | P1 |
| test_alias | P2 |
| test_case_sensitive_signal | P2 |
| test_dollar_in_name | P2 |
| test_signal_without_module_prefix | P2 |

---

## 四、修复记录

### 2026-05-23 (12d671c)
- 第一轮测试质量改进
- 修复 P1 测试类弱断言为强断言
- 去掉已知限制标注，按语义编写正确 assertion
- 发现 **8 个失败测试**，需要修复 tracer

### 2026-05-23 (bbbfdfc)
- 修复 P1 测试类弱断言
- 发现 3 个语义失败

### 2026-05-23 (b43f08e)
- 修复 P2/P3 测试类弱断言

### 2026-05-23 (0349b14)
- 修复 test_operators, test_system_tasks, test_directives, test_boundary

---

## 五、相关文档

- `TEST_QUALITY_IMPROVEMENT_PLAN.md` - 测试质量改进计划
- `DEVELOPMENT.md` - 开发规范