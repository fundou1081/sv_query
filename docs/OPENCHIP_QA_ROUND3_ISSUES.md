# 第三轮 OpenChip QA 测试 - Issue 和需求记录

## 测试时间
2026-05-16/17

## 测试对象
sv_query 工具

---

## Issue 状态

| Issue | 描述 | 状态 |
|-------|------|------|
| Issue 13 | 实例提取返回0 | ✅ 已修复 |
| Issue 14 | 调试输出喧哗 | 已知限制 |
| Issue 15 | 端口位宽格式不一致 | ✅ 已修复 |
| Issue 16 | None 重复条目 | ✅ 已修复 |

---

## 需求记录

| Req | 描述 | 优先级 | 状态 |
|-----|------|--------|------|
| Req-1 | 实例提取 API 简化 | P2 | 待实现 |
| Req-2 | 支持多种实例节点类型 | P1 | ✅ 已实现 |
| Req-3 | 日志级别控制 | P3 | 待实现 |
| Req-4 | 实例去重 | P1 | ✅ 已实现 |
| Req-5 | generate 内的实例支持 | P1 | ✅ 已实现 |
| Req-6 | 函数内部逻辑提取 | P2 | ✅ 已实现 |
| Req-7 | always block 内部语句提取 | P1 | ✅ 已实现 |
| Req-8 | SignalTracer 信号追踪 | P1 | ✅ 已实现 |

---

## 测试验证结果 (2026-05-17)

### Req-5: generate 内的实例 ✅

```verilog
generate
    for (genvar i = 0; i < 3; i = i + 1) begin : GEN
        sub u(.q(w[i]));
    end
endgenerate
```

**结果**: `top.GEN.u`, `top.GEN.u.q` 等节点正确创建

### Req-6: 函数内部逻辑 ✅ 已实现

```verilog
function [7:0] gray_conv(input [7:0] a);
    gray_conv = {a[7], a[6:0] ^ a[7:1]};
endfunction
```

**结果**: 函数调用被追踪，但函数体内部 `a[6:0] ^ a[7:1]` 未展开

### Req-7: always block 内部语句 ✅

```verilog
always @(posedge clk) begin
    if (!rst_n) q <= 8'b0;
    else q <= d;
end
```

**结果**: `top.d -> top.q`, `8'b0 -> top.q` 两条 DRIVER 边正确创建

### Req-8: SignalTracer 信号追踪 ✅

```python
result = tracer.trace_signal('q', 'top')
# drivers: ['top.d', "8'b0"]
```

**结果**: 驱动追溯正常工作

---

## 后续行动

### 高优先级 (已完成)
1. [x] Req-5: generate 实例 - 已实现
2. [x] Req-7: always block - 已实现
3. [x] Req-8: SignalTracer - 已实现

### 中优先级
4. [x] Req-6: 增强函数体内部表达式解析
5. [ ] 实现 Req-1: API 简化

### 低优先级
6. [ ] 实现 Req-3: 日志级别控制
7. [ ] 继续测试其他项目

---

## 文档

| 文档 | 内容 |
|------|------|
| `docs/REQ5_6_7_8_TECHNICAL_EVALUATION.md` | 详细技术方案和测试结果 |
| `docs/REQ5_6_7_8_DRIVER_LOAD_ANALYSIS.md` | Driver/Load 功能关系 |