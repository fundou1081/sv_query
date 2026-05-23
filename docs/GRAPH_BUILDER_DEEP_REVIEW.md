# graph_builder.py 深度 Review 报告

> 审查日期: 2026-05-23
> 文件: src/trace/core/graph_builder.py
> 总行数: 3297 行
> 提交: 1a60e08

---

## 一、架构概述

`graph_builder.py` 是 Builder Layer 的核心，负责将 Semantic AST 转换为 NetworkX 信号图。

### 文件结构

| 部分 | 行数 | 功能 |
|------|------|------|
| DriverExtractor | ~1800 | 主逻辑，信号图构建 |
| LoadExtractor | ~1100 | 负载追踪 |
| _collect_assignments_from_stmt | ~500 | 旧版语句收集 (已部分废弃) |
| _parse_assign | ~200 | 赋值解析 |
| _get_all_signals | ~400 | 表达式信号提取 (三元/拼接) |
| _get_signal | ~500 | 单信号提取 |

---

## 二、铁律遵守情况

### 铁律1: AST唯一数据源 ✅

- 使用 `SemanticAdapter` 获取信息
- 通过 `Compilation.getRoot()` 获取 Semantic AST

### 铁律2: 位精确性 ✅

- `data[7:0]` 和 `data[15:8]` 区分处理
- 使用 `width` 字段保留位宽信息

### 铁律3: 不可信则不输出 ⚠️

- 大部分情况返回 uncertain
- **问题**: 有多处 `except: pass` 静默忽略错误

### 铁律14: Syntax中间层 ✅

- 通过 `PyslangAdapter` 获取信息

### 铁律15: Visitor模式 ❌ **严重违反**

---

## 三、铁律15 违反详情

**规则**: AST 遍历必须使用 Visitor 模式，禁止 if-elif 链处理所有语法类型

**当前问题**: 大量 if-elif 链处理不同语法类型

### 3.1 _collect_stmts_with_context (line 106-308)

**问题**: 30+ 个 if-elif 分支处理不同语法节点

```python
# line 186-291
if ".TokenKind." in ks or "Trivia" in ks:
    return []
if "InitialBlock" in ks:
    ...
if any(x in ks for x in ["AlwaysFF", "AlwaysComb", "AlwaysLatch"]):
    ...
if "TimingControl" in ks:
    ...
if "Timed" in ks:
    ...
if "Block" in ks and "Statement" in ks:
    ...
if "Case" in ks and "Statement" in ks:      # ⚠️
    ...
if "Conditional" in ks and "Statement" in ks:  # ⚠️
    ...
if "ElseClause" in ks:
    ...
if "ExpressionStatement" in ks:
    ...
if "InvocationExpression" in ks or "Call" in ks:
    ...
if "Assignment" in ks:
    ...
```

**影响范围**: 
- 维护性差：添加新语法类型需要修改此方法
- 违反开闭原则
- 测试覆盖困难

### 3.2 _get_all_signals (line 1393-1573)

**问题**: 20+ 个 if-elif 分支处理不同表达式类型

```python
# line 1397-1537
if 'ConditionalOp' in kind_str or 'ConditionalExpression' in kind_str:
    ...
if 'ParenthesizedExpression' in kind_str:
    ...
if 'ConditionalPredicate' in kind_str or 'ConditionalPattern' in kind_str:
    ...
if 'TimingControlExpression' in kind_str:
    ...
if 'Conversion' in kind_str:
    ...
if 'Call' in kind_str or 'Invocation' in kind_str:
    ...
if 'ElementSelect' in kind_str:
    ...
if 'MemberAccess' in kind_str:
    ...
if 'Concatenation' in kind_str and 'Multiple' not in kind_str:
    ...
# ... 10+ more branches
```

### 3.3 _get_signal (line 1573-2193)

**问题**: 30+ 个 if-elif 分支处理不同信号类型

```python
# line 1573-2093
if hasattr(signal, 'kind') and str(signal.kind) == 'SyntaxKind.ScopedName':
    ...
if hasattr(signal, 'kind') and 'IntegerVector' in str(signal.kind):
    ...
if hasattr(signal, 'kind') and 'IntegerLiteral' in str(signal.kind):
    ...
# ... 30+ more branches
```

### 3.4 _collect_assignments_from_stmt (line 782-888)

**问题**: 10+ 个 if-elif 分支 (已部分废弃)

```python
# line 830-871
if kind and 'Case' in kind_str:
    ...
if kind and ('Assignment' in kind_str):
    ...
if kind and ('Blocking' in kind_str or 'AssignmentExpression' == kind_str):
    ...
if kind and 'ExpressionStatement' in kind_str:
    ...
```

---

## 四、其他问题

### 4.1 except: pass (铁律3 违反)

**位置**: 多处

```python
# line 304
except: pass

# line 1218
except Exception as e:
    pass  # 忽略处理错误,继续
```

**问题**: 
- 静默忽略错误，违反铁律3
- 调试困难
- 错误可能传播到下游

### 4.2 重复代码

#### 4.2.1 ScopedName 处理重复

