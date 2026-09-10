# 项目开发铁律

> 最后更新: 2026-07-29 (V6.8)
> 整合自: CODE_DISCIPLINE_REVIEW.md (2026-05-23) + CODE_DISCIPLINE_FIX_COMPLETENESS.md (2026-07-15) + V6.8 审查

---

## 铁律0: Semantic AST 唯一数据源 ⭐ V6.8

**所有代码数据提取必须使用 pyslang Semantic AST，禁止使用 Syntax AST 提取代码内容。**

### 典型案例: case item condition 含注释 (V6.8修复)

`StatementCollectorVisitor` 使用了 Syntax `StandardCaseItemSyntax.expressions` 而非 Semantic `ItemGroup.expressions`，导致 condition 字符串被注释污染。

```verilog
// RTL:
case (op) 2'd0: y = a + b; // ADD  ← 注释污染
// 错误结果 (Syntax): condition = "op == // ADD\n            2'd0"
// 正确结果 (Semantic): condition = "op == 2'b0"  (ConversionExpression.operand.value)
```

### 细则

1. **优先 Semantic 路径**: 始终通过 `compilation.getRoot()` → `topInstances[0].body` → `ProceduralBlockSymbol.body` → `.visit()` 遍历 AST
2. **Syntax 仅作位置参考**: `.syntax` 可获取 `SourceLocation` (file:line)，但**不可用于提取代码内容**
3. **找不到 Semantic 路径时**: 主动 `raise NotImplementedError` 或标记 confidence="uncertain"，记录到 `KNOWN_LIMITATIONS.md`
4. **禁止静默回退**: 不允许在 Semantic 不可用时静默回退到 Syntax 路径

### 检查清单

- [ ] 所有表达式值通过 Semantic `.value`/`.symbol`/`.operand` 获取
- [ ] 没有代码使用 Syntax 节点的 `__str__` 提取代码内容
- [ ] 遇到未知 expression kind 时主动报错，不静默跳过
- [ ] 新加 handler 验证 `condition_ast` 类型是 Semantic

---

## 铁律1: AST 唯一数据源

pyslang `Compilation.getRoot()` 为唯一可信 AST 数据源。不使用正则匹配解析 SV 代码。不使用 `SyntaxTree.fromText/fromFile`。

### 代码审查状态

| 文件 | 方式 | 状态 |
|------|------|------|
| `compiler.py` | `Compilation` + `getRoot()` | ✅ |
| `semantic_adapter.py` | 基于 `comp.getRoot()` | ✅ |
| `graph_builder.py` | 通过 SemanticAdapter | ✅ |
| `visitors/` | Visitor 遍历 AST | ✅ (V6.8修复后) |
| `uvm_testbench_extractor.py` | ⚠️ SyntaxTree (UVM宏展开限制) | 已记录 |

---

## 铁律2: 位精确性

`data[7:0]` ≠ `data[15:8]`，信号必须保留完整位级信息。

V6.5 `SignalSource` 提供结构化位精确存储 (`bit_start`/`bit_end` int)。

---

## 铁律3: 不可信则不输出

无法解析时必须返回 `confidence: "uncertain"`，记录到 `errors` 列表。

拒绝反模式:
- ❌ 不能故意让 bug 通过 (`test_X_documented_leak`)
- ❌ 不能部分修复 (只修一条路径)
- ❌ 不能用 TODO 注释代替修复

---

## 铁律4: 不允许创建孤儿节点

添加 TraceEdge 时，目标节点不存在则创建 placeholder。

---

## 铁律13: 金标准测试优先

每个新功能必须有 golden test。golden 对比 VizData 数据层（不对比 DOT 字符串）。

---

## 铁律14: Syntax 中间层

GraphBuilder 必须通过 PyslangAdapter 获取信息，不直接访问 pyslang API。

---

## 铁律15: Visitor 模式

AST 遍历必须使用 Visitor 模式（`@on` handler 或方法分派），禁止 if-elif 链。

---

## 铁律16: ENABLE/DATA 不作为独立边类型

ENABLE 用 `TraceEdge.condition` 替代，DATA 已与 DRIVER 合并。

---

## 铁律26: 禁止 if-elif AST 遍历

所有 AST 节点遍历统一走 Visitor 分派。

---

## 铁律29: Visitor 调用统一入口

所有 Visitor 调用统一通过 `extract()` 方法。

---

## 铁律30-32: Handler 规范

30. Handler 名称必须与 pyslang SyntaxKind 完全一致，禁止自创
31. 创建 Handler 前必须验证 pyslang 中存在对应类型
32. 同一个 Handler 只允许定义一次

---

## 铁律33: 基础组件必须彻底修复

- 一旦发现 bug → 必须彻底修所有等价路径
- 不接受 "Known Limitation" 作为不修复的理由
- 测试不能故意失败 (`test_X_documented_leak`)
