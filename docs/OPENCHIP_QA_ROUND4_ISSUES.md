# OpenChip QA Round 4 - 问题汇总

**测试时间**: 2026-05-17
**测试项目**: clacc/bs_mult

---

## 问题状态总结

| Issue | 问题 | 状态 | 说明 |
|-------|------|------|------|
| Issue 17 | 非ANSI端口位宽丢失 | ✅ 已记录 | 源代码问题，非 sv_query bug |
| Issue 18 | LOAD 边统计为 0 | ✅ 已确认 | 设计约束，保持现状 |
| Issue 19 | 实例节点前缀 "top" | ✅ 已修复 | 动态获取根模块名 |
| Issue 20 | 边数只有 3 | ✅ 已修复 | 添加缺少文件警告 |

---

## Issue 17: 非ANSI端口位宽丢失

### 案例: bs_mult.v 的 output p

**问题**: `p: output` 位宽丢失，应为 `output [29:0]`

**根因**: bs_mult.v 源代码不符合 SV 标准

```verilog
// 实际代码 (有问题)
output p;         // ❌ 缺少位宽声明

// 标准写法
output [29:0] p;   // ✅ 有位宽声明
```

**结论**: 这是源代码问题，非 sv_query bug。sv_query 正确识别了 `p` 是 output 端口，但无法提取位宽因为源代码没有声明。

**文档**: `docs/ISSUE_17_CASE_BS_MULT.md`

---

## Issue 18: LOAD 边统计为 0

### 问题

```
实际: DRIVER: 3, LOAD: 0, 总边数: 3
期望: 应该有实例端口连接边
```

### 根因

| 项目 | 说明 |
|------|------|
| **为什么 unknown** | bs_mult_slice.v 未解析，端口方向无从得知 |
| **为什么不创建边** | 代码逻辑：unknown 方向跳过边创建 |
| **影响** | 31 个实例 × 10 个端口 = 310 个连接跳过 |

### 解决方案

**保持现状** - 设计约束，正确性优先。

当模块未解析时：
- 端口方向 → 'unknown'
- 跳过边创建
- 输出警告 (Issue 20)

**文档**: `docs/ISSUE_18_CONCLUSION.md`

---

## Issue 19: 实例节点前缀错误 "top" ✅

### 问题

```
实际: top.I0.clk, top.I0.pout, ...
期望: bs_mult.I0.clk, bs_mult.I0.pout, ...
```

### 修复内容

1. 在 `ConnectionExtractor.__init__` 添加 `self.root_module_name = None`
2. 在 `extract()` 开始时动态获取第一个模块名
3. 将所有硬编码的 `"top."` 替换为 `f"{self.root_module_name}."`

### 验证结果

```
修复前: top.I0.clk (371 个), bs_mult.* (8 个)
修复后: bs_mult.I0.clk (379 个), top.* (0 个)
```

### Commit

`94ad7fa fix: Issue 19 - 动态获取根模块名而非硬编码 top`

---

## Issue 20: 边数只有 3

### 问题

当只解析 bs_mult.v 时：
- 总边数: 3 (只有 assign 语句的 DRIVER 边)
- 缺少实例端口连接边

### 修复内容

添加 `_missing_module_warning` 方法，当检测到实例但无端口定义时输出警告：

```
[sv_query] 可能缺少文件: 实例 'I0' 的模块 'bs_mult_slice' 没有找到端口定义。
  → 可能原因: 解析的文件范围不完整，缺少 'bs_mult_slice' 的定义文件
  → 建议: 确保传入所有相关的 Verilog 文件
```

### Commit

`f2b1647 fix: Issue 20 - 添加可能缺少文件的警告提示`

---

## Round 4 最终结论

### 问题分类

| 类型 | 数量 | 说明 |
|------|------|------|
| ✅ 已修复 | 2 | Issue 19, Issue 20 |
| ✅ 已记录为非bug | 2 | Issue 17 (源代码问题), Issue 18 (设计约束) |

### 学到的东西

1. **解析范围很重要**: sv_query 需要解析所有相关文件才能获取完整信息
2. **正确性优先**: 不创建错误边比创建边更重要
3. **警告友好**: 明确提示可能的问题比静默失败更好
4. **源代码质量**: 不符合标准的代码会导致工具无法正确解析

---

## Commits

| Commit | 说明 |
|--------|------|
| `94ad7fa` | fix: Issue 19 - 动态获取根模块名 |
| `f2b1647` | fix: Issue 20 - 添加缺少文件警告 |
| `858d9cb` | docs: Issue 17 - 记录源代码问题 |
| `dd8cc0f` | docs: Issue 18 - 根因分析 |
| `502ed76` | docs: Issue 18 - 结论: 保持现状 |