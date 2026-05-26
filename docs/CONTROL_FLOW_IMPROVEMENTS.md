# ControlFlow 改进方案

## 问题 1: 嵌套三元运算符条件

### 根因
**位置**: `SignalExpressionVisitor.get_all_conditional_op()` (line 6479)

**当前行为**: 
```python
def get_all_conditional_op(self, node) -> List[str]:
    # 提取 condition, left, right 的所有信号
    # 但不区分每个信号属于哪个分支
    return [sel, a, b, c]  # 丢失分支信息
```

### 改进方案

**方案 A**: 在 `SignalExpressionVisitor` 添加新方法
```python
def get_signals_with_conditions(self, node, parent_cond=None) -> List[Tuple[str, str]]:
    """返回 (signal, condition) 对列表
    
    对于嵌套三元 `a ? (b ? y1 : y2) : y3`:
    - y1 -> (y1, a && b)
    - y2 -> (y2, a && !b)  
    - y3 -> (y3, !a)
    """
```

**方案 B**: 在 `graph_builder.py` 的连续赋值处理中特殊处理 ConditionalOp

### 具体改动位置
1. `src/trace/core/visitors/signal_expression_visitor.py` - 添加 `get_signals_with_conditions()`
2. `src/trace/core/graph_builder.py` - 修改连续赋值边创建 (line 560-660)

---

## 问题 2: Case on signal 选择器为空

### 根因
**位置**: `statement_collector_visitor.py` - `_get_case_selector()` (line 660)

**问题**: 嵌套 case 时，inner case 是 `CaseStatementSyntax`（语法节点），不是 `CaseStatement`（语义节点）

**当前代码**:
```python
def _get_case_selector(self, node) -> str:
    expr = getattr(node, 'expr', None)
    if expr:
        sel_str = self._expr_to_string(expr)
        if sel_str:
            return sel_str  # 返回空字符串给 IdentifierNameSyntax
    return "?"  # 回退
```

**根因**: `_expr_to_string()` 不处理 `IdentifierNameSyntax`（语法树节点）

### 改进方案

**方案 A**: 修改 `_expr_to_string` 添加 `IdentifierNameSyntax` 处理
```python
# 在 _expr_to_string 中添加
if hasattr(expr, 'kind'):
    kind_name = expr.kind.name if hasattr(expr.kind, 'name') else str(expr.kind)
    if 'IdentifierName' in kind_name:
        # 直接返回 syntax 的字符串表示
        return str(expr).strip()
```

**方案 B**: 修改 `_get_case_selector` 直接处理 syntax 节点
```python
def _get_case_selector(self, node) -> str:
    # 语义路径
    expr = getattr(node, 'expr', None)
    if expr and hasattr(expr, 'kind'):
        kind_name = expr.kind.name if hasattr(expr.kind, 'name') else ""
        # 语义 NamedValueExpression
        if 'NamedValue' in kind_name:
            return self._expr_to_string(expr)
        # 语法 IdentifierNameSyntax - 直接返回 str
        if 'IdentifierName' in kind_name:
            return str(expr).strip()
    
    # 回退到 syntax.expr
    syntax = getattr(node, 'syntax', None)
    if syntax:
        expr = getattr(syntax, 'expr', None)
        if expr:
            return str(expr).strip()
    return "?"
```

### 具体改动位置
1. `src/trace/core/visitors/statement_collector_visitor.py`
   - `_expr_to_string()` - 添加 `IdentifierNameSyntax` 处理
   - 或 `_get_case_selector()` - 添加 syntax 节点直接处理

---

## 问题 3: always_comb 内嵌套 ternary 无输出

### 根因
**待进一步分析**

可能原因：
1. `always_comb` 块内的语句收集逻辑问题
2. 三元操作符在过程块内的处理与连续赋值不同

### 改进方案
需要先确认 `always_comb begin case(x) ... ternary ... end end` 的收集流程

---

## 优先级建议

| 问题 | 优先级 | 原因 |
|------|--------|------|
| 问题 2 | **高** | Case on signal 是常见模式，影响核心功能 |
| 问题 1 | 中 | 嵌套三元较少见，当前基本功能可用 |
| 问题 3 | 低 | 需要更多调试，可能涉及架构调整 |

---

## 验证方法

```bash
# 问题 2 验证
cat > /tmp/test_case.sv << 'EOF'
module top(input valid, data, output logic y);
    always_comb begin
        case (valid)
            1'b0: y = data;
            1'b1: y = data + 1;
        endcase
    end
endmodule
EOF
python run_cli.py controlflow analyze top.y -f /tmp/test_case.sv
# 期望: when valid == 1'b0, when valid == 1'b1

# 嵌套三元验证
cat > /tmp/test_nested_ternary.sv << 'EOF'
module top(input [1:0] sel, a, b, c, d, output logic y);
    assign y = (sel == 2'b00) ? a :
               (sel == 2'b01) ? b :
               (sel == 2'b10) ? c : d;
endmodule
EOF
python run_cli.py controlflow analyze top.y -f /tmp/test_nested_ternary.sv
# 期望: 4 个分支分别对应 4 个条件
```