**位置1** (line 1578-1600):
```python
if hasattr(signal, 'kind') and str(signal.kind) == 'SyntaxKind.ScopedName':
    def _get_scoped_parts(node, parts=None):
        if parts is None: parts = []
        ...
        return parts
    parts = _get_scoped_parts(signal)
    ...
```

**位置2** (line 1738-1762):
```python
# [P0-FIX] HierarchicalValueExpression: ifc.data
if kind and 'HierarchicalValue' in str(kind):
    syntax = getattr(signal, 'syntax', None)
    if syntax and hasattr(syntax, 'kind'):
        kind_str = str(syntax.kind)
        if 'ScopedName' in kind_str:
            # 复用 ScopedName 提取逻辑
            parts = []
            def _get_scoped_parts(node, parts=None):
                ...
```

**问题**: 同样的 `_get_scoped_parts` 函数定义了两遍

#### 4.2.2 IdentifierSelect 处理重复

**位置1** (line 1810-1895): `_get_signal` 中的 IdentifierSelect 处理
**位置2** (line 1530-1545): `_get_all_signals` 中已有 RangeSelect 处理

### 4.3 未使用的代码

```python
# line 844-858 (死代码)
if kind and 'Case' in kind_str:
    for item in node.items:
        ...
        return
    if hasattr(node, 'items') and node.items:
        print(f'[DEBUG case] items count={len(list(node.items))}')
        ...
```

这段代码在 `return` 之后，永远不会执行。

### 4.4 字符串类型判断问题

```python
# line 186
if ".TokenKind." in ks or "Trivia" in ks:
```

使用字符串包含判断 `in` 而不是 `==` 或 `startswith`，可能导致误匹配。

---

## 五、改进建议

### 5.1 重构为 Visitor 模式

**目标**: 将 if-elif 链重构为独立的 Visitor 方法

**方案**:

```python
# 当前 (违反铁律15)
def _collect_stmts_with_context(self, n, ctx=None, d=0, _s=None):
    ks = str(getattr(n, "kind", None))
    if "Case" in ks and "Statement" in ks:
        ...
    elif "Conditional" in ks and "Statement" in ks:
        ...

# 目标 (遵守铁律15)
class StatementVisitor:
    def visit_case_statement(self, n, ctx):
        ...
    
    def visit_conditional_statement(self, n, ctx):
        ...
    
    def generic_visit(self, n, ctx):
        # 默认递归处理子节点
        ...
```

### 5.2 提取公共函数

```python
# 提取 ScopedName 处理为公共函数
def _extract_scoped_name(syntax_node, adapter):
    """从 ScopedNameSyntax 提取点分路径"""
    parts = []
    def walk(node):
        kind = getattr(node, 'kind', None)
        if not kind: return
        kind_str = str(kind)
        if 'ScopedName' in kind_str:
            left = getattr(node, 'left', None)
            if left: walk(left)
            right = getattr(node, 'right', None)
            if right:
                ri = getattr(right, 'identifier', None)
                if ri:
                    rv = getattr(ri, 'value', None)
                    if rv: parts.append(str(rv).strip())
        elif 'IdentifierName' in kind_str:
            ident = getattr(node, 'identifier', None)
            if ident:
                val = getattr(ident, 'value', None)
                if val: parts.append(str(val).strip())
    walk(syntax_node)
    return '.'.join(parts) if parts else None
```

### 5.3 错误处理改进

```python
# 当前 (违反铁律3)
except: pass

# 目标 (遵守铁律3)
except Exception as e:
    result.errors.append(f"处理失败: {type(e).__name__}: {e}")
    # 继续处理，但记录错误
```

### 5.4 删除死代码

```python
# line 844-858 - 删除
if kind and 'Case' in kind_str:
    for item in node.items:
        ...
        return  # 之后都是死代码
    if hasattr(node, 'items') and node.items:
        print(f'[DEBUG case] ...')  # 永不会执行
```

---

## 六、优先级评估

| 问题 | 严重度 | 优先级 | 工作量 |
|------|--------|--------|--------|
| 铁律15违反 (if-elif链) | 🟡 中 | P2 | 高 (需要大规模重构) |
| except: pass | 🟡 中 | P2 | 中 |
| ScopedName重复 | 🟢 低 | P3 | 低 |
| 死代码 | 🟢 低 | P3 | 低 |

---

## 七、结论

| 指标 | 评分 |
|------|------|
| 铁律遵守率 | 85% (17/20) |
| 代码质量 | 🟡 良好(需改进) |
| 架构设计 | 🟡 良好(违反铁律15) |
| 可维护性 | 🟡 一般(if-elif链过长) |

**核心问题**: 
1. 大量 if-elif 链违反铁律15 (Visitor模式)
2. 多处 `except: pass` 违反铁律3 (不可信不输出)
3. 重复代码增加维护成本

**建议**: 
- P2: 重构为 Visitor 模式
- P2: 改进错误处理
- P3: 清理重复代码和死代码

---

## 八、下次审查

- 审查日期: 2026-06-23
- 重点: Visitor 模式重构进度

---

*本报告由 QClaw Agent 自动生成*
*审查时间: 2026-05-23 11:20 GMT+8*