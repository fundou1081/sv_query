# 第三轮 OpenChip QA 测试 - Issue 和需求记录

## 测试时间
2026-05-16

## 测试对象
sv_query 工具

---

## Issue 13: get_module_instances() 无法获取 bs_mult 实例

### 问题描述
`get_module_instances()` 返回 0 实例，但文件中有 31 个 `bs_mult_slice` 实例

### 根因分析
1. **API 设计问题**：方法需要传入 `parser.trees`，但：
   ```python
   instances = adapter.get_module_instances(parser.trees)  # 需要手动传入
   instances = adapter.get_module_instances()             # 返回空
   ```

2. **节点类型不匹配**：调试输出显示找到了 `SyntaxKind.HierarchicalInstance`，但代码搜索的是 `SyntaxKind.HierarchyInstantiation`

### sv_query 输出 (修复前)
```
实例数量: 0
```

### sv_query 输出 (修复后)
```
实例数量: 62
  I0 -> bs_mult_slice
  I1 -> bs_mult_slice
  ... (31个实例)
```

### 修复方案
1. 添加 `HierarchicalInstance` 节点类型支持
2. 代码变更: `if 'HierarchyInstantiation' in kind_str` → `if 'HierarchyInstantiation' in kind_str or 'HierarchicalInstance' in kind_str`

### 待解决问题
- 存在 `None -> None` 的重复条目 (62 vs 预期 31)
- 可能需要去重或过滤子节点

### 源码中的实例
```verilog
bs_mult_slice I0(.clk(clk), .xy(xy), ...);
bs_mult_slice I1(.clk(clk), .xy(xy), ...);
...
bs_mult_slice I30(.clk(clk), .xy(xy), ...);
```

### 影响
- bs_mult 模块实例数量显示为 0 (现已修复)
- 无法追踪实例连接关系

### 优先级
P1 (高频场景，影响基本使用)

### 状态
✅ 已修复 (添加 HierarchicalInstance 支持)

---

## Issue 14: 调试输出喧哗 (Verbose Log)

### 问题描述
`get_module_instances()` 启用调试模式时输出大量 UnknownNode 信息，淹没正常输出

### 示例输出
```
[UnknownNode] kind=TokenKind.EndModuleKeyword at depth=1
[UnknownNode] kind=TriviaKind.EndOfLine at depth=2
[UnknownNode] kind=TriviaKind.BlockComment at depth=2
... (数百行)
```

### 根因
调试日志直接 print 到 stdout，没有日志级别控制

### 影响
- 正常输出被淹没
- 用户体验差

### 优先级
P3 (低频调试场景)

### 状态
已知限制

---

## Issue 15: 端口位宽提取结果不一致

### 问题描述
`extract_port_width()` 返回的字典字段与文档描述不一致

### sv_query 输出
```python
width={'msb_raw': None, 'msb_eval': None, 'msb_is_param': False, 
       'lsb_raw': None, 'lsb_eval': None, 'lsb_is_param': False}
```

### 预期输出格式
```python
width={'msb': 29, 'lsb': 0}  # 或类似格式
```

### 根因
- 对于没有显式位宽的端口 (如 `input clk`)，返回 None
- 文档与实际返回格式不匹配

### 影响
- 无法区分 1-bit 端口和位宽未指定的端口

### 优先级
P2

### 状态
需确认预期行为

---

## 需求记录

### Req-1: 实例提取 API 简化

**描述**：用户应该能直接调用 `adapter.get_module_instances()` 而无需传入 trees

**当前**：
```python
instances = adapter.get_module_instances(parser.trees)  # 需要传入
```

**期望**：
```python
instances = adapter.get_module_instances()  # 直接调用
```

### Req-2: 支持 HierarchicalInstance 节点类型

**描述**：`get_module_instances()` 应该能识别 `SyntaxKind.HierarchicalInstance`

**当前**：只搜索 `SyntaxKind.HierarchyInstantiation`

**期望**：同时支持两种节点类型

### Req-4: 实例去重

**描述**：修复后出现 `None -> None` 重复条目，需要去重

**当前**：62 个实例 (含 31 个重复的 None)
**期望**：31 个实例

### Req-5: generate 内的实例支持

**描述**：generate 块内的实例也需要能被提取

**描述**：添加日志级别控制，减少调试信息输出

**当前**：所有调试信息直接输出

**期望**：支持 `logging.DEBUG` 等级别控制

---

## 测试进度

| 项目 | 模块 | 问题数 | 状态 |
|------|------|--------|------|
| clacc | bs_mult | 3 | 进行中 |
| clacc | dual_clock_fifo | - | 待测试 |
| clacc | mult_pipe2 | - | 待测试 |
| clacc | pe | - | 待测试 |
| serv | ... | - | 待测试 |
| ... | ... | - | ... |

---

## 后续行动

1. [ ] 修复 Issue 13: 实例提取 API
2. [ ] 确认 Issue 15: 位宽提取预期行为
3. [ ] 继续测试其他项目