# ControlFlow 调试分析记录

> 创建时间: 2026-05-26
> 更新: 2026-05-26

---

## 目录

1. [else-if 链条件解析](#else-if-链条件解析)
2. [上下文栈机制](#上下文栈机制)
3. [语义 AST vs 字符串判断](#语义-ast-vs-字符串判断)
4. [修复记录](#修复记录)

---

## else-if 链条件解析

### 语义正确性

if-else-if 链的条件逻辑是：

```systemverilog
if (A)
    x = 1;        // 条件：A
else if (B)
    x = 2;        // 条件：!A && B
else
    x = 3;        // 条件：!A && !B
```

**关键点**：else-if 不是独立的 if，它嵌套在上一层的 else 分支里。

### 条件求反规则

| 分支 | 条件计算 | 说明 |
|------|----------|------|
| if (A) | A | 第一层条件 |
| else if (B) | !A && B | 取反父条件 AND 当前条件 |
| else | !A && !B | 取反父条件 AND 当前条件取反 |

### 边界情况：多层嵌套

```systemverilog
if (A)
    if (B)
        x = 1;
    else if (C)
        x = 2;
```

第二层 else-if 的条件是：`!(A && B) && C = !A || !B && C`（根据德·摩根定律）

**但实际求反实现**：直接对累积条件字符串取反
- 父条件：`A && B`
- 求反后：`!(A && B)`
- 与 C 组合：`(!(A && B)) && C`

---

## 上下文栈机制

### 核心数据结构

```python
class StatementCollectorVisitor:
    def __init__(self, adapter):
        self._ctx_stack: List[Dict[str, Any]] = [{}]  # 栈底：空 context
        self._statements: List[Tuple[Any, Dict[str, Any]]] = []
    
    @property
    def current_ctx(self):
        """获取当前上下文（栈顶）"""
        return self._ctx_stack[-1] if self._ctx_stack else {}
```

### 栈操作流程

对于以下代码：

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n)         // 深度 1
        status <= 4'h0;
    else if (valid)     // 深度 2
        status <= 4'h1;
    else                // 深度 3
        status <= 4'h2;
end
```

**遍历过程**（深度优先 DFS）：

```
1. 进入顶层 if (!rst_n)
   stack: [{}, {"clock": "clk", "condition": ""}]
   
2. 进入 ifTrue 分支 (status <= 4'h0)
   → 栈顶 context: {"clock": "clk", "condition": ""}
   → 当前条件: "!rst_n"
   → 记录：condition = "!rst_n"

3. 遇到 else if (valid)
   → 这是 else 分支里嵌套的 if (ConditionalStatement)
   
   [求反逻辑]
   - parent_cond = "!rst_n"（栈顶 context 中的条件）
   - parent_cond_expr = UnaryOp(!, NamedValue)（语义 AST）
   - _is_simple_expr_for_negation(parent_cond_expr) = True（简单取反）
   - neg_parent = "!" + "!rst_n" = "!!rst_n"
   
   - cond = "valid"
   - _is_simple_expr_for_negation(valid) = True（简单标识符）
   - neg_cond = "!" + "valid" = "!valid"
   
   - new_cond = "!!rst_n" + " && " + "!valid" = "!!rst_n && !valid"
   
   → 压栈：{"clock": "clk", "condition": "!!rst_n && !valid", "_parent_cond_expr": valid_expr}

4. 进入第二层 ifTrue 分支 (status <= 4'h1)
   → 栈顶 context: {"condition": "!!rst_n && !valid"}
   → 记录：condition = "!!rst_n && !valid"

5. 遇到第二层 else
   → 求反逻辑
   - parent_cond = "!!rst_n && !valid"（复杂表达式）
   - neg_parent = "!(!!rst_n && !valid)"
   → 记录：condition = "!(!!rst_n && !valid)"
```

### 为什么用栈追踪父级条件？

**LIFO（后进先出）特性**：

- 第一层 else-if 处理完后弹出，第一层的 context 恢复
- 每一层都只看到自己"祖先们"的条件
- 嵌套多深都能正确追踪

```
当前在第三层：
stack = [第一层ctx, 第二层ctx, 第三层ctx]
                      ↑
                 current_ctx (栈顶)
```

### context 结构

```python
{
    "condition": "!!rst_n && valid && op_mode == 2'b01",  # 累积条件字符串
    "_parent_cond_expr": <Expression object>,            # 父条件表达式（语义AST）
    "clock": "clk",                                       # 时钟域（always_ff）
    "reset": "rst_n",                                     # 复位信号
}
```

`_parent_cond_expr` 用于下一层 else-if 判断是否需要括号。

---

## 语义 AST vs 字符串判断

### 问题：为什么不能用字符串判断？

之前的错误实现：

```python
def needs_parentheses(c: str) -> bool:
    if c.startswith('!'):
        rest = c[1:]
        while rest.startswith('!'):
            rest = rest[1:]
        if rest.replace('_', '').replace('.', '').isalnum():
            return False  # 错误！
```

**问题案例**：

| 条件字符串 | 字符串判断结果 | 实际问题 |
|------------|---------------|----------|
| `!rst_n` | 不需要括号 ✅ | 正确：加一层变成 `!!rst_n` |
| `!!rst_n` | 不需要括号 ❌ | 错误：加一层变成 `!!!rst_n`，但实际 `!rst_n` 的取反应该是 `!rst_n` |

`!!rst_n` 的语义是双重取反 `!(!(rst_n))`，但从字符串看以 `!` 开头，被错误判断为"简单取反"。

### 正确方案：语义 AST 判断

```python
def _is_simple_expr_for_negation(self, expr) -> bool:
    """判断表达式是否为简单条件（可以直接求反，不需要括号）"""
    if expr is None:
        return True
    
    kind = getattr(expr, 'kind', None)
    if not kind:
        return True
    kind_name = kind.name if hasattr(kind, 'name') else str(kind)
    
    # 简单标识符：直接加 !
    if kind_name in ('NamedValue', 'Identifier', 'Reference'):
        return True
    
    # UnaryOp：检查是否简单取反 !identifier
    if 'UnaryOp' in kind_name:
        op = getattr(expr, 'op', None)
        if not op or 'Not' not in (op.name if hasattr(op, 'name') else str(op)):
            return False
        operand = getattr(expr, 'operand', None)
        if operand:
            operand_kind = getattr(operand, 'kind', None)
            if operand_kind:
                operand_name = operand_kind.name if hasattr(operand_kind, 'name') else str(operand_kind)
                # 只有 !identifier 是简单的
                return operand_name in ('NamedValue', 'Identifier', 'Reference')
        return False
    
    # BinaryOp 等：需要括号
    return False
```

### 语义判断示例

| 表达式 | AST类型 | 操作数 | 是否简单 | 求反结果 |
|--------|---------|--------|----------|----------|
| `sel` | NamedValue | - | ✅ | `!sel` |
| `!rst_n` | UnaryOp(Not, NamedValue) | NamedValue | ✅ | `!!rst_n` |
| `!!rst_n` | UnaryOp(Not, UnaryOp) | UnaryOp | ❌ | `!(!!rst_n)` |
| `valid && sel` | BinaryOp | - | ❌ | `!(valid && sel)` |
| `!(valid && sel)` | UnaryOp(Not, BinaryOp) | BinaryOp | ❌ | `!(!(valid && sel))` |

### 关键区别

- **字符串视角**：`!!rst_n` 以 `!` 开头 → 简单取反
- **语义视角**：`!!rst_n` 是 `UnaryOp(Not, UnaryOp(Not, NamedValue))` → 嵌套取反，需要括号

---

## 修复记录

### Issue: else-if 链条件错误 ✅ 已修复 (2026-05-26)

**问题现象**：
```
# 错误输出
when !valid && op_mode == 2'b01 && valid && op_mode == 2'b10: ...
# 矛盾条件：同时有 valid 和 !valid
```

**根本原因**：使用字符串匹配判断是否需要括号

**修复方案**：
1. 新增 `_is_simple_expr_for_negation()` 方法，用语义 AST 判断
2. context 中保存 `_parent_cond_expr`（表达式对象）
3. 访问 else 分支时，根据父条件的语义结构决定是否需要括号

**关键代码**：
```python
# 访问 else-if 时
parent_cond = self.current_ctx.get('condition', '')
parent_cond_expr = self.current_ctx.get('_parent_cond_expr', None)

if parent_cond:
    # 根据语义判断是否需要括号
    if parent_cond_expr and self._is_simple_expr_for_negation(parent_cond_expr):
        neg_parent = "!" + parent_cond  # 简单条件，直接加 !
    else:
        neg_parent = "!(" + parent_cond + ")"  # 复杂条件，加括号
```

**验证结果**：
```
# 正确输出
when !!rst_n && valid && op_mode == 2'b01: ...
when !!!rst_n && !(valid && op_mode == 2'b01) && valid && op_mode == 2'b10: ...
```

---

## 测试结果

```bash
cd ~/my_dv_proj/sv_query
python -m pytest sim/tests/ -v
# ================== 845 passed, 1 skipped, 1 warning ==================
```

---

## 相关文件

- `src/trace/core/visitors/statement_collector_visitor.py`
  - `_is_simple_expr_for_negation()`: 语义 AST 简单性判断
  - `visit_conditional_statement()`: else-if 链处理，栈操作
  - context 中的 `_parent_cond_expr` 字段

- `docs/CONTROL_FLOW_DEBUG.md` (本文档)