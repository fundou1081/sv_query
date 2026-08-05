# Expression Tree Proposal (草案)

## 问题

`driver_extractor` 的 `source_op` 提取把嵌套表达式扁平化了。例如：
`assign z = (a * b) + c;` 中，pyslang AST 有完整的树结构 `Add(Mul(a,b), c)`，
但 `source_op` 把所有边都标为 `Add`，丢失了乘法中间步骤。

## 方案

在 `viz_data_builder` 或新增模块中，直接从 pyslang raw AST 节点重建表达式树。

### 新增数据结构

```python
@dataclass
class ExprNode:
    id: str             # 唯一 ID
    op: str             # Add, Multiply, Const, SignalRef, Slice, Concat, Call
    label: str          # 显示标签: +, x, 8'd128, a, [7:0], {}, add_sat
    children: list['ExprNode']
    width: tuple|None   # (msb, lsb)
```

### 数据流

```
pyslang raw AST node (raw_rhs) 
  → ExpressionTree.build(assign_node) → ExprNode 树
  → elk_bridge 递归渲染
```

### 实现路径

1. **探索 pyslang semantic AST API** — `root.topInstances` → `inst.body` → member 的 `getAssignmentExpressions()`
2. **实现 `ExpressionTree.build()`** — 递归 walk pyslang AST 节点:
   - BinaryExpression → 创建 `ExprNode(op=detect_op, children=[left_subtree, right_subtree])`
   - ConditionalExpression → 再拆分（ternary scope 已有处理）
   - LiteralExpression → `ExprNode(op=Const, label=str(raw_val))`
   - NamedValueExpression → `ExprNode(op=SignalRef, label=name)`
   - ConversionExpression → passthrough to inner
   - ConcatenationExpression → `ExprNode(op=Concat, label='{}', children=[...])`
   - CallExpression/InvocationExpression → `ExprNode(op=Call, label=func_name, children=[...])`
3. **elk_bridge 增加 `_render_expr_tree`** — 递归渲染 ExprNode 为 ELK nodes/edges
4. **渐进式迁移** — VizData.meta 加 `expr_trees: dict[str, ExprNode]`，elk_bridge 优先用树渲染，fallback 到现有逻辑

### 关键点

- **表达式树在 VizData 层**，不侵入 elk_bridge 的数据流判断
- **fallback 安全** — 无表达式树时完全回到现有逻辑
- **渐进式覆盖** — 先做 case 10 的 `(a * b) + c`，再扩展到其他表达式类型

## TODO

- [ ] 确认 pyslang API 如何获取每个 assign 的 raw expression node
- [ ] 实现 ExpressionTree.build()
- [ ] elk_bridge._render_expr_tree()
- [ ] 回归测试（batch 29 golden）
