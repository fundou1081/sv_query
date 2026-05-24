# Issue 17 根因分析

**问题**: 非ANSI端口 `p` 位宽丢失 (应 `[29:0]`)

---

## 根因分析

### bs_mult 源代码结构

```verilog
module bs_mult(clk, x, y, p, firstbit, lastbit);  // 非ANSI端口列表
    input clk;                                      // 无位宽 → 1-bit
    input x, y, firstbit, lastbit;                  // 无位宽 → 1-bit
    output p;                                       // 无位宽 → ???

    wire [29:0] pout;                              // pout 有位宽 [29:0]
    wire [30:0] rout;
    wire [30:0] cout;

    bs_mult_slice I0(... .pout(p), ...);            // I0.pout 连接 p
```

### 问题本质

**`p` 端口没有独立的位宽声明**。它的位宽信息完全来自实例连接：
- `I0.pout(p)` 表示 `I0` 的 `pout` 端口连接到 `p`
- `pout` 是 `wire [29:0]`，所以 `p` 也是 `output [29:0]`

### pyslang AST 分析

| 节点 | kind | header.dataType | dimensions |
|------|------|-----------------|------------|
| clk PortDeclaration | PortDeclaration | None (ImplicitType) | None |
| p PortDeclaration | PortDeclaration | None (ImplicitType) | None |
| pout NetDeclaration | NetDeclaration | None (implicit wire) | [29:0] 在 declarator 上 |

**结论**: `p` 的位宽**无法从其自身获取**，只能从实例连接推断。

---

## 当前行为

`extract_port_width_with_eval()` 处理非ANSI端口时：
1. 获取端口名 `p`
2. 在 `scope.members` 中查找匹配的 `PortDeclaration`
3. 如果找到，递归提取其位宽
4. **如果找不到匹配的声明，返回空结果**

对于 `p`:
- 找不到 `output [29:0] p;` 这样的声明
- 返回 `{'msb_eval': None, 'lsb_eval': None}`

---

## 解决方案

### 方案 A: 后处理推断 (推荐)

在 GraphBuilder 完成节点构建后，对顶级模块端口进行宽度推断：

```python
def _infer_top_port_widths(self):
    """对顶级模块中位宽为 (0,0) 的端口，尝试从连接推断"""
    for node in self.graph.nodes():
        if node.module not in self.adapter.get_module_names():
            continue
        if node.kind not in [NodeKind.PORT_IN, NodeKind.PORT_OUT, NodeKind.PORT_INOUT]:
            continue
        if node.width != (0, 0):
            continue
        
        # 查找连接到该端口的边
        for src, dst in self.graph.edges():
            if dst == node.id:
                src_node = self.graph.get_node(src)
                if src_node and src_node.width != (0, 0):
                    node.width = src_node.width
                    break
```

### 方案 B: 修改 extract_port_width 逻辑

在 `extract_port_width_with_eval` 返回空结果时，尝试从实例连接推断。

**缺点**: 需要访问实例连接信息，超出了该方法的职责范围。

---

## 推荐方案

**方案 A** - 在 GraphBuilder 中后处理

理由:
1. 不改变现有 API 契约
2. 端口宽度推断是图构建的一部分
3. 可以利用完整的连接信息

---

## 验证方法

修复后:
```python
# 解析 bs_mult.v + bs_mult_slice.v
trees = {
    'bs_mult.v': pyslang.SyntaxTree.fromFile(...),
    'bs_mult_slice.v': pyslang.SyntaxTree.fromFile(...),
}
tracer = UnifiedTracer(trees=trees)
tracer.build_graph()

# p 端口位宽应为 (29, 0)
# 边数应 > 3，包含 CONNECTION 边
```