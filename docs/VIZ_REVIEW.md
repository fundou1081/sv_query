# dataflow 绘图代码 review & 增强方案

## 当前架构 (1313行, 4文件)

```
SignalGraph (networkx)
    │
    ▼
viz_data_builder.py (296行)  ──→  VizData  ──→  viz_engine.py (548行)
     │                                           │
     ├─ _passthrough_op_chain                     ├─ OP/const/concat/slice构建
     │   Phase A: 同位边补全 (同一dst多条入边)        ├─ sig_op_index 信号→OP索引
     │   Phase B: 下游透传 (中间wire的inner_ops)     ├─ scope渲染 (双线实框+TRUE/FALSE+rank=same)
     │                                             ├─ stage cluster渲染
     │                                             └─ 非OP条件边渲染
     │
     ├─ control_tree.py (254行)
     │   └─ build_control_tree: condition_chain → MuxNode tree
     │
     └─ viz_data_models.py (215行)
         ├─ VizNode.from_trace_node
         └─ VizEdge.from_trace_edge
```

## 现状问题

### 问题1: OP节点入边数不准确 (checker发现)
| 种类 | 表现 | 根因 |
|------|------|------|
| 常量缺失 | `>>` 入边=1 期望=2 | const_map 覆盖不全 (wire声明中的常量未完全提取) |
| 三目汇聚 | `+` 入边=6 (if-else) | 多条condition边直接连到同一OP, 未经过MUX汇聚 |
| scope 分支 | `+` 入边=1 (三目混合) | scope分支框内OP只从中间信号入, 常量/另一操作数没连 |

### 问题2: 缺少MUX汇聚层
if/case/三目选择出的信号, 当前直接连到OP节点, 造成:
- 一个OP节点有4-6条入边 (逻辑上应该是 2操作数 × N分支)
- 数据流拓扑不正确

**正确流程**: `signalA─cond₀─→[MUX]→[+]→result`
                     `signalB─cond₁─↗`

### 问题3: Phase A 同位边补全过于激进
`_passthrough_op_chain` 的 Phase A 把同一dst的所有入边合并到同一个OP, 不考虑它们来自不同condition。应该:
- 先按 condition 分组
- 同 condition 内的多条边共享OP
- 不同 condition 的边先经MUX汇聚

### 问题4: const_map 提取不完整
- 只解析 wire 和 assign 声明
- 没有解析 `always_comb begin ... end` 中的阻塞赋值
- 没有处理 `{1'b0, data_in} + offset` 这种拼接+运算的复合表达式

## 增强方案

### 1. 在 viz_data_builder 中引入 MUX 节点生成 (核心改动)

```python
def _build_mux_nodes(viz, node_map):
    """
    Phase C: 对于同一个 dst 的多条带不同 condition 的边,
    生成 MUX 节点汇聚, 然后 MUX→dst.
    
    逻辑:
    1. group edges by (dst, source_op)
    2. 如果同组有2+不同 condition → 生成 MUX
    3. MUX节点: id='op_mux_{dst}', kind='MUX', inputs按condition排序
    4. 替换原始边: signal_i → MUX → dst
    """
```

### 2. 完善 const_map 提取
- 解析 `always_comb` 中的阻塞赋值
- 处理复合表达式中的常量 (如 `{1'b0, data_in} + offset`)

### 3. 内建 checker 作为 viz_engine 的可选后处理
- `check_op_arity(dot) → list[Issue]` 
- 在 render 后自动调用, 发现异常时打印警告
- 可配置为 strict 模式: 异常时抛错

### 4. 重构 viz_engine.py 为三个独立渲染器
当前548行单文件, 建议拆分为:
- `viz_dataflow_stage.py` — stage cluster + 非scope边渲染
- `viz_dataflow_scope.py` — scope框渲染 (当前已较清晰)
- `viz_dataflow_ops.py` — OP/const/concat/slice节点生成

## 优先级

1. **高**: MUX汇聚层 (问题1+2, 影响数据流正确性)
2. **中**: const_map完善 (问题1, 常量缺失)
3. **低**: 文件拆分 (问题4, 可维护性)
