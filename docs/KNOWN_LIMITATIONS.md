# 已知限制汇总

> 本文档记录 sv_query 项目中发现的所有已知限制，用于追踪和计划修复。

最后更新: 2026-05-23

---

## 一、失败测试（9 个 - 需要修复 tracer）

| # | 测试文件 | 测试方法 | 限制描述 | 根本原因 |
|---|----------|----------|----------|----------|
| 1 | test_operators.py | test_ternary | 三元运算符 `sel ? a : b`，sel 应为驱动源 | 条件选择信号未被识别为驱动源 |
| 2 | test_operators.py | test_complex_expression | 复杂表达式中 sel 应为驱动源 | 同上 |
| 3 | test_system_tasks.py | test_floor | `$floor(r)` 函数参数 r 应为驱动源 | 函数调用的输入参数未被识别为驱动源 |
| 4 | test_aliases.py | test_alias | `alias b = a` 应追踪到 a | alias 语句处理缺失 |
| 5 | test_boundary.py | test_parameterized_module | 参数化模块 `dout = din` 应追踪到 din | 参数化模块解析缺失 |
| 6 | test_complex_conditions.py | test_case_inside_if | `case (1'b1) default: y<=0` 应返回 2 驱动 | priority case default 分支未追踪 |
| 7 | test_boundary.py | test_case_sensitive_signal | `Din` 和 `din` 应区分 | 信号名大小写区分缺失 |
| 8 | test_boundary.py | test_dollar_in_name | `$data` 美元符信号应支持 | 美元符信号名解析缺失 |
| 9 | test_boundary.py | test_signal_without_module_prefix | 不带模块名查询 `dout` 应找到 | 模块名查询参数缺失 |

---

## 二、修复优先级

### P1 - 已完成（3 个）✅ 2026-05-23
**核心功能，修复简单，影响大**

| # | 测试 | RTL | 状态 | 修复内容 |
|---|------|-----|------|----------|
| 1 | test_ternary | `sel ? a : b` | ✅ 通过 | ConditionalOp 添加 conditions[0].expr 处理 |
| 2 | test_complex_expression | `((a+b)&c)\|(sel?a:b)` | ✅ 通过 | 同上 |
| 3 | test_floor | `$floor(r)` | ✅ 通过 | Call 表达式添加 arguments 参数提取 |

### P2 - 中优先级（2 个完成，2 个待修复）
**中等复杂度，需要一定的 AST 修改**

| # | 测试 | RTL | 状态 | 修复内容 |
|---|------|-----|------|----------|
| 4 | test_alias | `alias b = a` | ✅ 通过 | 添加 get_net_aliases() + graph_builder alias 处理 |
| 6 | test_case_inside_if | `case(1'b1) default: y<=0` | ✅ 通过 | CaseStatement items 从 semantic.items 改为 syntax.items |
| 5 | test_parameterized_module | `parameter WIDTH = 8` | ❌ 待修 | 参数化模块 get_modules() 返回空，需要调试 |
| 7 | test_ternary_in_if | `if(sel) y<=sel?a:b` | ✅ 通过 | 已由 P1 三元修复覆盖 |

### P3 - 低优先级（3 个）
**复杂或边缘用例**

| # | 测试 | RTL | 状态 | 原因 |
|---|------|-----|------|------|
| 8 | test_case_sensitive_signal | `Din` vs `din` | ❌ 待修 | 需要信号名查表 |
| 9 | test_dollar_in_name | `$data` | ❌ 待修 | 需要修改词法分析 |
| 10 | test_signal_without_module_prefix | `trace_signal('dout')` | ❌ 待修 | 修改 API 或实现自动查找 |

---

## 三、失败测试详细说明

### 3.1 test_ternary - 三元运算符 sel 未追踪
```systemverilog
assign y = sel ? a : b;  // sel 是控制信号，应参与驱动追踪
```
当前返回 2 驱动 (a,b)，期望 3 个驱动 (sel,a,b)

### 3.2 test_complex_expression - 复杂表达式中 sel 未追踪
```systemverilog
assign y = ((a + b) & c) | (sel ? a : b);  // sel 是控制信号
```
当前返回 3 驱动 (a,b,c)，期望 4 个驱动 (sel,a,b,c)

### 3.3 test_floor - $floor() 函数参数未追踪
```systemverilog
assign f = $floor(r);  // r 是输入参数，应参与驱动追踪
```
当前返回 0 驱动，期望 1 个驱动 (top.r)

### 3.4 test_alias - alias 语句不支持
```systemverilog
module top(input a, output b);
    alias b = a;  // 应追踪 b <- a
endmodule
```
当前返回 0 驱动，期望 1 个驱动 (top.a)

### 3.5 test_parameterized_module - 参数化模块未支持
```systemverilog
module #(parameter WIDTH = 8) top(...);
    assign dout = din;  // din 宽度使用 WIDTH 参数
endmodule
```
当前返回 0 驱动，期望 1 个驱动 (top.din)

### 3.6 test_case_inside_if - priority case default 分支未追踪
```systemverilog
always_ff @(posedge clk)
    if (sel)
        case (1'b1)  // priority case
            a: y <= 1;
            default: y <= 0;  // default 分支可到达
        endcase
```
当前返回 1 驱动 (1)，期望 2 个驱动 (1, 0)

### 3.7 test_case_sensitive_signal - 大小写敏感未支持
```systemverilog
module top(input Din, input din, ...);  // Din 和 din 是不同信号
```
当前返回 0 驱动，期望 1 个驱动 (top.Din)

### 3.8 test_dollar_in_name - 美元符信号名未支持
```systemverilog
module top(input $data, output dout);
    assign dout = $data;
endmodule
```
当前返回 0 驱动，期望 1 个驱动 (top.$data)

### 3.9 test_signal_without_module_prefix - 不带模块名查询未支持
```systemverilog
tracer.trace_signal('dout')  // 应自动查找 dout 信号
```
当前返回 0 驱动，期望 1 个驱动 (top.din)

---

## 四、修复记录

### 2026-05-23 (f227660)
- 修正 test_case_inside_if - priority case 语义正确，测试应失败
- **9 个失败测试**，需要修复 tracer

### 2026-05-23 (2a43df7)
- 修复 test_case_stmt.py 和 test_complex_conditions.py 弱断言

### 2026-05-23 (12d671c)
- 第一轮测试质量改进
- 8 个失败测试需要修复 tracer

---

## 五、相关文档

- `TEST_QUALITY_IMPROVEMENT_PLAN.md` - 测试质量改进计划
- `DEVELOPMENT.md` - 开发规范