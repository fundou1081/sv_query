# sv_query 项目架构对比分析

**日期**: 2026-05-24
**分析范围**: 已有过渡架构、新架构提案 vs pyslang 原生结构

---

## 一、项目现状

### 1.1 项目定位

**sv_query** 是一个 SystemVerilog 代码分析工具，核心功能：
- 解析 SV 源码（基于 pyslang）
- 提取信号（wire, reg, logic 等）
- 构建信号依赖图
- 支持仿真波形分析

### 1.2 核心文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `signal_expression_visitor.py` | 7030 | 核心：信号提取 visitor |
| `graph_builder.py` | 123888 | 图构建 |
| `semantic_adapter.py` | 63155 | 语义分析 |
| `base.py` | 94616 | 基础功能 |

### 1.3 pyslang 依赖

- **版本**: 10.0.0
- **SyntaxKind**: 536 个语法类型
- **架构**: 原生 C++ 绑定，Python 封装

---

## 二、架构方案对比

### 方案 A：已有架构（visitor 模式）

**结构**：
```
signal_expression_visitor.py
├── visit_identifier_name()      # 45 个 visit_ 方法
├── visit_scoped_name()
├── visit_binary_expression()
├── ...
└── extract()                    # 主入口
```

**特点**：
- 45 个 `visit_` 方法
- 手动 dispatch：`visit()` 根据方法名查找
- 返回 `Optional[str]`（信号名）
- 手动处理子节点递归

**优点**：
- 实现简单直观
- 易于理解（每个类型一个方法）
- 适合快速开发

**缺点**：
- visit_ 命名与 pyslang 不一致
- 逻辑和遍历混在一起
- 45 个方法覆盖不了 536 种语法类型
- 子节点处理需要手动递归

---

### 方案 B：过渡架构（@on handler）

**结构**：
```
signal_expression_visitor.py
├── @on('IdentifierName')        # 536 个 @on handlers
├── @on('AssignmentExpression')
├── @on('BinaryExpression')
├── ...
├── _dispatch_enabled = True/False
└── extract()                    # 主入口
```

**特点**：
- 536 个 `@on` handler（与 pyslang 1:1 对齐）
- 单 dispatch：`extract()` 根据 `node.kind` 分派
- 返回 `SignalResult`（富信息对象）
- Handler 手动处理子节点

**优点**：
- 与 pyslang 类型完全对齐
- 536 种语法类型全覆盖
- 返回富信息（SignalResult）
- 新增类型只需要添加 handler

**缺点**：
- 536 个 handler 大部分是空 stub
- Handler 需要手动处理子节点
- 两套系统并存（visit_ + @on）
- Handler 逻辑和遍历未分离

---

### 方案 C：新架构提案（反射 @on handler）

**结构**：
```
signal_expression_visitor.py
├── @on('IdentifierName')         # 536 个简化 @on handlers
├── @on('AssignmentExpression')   # 只处理当前节点
├── @on('BinaryExpression')
├── ...
├── _extract_children(node)      # 框架自动反射遍历
├── extract()                    # 主入口
└── _get_signal_name(node)       # 辅助方法
```

**特点**：
- Handler 只处理当前节点逻辑
- 框架自动反射发现并递归子节点
- 返回 `SignalResult`

**优点**：
- Handler 职责单一
- 代码量减少
- 一致性更好
- 符合 visitor 模式原意

**缺点**：
- 反射开销
- 需要正确过滤 AST 属性
- 循环引用处理复杂
- 实现复杂度高

---

## 三、pyslang 原生架构参考

### 3.1 pyslang 的设计

pyslang 是 SystemVerilog 解析器，核心概念：

```python
# pyslang 节点结构
node.kind        # SyntaxKind 枚举
node.left       # 子节点（AST 节点）
node.right      # 子节点（AST 节点）
node.value      # 值（Token 或标量）
```

**设计原则**：
1. **1:1 对齐语法** - 每个 SyntaxKind 对应一个节点类
2. **树形结构** - 父节点包含子节点引用
3. **反射友好** - 子节点通过属性名访问

### 3.2 pyslang 的 visitor 模式

pyslang 本身支持 visitor 模式：
```python
# pyslang 内置 visitor
class SyntaxVisitor:
    def visit(self, node):
        kind = node.kind
        method = f'visit_{kind.name}'  # 动态查找
        if hasattr(self, method):
            return getattr(self, method)(node)
```

