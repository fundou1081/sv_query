# REFACTOR: ExpressionTree 从 SignalGraph(semantic AST) 获取，消除 Syntax AST 冗余

> 创建时间: 2026-08-07
> 状态: 计划中（已按 2026-08-07 实证修订，v3 = A 计划，全量移入 SignalGraph）
> 来源: 方豆指出 viz_data_builder 重新使用 SyntaxTree.fromText() 违反了「所有数据从 SignalGraph 获取」的开发规则
> 范围: 方豆指示按 A 计划——所有数据都从 SignalGraph 获得，信息不够就增强 SignalGraph

---

## 问题

`viz_data_builder.py::_build_expr_trees_for_datapath` 重新调用 `SyntaxTree.fromText(src_text)` 解析源文件，做了一次**完全独立的 pyslang 解析**——跟 SignalGraph 构建时的 semantic 解析是两套独立流程。

### 冗余明细

```
viz_data_builder 当前:
  1. open(src).read()                        ← 重新读文件（tracer 已读过）
  2. SyntaxTree.fromText(src_text)           ← 全新解析（tracer 已用 semantic 解析过）
  3. st.root.members 遍历                    ← 手动 AST 遍历（driver_extractor 已遍历过）
  4. ContinuousAssign 提取                   ← 重复分析（driver_extractor 已处理）
  5. NetDeclaration 提取                     ← 重复分析（driver_extractor 已处理）
  6. always_comb/always_ff 提取              ← 重复分析（driver_extractor 已处理）
  7. _walk_procedural_statement 递归         ← 重复递归（driver_extractor 已处理）
```

**同时移除**: `source_files` 选项（VizBuildOptions 中不再需要，不再有文件 I/O）

---

## 根因

DriverExtractor 处理 RHS 的方式是「分解」——把复合表达式拆成多个 `(leaf_signal → dst)` 边：

```
assign y = a + b * c

DriverExtractor 输出:
  Edge(a → y, source.op="Add", source.side="left")
  Edge(b → y, source.op="Add", source.side="right")  # ← b*c 这层丢失！
  Edge(c → y, source.op="Add", source.side="right")  # ← c 被直接拉到顶层
```

viz 需要的是完整的 ExpressionTree：
```
  Add(a, Multiply(b, c))
```

所以 viz 层只能重新解析源文件来获取完整表达式树。

---

## 解决方案（v2，基于实证修订）

**不改变 ExpressionTree 解析引擎，而是在 DriverExtractor 已有的 assign 处理 flow 中，从 semantic AST 节点的 `.syntax` 构建完整表达式树，存入 `ExtractorResult.expr_trees` 容器。**

### 核心实证（2026-08-07 已跑通验证）

#### 1. semantic AST `.syntax` → syntax tokens，与 fromText 完全一致

```python
# ContinuousAssign (assign y = prod[15:8] + 8'd128)
semantic_rhs.syntax → SyntaxKind.AddExpression
list(syn) → [' prod[15:8]', ' +', " 8'd128"]   # 3 tokens ✅

# NetDeclaration init (wire sum = a + b)  ← 直接 init 就是 BinaryExpression，不是 EqualsValueClause！
net_decl.initializer → BinaryExpression
init.syntax → SyntaxKind.AddExpression
list(syn) → [' a', ' +', ' b']                 # ✅ 直接可用，无需 .expr.syntax
```

#### 2. 多分支 case 赋值：每个分支是独立 semantic 节点

case13 `result`（always_comb case）实测 5 个分支，每个 rhs 独立：

| 分支 | rhs.kind | rhs.syntax.kind | syntax tokens | 复杂度 |
|------|---------|-----------------|---------------|:---:|
| `mode==2'b0` | NamedValue | IdentifierName | `['data_in']` | 1 |
| `mode==2'b1` | NamedValue | IdentifierName | `['scaled']` | 1 |
| `mode==2'b10` | ConditionalOp | ConditionalExpression | `['valid ? data_minus_1 : offset']` | 3 |
| `mode==2'b11` | NamedValue | IdentifierName | `['data_sat']` | 1 |
| `default` | NamedValue | IdentifierName | `['data_in']` | 1 |

**同一 lhs，多个 rhs → 必须收集全部，再做「取最复杂」合并**（max by tree complexity），否则会退化成「取最后一个」（case13 result 会回归到 `data_in` 而非 `valid ? ... : offset`）。

#### 3. CallExpression（函数调用）完全可用

