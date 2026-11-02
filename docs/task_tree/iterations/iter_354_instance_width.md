# Iteration 354: 取实例 width（PLAN P53）

**Metadata**:
- **Iteration #**: 354
- **Task Tree Level**: L2（PLAN `P53`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "应该取实例的 width"）
- **Outcome**: ✅ 完成（参数化实例 width；2719 passed）

## 🎯 问题

P52 用 **module 定义** 的 width 传播到实例：

```text
axi_vfifo_enc.out_hdr_next = 23
```

同一 module type 的不同 parameter 实例会被错误地赋同一个 width：

```systemverilog
leaf #(.W(8)) u8(...);
leaf #(.W(4)) u4(...);   // u4 也拿到 8 位
```

## 🔧 修复

`_propagate_instance_widths` 改为**实例优先**：

1. `adapter.get_data_declarations(inst._symbol)`：
   - 内部变量/线网，parameter 已解析；
2. `adapter.get_port_declarations(inst._symbol)`：
   - 端口 width，parameter 已解析；
3. `module 定义 map` 只作 fallback（实例 body 没覆盖时）。

实例 body 的宽度为零/未知时不覆盖（避免把 scalar 误降级）。

## 🧪 验证

参数化 fixture：

```systemverilog
leaf #(.W(8)) u8(...);
leaf #(.W(4)) u4(...);
```

结果：

```text
top.u8.i (7,0)
top.u8.o (7,0)
top.u4.i (3,0)
top.u4.o (3,0)
```

bit consistency：

```text
verilog-axi  pass 0 violations
picorv32     pass 0 violations
strict_uart  pass 0 violations
```

## 📉 graph baseline 变化

5 个 baseline 有意重采：

- generate_forms：`u_leaf.a/y` `(0,0)→(1,0)`；
- minimal_3module / minimal_arbiter / scheduler_minimal / wrapper_chain：
  实例端口/内部 scalar `(0,0)→(1,0)`。

原因是实例 body 的端口声明提供了 scalar `(1,0)`，比旧 `(0,0)` 更准确。

## 🧪 测试

- `test_instance_specific_parameter_width`；
- 5 个 graph baseline 有意重采；
- 全量 **2719 passed / 0 failed**。

## ⚠️ 边界

- 实例 body 声明/端口枚举失败时退回 module 定义 map（logger.debug）；
- 未覆盖同一实例内 generate 分支的 parameter 特化（节点路径已有 generate 索引）；
- width 仍是元数据，不是位逻辑证明。

## 🔗 相关

- 计划: [PLAN.md P53](../../../PLAN.md)