---

## 四、评价指标分析

### 4.1 简洁性

| 指标 | 方案 A (visitor) | 方案 B (@on) | 方案 C (反射 @on) |
|------|------------------|--------------|-------------------|
| 代码行数 | ~7000 | ~7000 | ~6000 (预估) |
| 概念数 | 1 (visit_) | 2 (visit_ + @on) | 1 (@on) |
| 配置项 | 0 | 1 (_dispatch) | 0 |
| **评分** | ★★★☆ | ★★☆☆ | ★★★★ |

### 4.2 合适的抽象

| 指标 | 方案 A | 方案 B | 方案 C |
|------|--------|--------|--------|
| 与 pyslang 对齐 | 低 | 高 | 高 |
| 抽象一致性 | 中 | 高 | 高 |
| 扩展性 | 差 | 好 | 最好 |
| **评分** | ★★☆☆ | ★★★★ | ★★★★★ |

### 4.3 下游任务适配性

**下游任务**：
1. **信号提取** - 提取 wire/reg/信号名
2. **依赖图构建** - 构建信号依赖关系
3. **波形分析** - 关联信号和仿真结果
4. **代码生成** - 生成测试用例

| 指标 | 方案 A | 方案 B | 方案 C |
|------|--------|--------|--------|
| 信号提取 | ✓ | ✓ | ✓ |
| 依赖图构建 | 中 | 好 | 好 |
| 波形分析 | 需要适配 | 好 | 好 |
| **评分** | ★★★☆ | ★★★★ | ★★★★ |

### 4.4 开发体验

| 指标 | 方案 A | 方案 B | 方案 C |
|------|--------|--------|--------|
| 新增类型 | 需要添加 visit_ | 添加 @on handler | 添加简单 @on |
| 调试难度 | 低 | 中 | 高 |
| 学习曲线 | 陡 | 中 | 陡 |
| **评分** | ★★★☆ | ★★★☆☆ | ★★★☆☆ |

### 4.5 维护性

| 指标 | 方案 A | 方案 B | 方案 C |
|------|--------|--------|--------|
| 代码重复 | 高 | 中 | 低 |
| 一致性 | 差 | 好 | 最好 |
| 测试难度 | 低 | 中 | 高 |
| **评分** | ★★☆☆ | ★★★☆☆ | ★★★★ |

---

## 五、综合对比

| 指标 | 权重 | 方案 A | 方案 B | 方案 C |
|------|------|--------|--------|--------|
| 简洁性 | 20% | 3 | 2 | 4 |
| 合适的抽象 | 25% | 2 | 4 | 5 |
| 下游适配 | 20% | 3 | 4 | 4 |
| 开发体验 | 15% | 3 | 3 | 3 |
| 维护性 | 20% | 2 | 3 | 4 |
| **加权总分** | | **2.45** | **3.20** | **4.20** |

---

## 六、结论

### 6.1 推荐：方案 C（新架构）

**理由**：
1. 与 pyslang 设计理念一致（1:1 对齐 + 反射）
2. Handler 职责单一，易于维护
3. 框架自动处理遍历，代码量减少
4. 长期可维护性最好

### 6.2 实施建议

**阶段 1：清理**
- 删除已标记为 DEAD CODE 的 visit_ 方法
- 禁用 `_dispatch_enabled = False` 临时

**阶段 2：实现框架**
- 实现 `_extract_children()` 反射方法
- 实现 `_get_signal_name()` 辅助方法
- 修改 `extract()` 集成自动遍历

**阶段 3：简化 handlers**
- 选择几个 handler 试点
- 验证功能正确性
- 批量简化其他 handlers

**阶段 4：生产验证**
- 完整测试
- 性能测试
- 删除旧代码

### 6.3 风险

1. **反射开销** - 需要实测验证性能
2. **pyslang 版本兼容** - 反射依赖节点结构
3. **调试困难** - 递归隐藏在不显眼处

---

## 七、附录：参考实现

### pyslang 节点属性过滤示例

```python
def _is_ast_node(attr, value):
    """判断属性是否是 AST 子节点"""
    # 跳过私有属性
    if attr.startswith('_'):
        return False
    
    # 跳过非节点值
    if value is None:
        return False
    if isinstance(value, (str, int, float, bool)):
        return False
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return False
    
    # 检查是否有 kind 属性（AST 节点特征）
    return hasattr(value, 'kind')
```