```
data_sat: init.kind=Call, syntax.kind=InvocationExpression
list(syn) → ['saturate', '({1'b0, data_in} + offset)']   # 2 tokens
```
这正好匹配 ExpressionTree._parse_expr 的「2-token 函数调用」分支 `[name, argumentlist]` ✅

---

## 数据流向设计

### 数据模型：ExprTree 收集方式（v2 修正）

**不再把 expr_tree 存到每条 TraceEdge 上**（因为多分支 case 是「1 个 dst → N 条边」，每条边只是 leaf→dst 关系，不是完整树）。而是在 `ExtractorResult` 上增加 `expr_trees` 容器，按 **lhs_name** 收集，同一 lhs 多 rhs 时取最复杂：

```python
# extractor_models.py
@dataclass
class ExtractorResult:
    nodes: list[TraceNode] = field(default_factory=list)
    edges: list[TraceEdge] = field(default_factory=list)
    expr_trees: dict[str, dict] = field(default_factory=dict)  # NEW: {lhs_name(key含module) → tree_dict}
```

### GraphBuilder 汇总（v2 修正 — 不存在 `_results` 属性）

实证：`_extract_all_nodes`/`_extract_all_edges` 用 `result = extractor.extract()` 局部变量，**没有存到 extractor 上**。需直接改 `_extract_all_edges`（或加 `_extract_all_expr_trees`）在 extract 后收集：

```python
# graph_builder.py
class SignalGraph(nx.DiGraph):
    def __init__(self):
        super().__init__()
        # ... existing ...
        self._expr_trees: dict[str, dict] = {}  # NEW

def _extract_all_edges(self):
    for _name, extractor in self._extractors.items():
        result = extractor.extract()
        for edge in result.edges:
            self.graph.add_trace_edge(edge)
        # ... existing port_to_internal 收集 ...
        # NEW: 收集 expr_trees
        if getattr(result, 'expr_trees', None):
            self.graph._expr_trees.update(result.expr_trees)
```

（在 `_extract_all_edges` 里收集即可，无需单独方法，避免 extractor 被调用两次。）

---

## 改动计划

### 文件 1: `src/trace/core/extractor_models.py`

`ExtractorResult` 新增 `expr_trees` 字段（±2 行）。

### 文件 2: `src/trace/core/driver_extractor.py`（核心改动）

#### 新增方法 `_store_expr_tree`（含多分支合并）

```python
def _store_expr_tree(self, lhs_name, rhs_expr, module_name, result):
    """从 rhs_expr.syntax 构建 ExpressionTree，存入 result.expr_trees。
    
    同一 lhs 多 rhs（case/if 多分支）时，收集所有 tree_dict，
    最后取「最复杂」（descendant count max）的代表。
    """
    from .graph.viz.expression_tree import ExpressionTree
    
    syntax = getattr(rhs_expr, 'syntax', None)
    if syntax is None:
        return
    try:
        tokens = list(syntax)
    except (TypeError, ValueError):
        return
    if not tokens:
        return
    
    root = ExpressionTree._parse_expr(tokens, 0, len(tokens))
    if root is None:
        return
    
    tree_key = f"{module_name}.{lhs_name}" if module_name else lhs_name
    tree_dict = ExpressionTree._to_dict(root)
    
    # 多分支合并：已有则取更复杂的
    existing = result.expr_trees.get(tree_key)
    if existing and _tree_complexity(tree_dict) <= _tree_complexity(existing):
        return  # 保留更复杂的
    result.expr_trees[tree_key] = tree_dict
```

#### 辅助函数 `_tree_complexity`

```python
def _tree_complexity(d: dict) -> int:
    """计算 tree_dict 的 descendants 总数（含自身）"""
    total = 1
    for c in d.get('children', []):
        total += _tree_complexity(c)
    return total
```

#### 调用点覆盖（v2 确认覆盖范围）

| 调用点 | 场景 | 是否覆盖 | 说明 |
|--------|------|:---:|------|
| `_handle_normal_assign` 末尾 | `assign y = ...` | ✅ | 主路径 |
| `_handle_call_assign` | `assign y = func(...)` | ✅ | case13 data_sat 在 netdecl 而非这里，但也要覆盖 |
| `_handle_binary_invocation_assign` | `assign y = a & func(b)` | ✅ | |
| `_create_net_decl_edges` | `wire sum = a + b` | ✅ | init 直接是表达式，`.syntax` 可用 |
| `_create_always_edges` 主路径 | `always_comb result = ...` | ✅ | 每个 case 分支 label 调用（多分支自动合并） |

