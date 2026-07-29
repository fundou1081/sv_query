# 项目开发铁律

> 更新: 2026-07-29 (V6.8)
> 这些铁律不可违反。违反需要在 CODE_DISCIPLINE_VIOLATIONS.md 记录。

---

## 铁律0: Semantic AST 唯一数据源 ⭐ NEW V6.8

**所有代码数据提取必须使用 pyslang Semantic AST（Compilation → getRoot() → body.visit()），禁止使用 Syntax AST 提取代码内容。**

### 典型案例: case item condition 含注释 (2026-07-29)

**问题**: `StatementCollectorVisitor.visit_case_statement()` 使用了 Syntax `StandardCaseItemSyntax.expressions` 来提取 case 条件表达式。Syntax AST 的 `__str__` 返回的是**原始源码文本**（含注释/空白），导致 condition 字符串被污染。

```verilog
// RTL:
case (op)
    2'd0: y = a + b;   // ADD   ← 注释污染
    2'd1: y = a - b;   // SUB
endcase

// 错误结果 (Syntax AST):
condition = "op == // ADD\n            2'd1"   // 注释嵌入!

// 正确结果 (Semantic AST):
condition = "op == 2'b1"                        // 干净数值
```

**根因**: Syntax `IntegerVectorExpressionSyntax.__str__` 包含源码注释/空白。Semantic `ConversionExpression.operand.value` 是 elaboration 后的干净数值。

**修复**: 改用 Semantic `ItemGroup`（pyslang Semantic AST 的 case item）替代 Syntax `StandardCaseItemSyntax`。通过 `ProceduralBlockSymbol.body.visit()` 遍历 Semantic 树。

**教训**: Syntax AST 的 `__str__` **不可信** — 它返回源码原始文本（含注释、空白、trivia）。只有 Semantic AST 的属性（`.value`, `.symbol`, `.kind`）才是 elaboration 后的可靠数据。

### 铁律0细则

1. **优先 Semantic 路径**: 始终通过 `compilation.getRoot()` → `topInstances[0].body` → `ProceduralBlockSymbol.body` → `.visit()` 遍历 AST
2. **Syntax 仅作位置参考**: `.syntax` 可用于获取 `SourceLocation`（file:line），但**不可用于提取代码内容**
3. **找不到 Semantic 路径时**: 主动报错或标记，记录在 `KNOWN_LIMITATIONS.md`，交给用户决策
4. **禁止静默回退**: 不允许在 Semantic 不可用时静默回退到 Syntax 路径

### 检查清单

开发新功能时，确保:

- [ ] 所有表达式值通过 Semantic AST `.value`/`.symbol`/`.operand` 获取
- [ ] 没有代码使用 Syntax 节点的 `__str__` 来提取代码内容
- [ ] 遇到未知 expression kind 时主动 `raise NotImplementedError`，不静默跳过
- [ ] 新加 handler 验证 `condition_ast` 的类型是 Semantic（不是 Syntax）

---

## 铁律1: AST 唯一数据源

pyslang Compilation + getRoot() 为唯一可信 AST 数据源。不使用正则匹配解析 SV 代码。

---

## 铁律4: 不允许创建孤儿节点

添加 TraceEdge 时，如果目标节点不存在则创建 placeholder，记录在 `KNOWN_LIMITATIONS.md`。

---

## 铁律13: 金标准测试优先

每个新功能必须有 golden test。golden 对比 VizData 数据层（不是 DOT 输出）。

---

## 铁律15: Visitor 模式

AST 遍历必须使用 Visitor 模式（`@on` handler 或方法分派），禁止 if-elif 链。

---

## 铁律16: ENABLE/DATA 不作为独立边类型

ENABLE 用 TraceEdge.condition 替代，DATA 已与 DRIVER 合并。

---

## 铁律26: 禁止 if-elif AST 遍历

所有 AST 节点遍历统一走 Visitor 分派。

---

## 铁律29: Visitor 调用统一入口

所有 Visitor 调用统一通过 `extract()` 方法（不是 `visit()` 或 `get_all_signals()` 直接调用）。
