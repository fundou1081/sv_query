# Issue 18 根因分析

**问题**: LOAD 边统计为 0
**状态**: 已分析根因
**日期**: 2026-05-17

---

## 问题描述

```
实际结果:
  边类型统计:
    DRIVER: 3
    LOAD: 0      ← 期望有 LOAD 边

总边数: 3
期望: > 3 (包含实例端口连接)
```

---

## 根因分析

### 直接原因

当只解析 `bs_mult.v` 时：

1. **bs_mult_slice 模块未解析** - 定义在单独的 `bs_mult_slice.v` 文件中
2. **bs_mult_slice 端口方向未知** - 所有端口方向返回 'unknown'
3. **unknown 方向不创建边** - 代码逻辑：只有 'input'/'output' 才创建 CONNECTION 边

### 代码逻辑验证

```python
# graph_builder.py 中的逻辑
for port_name, signal_name in named_conns.items():
    direction = module_ports.get(port_name, 'unknown').strip()
    
    if direction_clean == 'input':
        # 创建 CONNECTION 边 (input 信号 → 实例端口)
    elif direction_clean == 'output':
        # 创建 CONNECTION 边 (实例端口 → output 信号)
    else:
        # unknown: 不创建边!
```

当 `direction = 'unknown'` 时（因为 bs_mult_slice 未解析），不创建任何边。

### 数据验证

```
all_module_ports: {'bs_mult': {...}}
实例 I0 类型: bs_mult_slice
module_ports.get('bs_mult_slice'): NOT FOUND

I0 连接:
  clk -> clk (direction: unknown)   ← 不创建边
  xy -> xy (direction: unknown)     ← 不创建边
  pin -> pout (direction: unknown)   ← 不创建边
  ...
```

所有 31 个实例 (I0-I30) 的所有 10 个端口连接都没有创建边。

---

## 问题本质

**Issue 18 不是 sv_query 的 bug**，而是**解析范围不完整**导致的正常行为：

| 场景 | 边数 | 原因 |
|------|------|------|
| 仅 bs_mult.v | 3 | bs_mult_slice 未解析，无法创建连接边 |
| bs_mult.v + bs_mult_slice.v | 708 | 两个文件都解析，完整连接 |

---

## 解决方案

### 方案 A: 记录为正常行为 (推荐)

Issue 18 记录为**设计约束**：
- sv_query 需要解析所有相关文件才能获取完整连接信息
- 当实例模块未解析时，连接边不会被创建
- 这是语义正确性要求，不是 bug

**理由**: 如果允许"猜测"端口方向，可能导致错误的连接追踪。

### 方案 B: 添加警告

当实例模块未解析时，添加更明确的警告：

```python
if not module_ports and conns:
    # 已有警告，但可以增强
    logger.warning(
        f"实例 {inst_name} ({inst_module_name}) 的模块未解析，"
        f"无法确定端口方向 ({len(conns)} 个连接跳过)"
    )
```

### 方案 C: 保守推断方向

如果确实需要创建边，可以保守推断：
- 大部分端口是 input
- 输出端口通常更少

**⚠️ 风险**: 可能创建错误的连接边。

---

## 推荐方案

**方案 A** - 记录为正常行为

理由:
1. **正确性优先**: 不创建边比创建错误边好
2. **已有警告**: Issue 20 已添加缺少文件的警告
3. **用户责任**: 用户需要确保传入所有相关文件

---

## 验证数据

### 场景1: 仅 bs_mult.v

```
节点数: 379
边数: 3 (只有 DRIVER 边)

实例: bs_mult_slice × 31
警告: Missing module: bs_mult_slice (31 条)
```

### 场景2: 两个文件都解析

```
节点数: 411
边数: 708
  CONNECTION: 587
  DRIVER: 118
  BIT_SELECT: 3

模块: bs_mult, bs_mult_slice
```

---

## 总结

| 项目 | 说明 |
|------|------|
| **根因** | bs_mult_slice 未解析，端口方向未知 |
| **直接原因** | unknown 方向不创建边 |
| **问题类型** | 解析范围不完整，非 bug |
| **解决方案** | 记录为设计约束 (方案 A) |
| **已有改进** | Issue 20 已添加警告提示 |