**关键（来自实证 #5）**: `_create_always_edges` 的 `_collect_stmts_with_context` 已经把每个 case/if 分支展开成独立 `(assign_expr, context)` 条目。所以**在循环内对每个 `stmt`（ExpressionKind.Assignment）调用 `_store_expr_tree`**，多分支自然在 `_store_expr_tree` 里合并。

```python
# _create_always_edges 主循环内（lhs, rhs, rhs_expr = self._parse_assign(stmt) 之后）：
if lhs and rhs_expr is not None:
    self._store_expr_tree(lhs, rhs_expr, module_name, result)
    # 注意：不放 leaf_from_ctx 分支内；leaf_from_ctx 场景 rhs_expr 是展开后的零散值，跳过
```

#### 注意（实证发现）leaf_from_ctx 场景
`ctx["leaf_name"]` 分支（ternary 已展开）下，rhs_expr 可能是展开后的零散 leaf，不构建完整树——**放在 `if not leaf_from_ctx:` 内**。

### 文件 3: `src/trace/core/graph_builder.py`

`SignalGraph.__init__` 加 `_expr_trees`；`_extract_all_edges` 收集 `result.expr_trees`（如前）。

同时 `to_dict`/`from_dict` 序列化加 `_expr_trees`（保持 snapshot 完整）——**或**暂不加（viz 实时路径用）。**决定：加**，保持金标准完整。

### 文件 4: `src/trace/core/graph/viz/viz_data_builder.py`（删除冗余代码）

删除：
- `_build_expr_trees_for_datapath()` + 所有 SyntaxTree.fromText 代码
- `_extract_procedural_assignments()`
- `_walk_procedural_statement()`
- `_extract_module_name()`
- `from trace.core._pyslang_compat import SyntaxTree` 引用
- `VizBuildOptions.source_files` / `_enrich_datapath_info` 的 source_files 逻辑（含整个 regex const_map 源码扫描？——**见下方风险#6**）

替换 `_enrich_datapath_info` 末尾：

```python
# OLD:
_build_expr_trees_for_datapath(viz, dp, src_files, opts)

# NEW:
if hasattr(graph, '_expr_trees'):
    dp['expr_trees'] = dict(graph._expr_trees)
```

注意：`_enrich_datapath_info(viz, graph, opts)` 已经接收 `graph`，所以能直接访问 `graph._expr_trees`。

### 文件 5: 不动

- `expression_tree.py` — 不动（复用现有 `_parse_expr` + `_to_dict`）
- `viz_engine.py` — 不动
- `elk_bridge.py` — 不动
- `models.py` — 不动（TraceEdge 不加 rhs_expr 字段；用 ExtractorResult.expr_trees 容器）

---

## 改动统计（v2）

| 文件 | 改动 | 行数 | 复杂度 |
|------|------|:---:|:---:|
| `extractor_models.py` | `expr_trees` 字段 | +2 | 🟢 |
| `driver_extractor.py` | `_store_expr_tree` + `_tree_complexity` + 5 调用点 | +55 | 🟡🔴 |
| `graph_builder.py` | `_expr_trees` + collection + serialize | +20 | 🟢 |
| `viz_data_builder.py` | 删除冗余 + 切换数据源 | -160 / +5 | 🟢 |
| **总计** | | **~+82 / -160 = 净减 ~78 行** | |

---

## 测试计划

### Golden 一致性验证（关键）

**旧路径 vs 新路径 expr_trees 必须一致**，尤其验证 case13 多分支「取最复杂」：

```bash
cd ~/my_dv_proj/sv_query
python3 -c "
import sys; sys.path.insert(0, 'src')
from cli._viz_common import build_viz_tracer
from trace.core.graph.analyzer.signal_classifier import classify_graph
from trace.core.graph.viz.viz_data_builder import build_viz_data, VizBuildOptions

for fixture in [...8 golden cases...]:
    tracer, graph = build_viz_tracer(file=fixture, ...)
    viz = build_viz_data(graph, VizBuildOptions(target_module=..., ...))
    new_trees = graph._expr_trees
    old_trees = <从重构前快照或临时调用旧函数获取>
    assert new_trees == old_trees, fixture
"
```

### 重点回归：case13 result「取最复杂」不退化

```python
# 验证 result 的 expr_tree 是 Ternary(valid ? data_minus_1 : offset)，不是 data_in
assert graph._expr_trees['complex_design.result']['op'] == 'Ternary'
```

### 全量回归

```bash
python -m pytest sim/tests/unit/ -q --tb=line   # target: 980 pass, 0 regression
python -m pytest sim/tests/integration/ -q --tb=line
```

### 具体 golden cases

