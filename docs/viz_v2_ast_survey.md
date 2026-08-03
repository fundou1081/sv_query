# pyslang Semantic AST 摸底 —— Statement 层可行性结论

> 摸底日期：2026-08-02
> 测试文件：fixed_point_patterns.sv / fsm_demo.sv

---

## pyslang body 中的成员类型

```
SymbolKind.Port             → 端口声明
SymbolKind.Net              → wire/reg 声明的符号 (有 .initializer 属性)
SymbolKind.Variable         → reg 在 always 块中赋值的符号 (无 .initializer)
SymbolKind.Parameter        → parameter/localparam
SymbolKind.ContinuousAssign → assign 语句 (.assignment = AssignmentExpression)
SymbolKind.ProceduralBlock  → always@ / always_ff / always_comb (.procedureKind)
```

## 各级结构

### ContinuousAssign (assign 语句)

```
ContinuousAssign
├── .assignment (AssignmentExpression)
│   ├── .left   → NamedValueExpression (LHS, _extract_signals 可拿信号名)
│   └── .right  → 各种 Expression:
│       ├── BinaryOp:      .op=Add/Multiply/...   .left / .right 有信号名
│       ├── ConditionalOp: .conditions=[]  .Left=.Right 有分支信号
│       └── Conversion:    unwrap() 后得到内部 Expression
│   .location.offset       → 源码位置 (可用于行号计算)
│   .syntax.sourceRange    → 源码位置 (更精确, line/column 可用)
```

**可提取的 Statement 字段**：
- lhs: ✅ `_extract_signals_from_expr(left)`
- rhs_expression: ❌ 需要从 syntax 取源码文本，或从 AST 递归重建
- operator/operator_symbol: ✅ `BinaryOp.op`
- operands: ✅ `_extract_signals_from_expr(side)` for BinaryOp
- true_condition: ✅ 对于 ConditionalOp，`.Left` 和 `.Right` 的分支信号已提取
- 但 `.conditions` 返回空 list —— 条件信号需要从 `.Left/.Right` 的差异推断

### NetSymbol (wire 声明带初始值)

```
NetSymbol
├── .initializer → 各种 Expression (BinaryOp/Conversion/...)
├── .location.offset
└── .name
```

**可提取的 Statement 字段**：
- lhs: ✅ `.name`
- rhs_expression: ❌ 需要 syntax 源码文本
- operator/operands: ✅ 跟 ContinuousAssign 一样解析 .initializer
- assign_type: ✅ "net_decl"
- true_condition: ❌ wire 声明无条件

### ProceduralBlock (always@ / always_ff / always_comb)

```
ProceduralBlock (.procedureKind = Always/AlwaysFF/AlwaysComb)
├── .body (TimedStatement)
│   ├── .timing → SignalEventControl (提取敏感列表: posedge clk)
│   └── .stmt (BlockStatement)
│       └── .body (StatementList)
│           └── list of Statement:
│               ├── CaseStatement → 可提取 case label 和条件
│               ├── ConditionalStatement (if/else)
│               ├── ExpressionStatement → AssignmentExpression
│               └── ...
```

**可提取的 Statement 字段**：
- procedural_block: ✅ `.procedureKind` (Always/AlwaysFF/AlwaysComb)
- clock_signal: ✅ 从 TimedStatement.timing 提取
- assign_type: ✅ 从 statement 类型推断 (nonblocking <= vs blocking =)
  - 但 pyslang AST 不直接区分 <= 和 =
  - 需要检查 AssignmentExpression 的 syntax kind
- true_condition: ✅ if/else → ConditionalStatement

### 问题

... 继续

---

## 结论：Statement 层可行，但有 3 个限制

### ✅ 可以提取的

| 字段 | 来源 | 难度 |
|------|------|------|
| lhs | `_extract_signals_from_expr(left)` | 低 |
| operands | `_extract_signals_from_expr(side)` for each BinaryOp side | 低 |
| operator | BinaryOp.op.name → "Add" | 低 |
| operator_symbol | 映射表 Add→+ | 低 |
| assign_type | NetSymbol→net_decl, ContinuousAssign→continuous, ProceduralBlock→nonblocking/blocking | 低 |
| procedural_block | ProceduralBlock.procedureKind | 低 |
| clock_signal | TimedStatement.timing → SignalEventControl | 低 |
| source_file | SyntaxTree 文件名 | 低 |
| source_line | SyntaxTree 根据 offset 算行号 | 低 |
| lhs_width | left.type → 提取位宽 | 低 |
| port_connection | InstanceSymbol.portConnections | 低 |
| function_call | 检测 CallExpression | 低 |

### ⚠️ 可以但有挑战的

| 字段 | 挑战 |
|------|------|
| rhs_expression | pyslang AST 不直接存储源码文本。需要要么用 syntax node range 从源文件读，要么从 AST 递归拼接 |
| true_condition | ConditionalOp 的 condition 字段不可用（空 list）。需要 if-else / case 语句级别的条件提取 |
| inner_ops | 需要在 BinaryOp 嵌套中递归提取，当前已有 `_detect_binary_op` 可以做 |
| alternatives | 三元运算符的 else 分支可以用 `right`，多分支需要更多逻辑 |

### ❌ 目前拿不到的

| 字段 | 原因 |
|------|------|
| 条件表达式文本 (foo > bar) | ConditionalOp.conditions 返回空 list，只能用信号差异推断"控制信号"但不能拿到源码文案 |
| reset_signal | 需要从 procedural block 的 if 语句中识别异步复位 pattern |
| enable_signal | 需要从 if 语句中识别 enable pattern |
| cycle delta | 需要 always_ff 中识别 <= 赋值 vs 组合逻辑中的 = 赋值 |

### 关键发现：AST 不存源码文本

pyslang semantic AST 的 Expression 节点**不包含源码文本**。源码文本需要通过 syntax node 的 sourceRange 从原始文件中读取。这意味着：

1. `rhs_expression = "(sum_ac + 16'd128) >>> 8"` 需要从文件读
2. `true_condition = "!(sum_ab > 16'd255)"` 需要从文件读
3. 运算符符号（+/*/>>>）已经在 AST 中（BinaryOp.op.name），不需要源码文本

**替代方案**：不依赖于从文件读取源码文本。在 Statement 层中，只存储**结构化的条件数据**（条件信号列表、比较运算符、阈值），而不是原始文本。这符合 "基于 semantic AST" 的原则。

例如：
```python
# 不存: true_condition_text = "!(sum_ab > 16'd255)"
# 而存:
true_condition_signals = ["sum_ab"]
true_condition_comparison = ("GreaterThan", "16'd255")  # 比较类型 + 阈值
true_condition_negated = True  # 前面有 !
```