| Case | 场景 | 验证点 |
|------|------|--------|
| golden_dataflow_1_basic.sv | assign: y = a + b | 简单二元 |
| golden_dataflow_2_concat.sv | assign: y = {a, b} | 拼接 |
| golden_dataflow_3nested.sv | assign: y = a + b * c | 嵌套运算 |
| golden_dataflow_4_ternary.sv | assign: y = sel ? a : b | 三元 |
| golden_dataflow_5_combined.sv | wire + assign 多级 | 中间信号链 |
| golden_dataflow_8_ifelse.sv | always_comb if-else | if-else |
| golden_dataflow_9_case.sv | always_comb case | case 语句 |
| golden_dataflow_13_complex.sv | always_ff+always_comb+function+case | 复杂场景（含多分支取最复杂） |

---

## A 计划：const_map + func 信息也一并移入 SignalGraph

方豆指示按 A 计划，目标是全部数据从 SignalGraph 获得。

### A 计划实证（2026-08-07 已验证）

**旧 regex const_map 在 case13 直接为空 `{}`**：
- 依赖 `VizEdge.expression`，但该字段已被大段源码污染（`expression='\`timescale\nmodule...'`）
- 导致 `re.match(r'(?:assign|wire)...')` 匹配失败，const_map 全空

**而 expr_trees 的树遍历能拿到所有 Const 和 Call**（实测 case13）：
```
data_minus_1 → Const "8'd1"
data_sat     → Call  "saturate"
overflow     → Const "9'd255", "8'd250"
clamped     → Const "9'd255", "8'd255"
```

**结论**：从 expr_trees 树里提取 const_map 和 func 信息，**比旧 regex 更准确更完整**（旧方案在复杂 case 会漏）。

### A 计划改动：SignalGraph 增强 3 个容器

在 `SignalGraph` / `ExtractorResult` 上承载：

```python
# SignalGraph 新增（或 ExtractorResult）
_expr_trees:  dict[str, dict]   # {dst_key → tree_dict}
_const_map:   dict[str, list]   # {dst_short → [const_str,...]}  从 expr_trees 树遍历 Const 叶子提取
_func_info:   dict[str, tuple]  # {func_name → (msb,lsb)}       从 expr_trees 树遍历 Call 节点提取
```

### 提取逻辑（在 DriverExtractor 构建树时顺便做）

`_store_expr_tree` 构建完 tree_dict 后，同时遍历它填充 const_map / func_info：

```python
def _collect_from_tree(tree_dict, dst_short, const_map, func_info):
    """从树里提取 Const 叶子到 const_map，Call 节点到 func_info"""
    op = tree_dict.get('op'); lbl = tree_dict.get('label')
    if op == 'Const':
        if lbl not in const_map.setdefault(dst_short, []):
            const_map[dst_short].append(lbl)
    if op == 'Call':
        if lbl not in func_info:
            func_info[lbl] = None  # 宽度由 adapter 层语义解析补充（见下）
    for c in tree_dict.get('children', []):
        _collect_from_tree(c, dst_short, const_map, func_info)
```

### func_widths 来源（A 计划需要增强 SignalGraph）

旧 regex 从 `function [7:0] add_sat(...)` 提位宽。A 计划改为从 **semantic AST function symbol** 获取：

```python
# semantic_adapter.py — NEW get_function_width()
def get_function_width(self, func) -> tuple[int, int] | None:
    """从 function symbol 的 returnType 提取 (msb, lsb)

    function [7:0] saturate(...) → returnType=PackedArrayType
    getBitVectorRange() → "[7:0]" → 解析 (7, 0)
    标量函数 (无打包范围) → None (用 EffectiveWidth)
    """
    rt = getattr(func, 'returnType', None)
    if rt is None:
        return None
    try:
        rng = rt.getBitVectorRange()  # "[7:0]" 或 None
    except Exception:
        rng = None
    if rng:
        import re
        m = re.fullmatch(r'\[(\d+)(?::(\d+))?\]', str(rng).strip())
        if m:
            msb = int(m.group(1))
            lsb = int(m.group(2)) if m.group(2) else msb
            return (msb, lsb)
    return None
```

**实证确认（case13 `saturate`）**：
```
func = SubroutineSymbol
rt = func.returnType          → PackedArrayType
rt.getBitVectorRange()        → "[7:0]"  ✅
rt.fixedRange                 → "[7:0]"  ✅
rt.bitWidth                   → 8        （只有总宽，无 MSB/LSB 分离）
```

**集成点**（DriverExtractor.extract() 或新收集逻辑，每 module 处理时）：
```python
for fn in self.adapter.get_function_declarations(module):
    fn_name = self.adapter.get_function_name(fn)
    if fn_name not in func_info:
        func_info[fn_name] = self.adapter.get_function_width(fn)
```

`func_info` 存到 `ExtractorResult` / `SignalGraph`，viz 层读取。

**对比旧方案**：
| 维度 | 旧（regex 扫源码） | 新（semantic function symbol） |
|------|------------------|-------------------------------|
| 数据源 | `open().read()` + regex | semantic AST `.returnType` ✅ |
| 位宽准确性 | 依赖源码文本格式 | 精确类型系统 ✅ |
| 复杂函数（多层 packed + 无符号） | 可能 miss | `getBitVectorRange` 稳 |

**改动**：`semantic_adapter.py` 新增 `get_function_width(func)`（约 20 行），这是 A 计划唯一新增的 adapter 方法。

### 副作用（正向）

1. **修复 const_map 在复杂 case 为空的 bug**（从树提取比 regex 可靠）
2. `op_index` 本就来自 `e.source_op`（已在 SignalGraph）——顺带改从 graph 而非 viz.edges 读
3. 彻底消灭 viz 层 `_enrich_datapath_info` 的全部 `open().read()` + regex 源码扫描

---

## 风险点与对策（v3 = A 计划）

| # | 风险 | 实证状态 | 对策 |
|---|------|:---:|------|
| 1 | netdecl `init` 是 EqualsValueClause 需 `.expr.syntax` | ❌ 已证伪（实测 init 直接是 BinaryExpression） | 直接 `init.syntax` 即可 |
| 2 | GraphBuilder 有 `ext._results` 属性 | ❌ 已证伪（不存储） | 改 `_extract_all_edges` 内直接收集 |
| 3 | concat/call/binary_invocation 不覆盖 | ❌ 已证伪（netdecl 的 data_sat 已含 Call） | 仍需在 3 个 `_handle_*` 加调用 |
| 4 | 多分支「取最复杂」退化 | ✅ 已证（必须收集全部再 max） | `_store_expr_tree` 内做 max 合并 |
| 5 | leaf_from_ctx 分支 rhs 已拆解 | ✅ 已证 | `if not leaf_from_ctx:` 内才调用 |
| 6 | const_map / func 信息也移入 | ✅ 已证（A 计划） | 从 expr_trees 树遍历提取 Const/Call；func_widths 从 semantic function symbol 获取 |
| 7 | Snapshot 序列化缺 `_expr_trees`（及 const_map/func） | ⚠️ 待评估 | to_dict/from_dict 加字段保持完整 |
| 8 | 旧 const_map 在复杂 case 为空（bug） | ✅ 已证（case13 实测空） | A 计划从树提取，顺带修复 |

---

## 预估工时（v3 = A 计划）

| Phase | 内容 | 预估 |
|-------|------|:---:|
| 0 | 实证（已完成） | ✅ | — |
| 1 | `ExtractorResult` + `SignalGraph` 增字段（expr_trees/const_map/func_info） | 0.5h |
| 2 | DriverExtractor `_store_expr_tree`（含多分支合并）+ `_collect_from_tree` + 5 调用点 | 3h |
| 3 | func_widths 从 semantic function symbol 获取（adapter 增强） | 1h |
| 4 | GraphBuilder 收集 + serialize | 1h |
| 5 | viz_data_builder 删除 `_enrich_datapath_info` 全部源码扫描 + 切换数据源 | 1.5h |
| 6 | Golden 一致性 + const_map 修复验证 + 全量回归 | 2h |
| **总计** | | **~9h** |

---

## 执行记录

- [ ] 2026-08-07 v1 初版计划写完
- [ ] 2026-08-07 v2 实证修订：netdecl init 直接可用、GraphBuilder 无 _results、多分支需 max 合并、concat/call 需覆盖
- [ ] 2026-08-07 v3 = A 计划：方豆指示全部数据从 SignalGraph，连 const_map/func 也移入；实证旧 const_map 在 case13 为空、树遍历能提取全部 Const/Call
- [ ] Phase 1: 数据模型增强（expr_trees/const_map/func_info）
- [ ] Phase 2: DriverExtractor `_store_expr_tree` + `_collect_from_tree`
- [ ] Phase 3: func_widths 从 semantic function symbol 获取
- [ ] Phase 4: GraphBuilder 收集 + serialize
- [ ] Phase 5: viz_data_builder 切换 + 删除源码扫描
- [ ] Phase 6: 测试验证（含 const_map 修复确认）
