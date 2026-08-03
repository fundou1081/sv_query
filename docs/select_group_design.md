# select_group 数据结构设计

## 核心思想

condition_chain 携带"条件累积"（用于 dataflow 图虚线标注），
select_group 携带"互斥选择"（用于 control 图 mux/case/if 渲染）。

两个字段互补，一个 TraceEdge 同时拥有两者。

---

## 数据结构

```python
@dataclass  
class SelectBranch:
    """选择结构中的一个分支。"""
    condition: str               # 分支条件表达式 "sel" | "sel_d == 2'd0" | "default"
    is_default: bool = False     # 是否 default 分支 (case/if-else 的 else)
    is_negation: bool = False    # 是否取反分支 (else / ?: 的 false 分支)


@dataclass
class SelectGroup:
    """一组互斥的选择分支，来自 if/else | case | ?: 等选择结构。
    
    存储在 SignalGraph.select_groups: dict[str, SelectGroup] 中。
    TraceEdge.select_group_id 指向此表。
    """
    id: str                      # 唯一标识 "sg_1"
    kind: str                    # "ternary" | "if_else" | "case"
    
    # 条件信号: 这个选择结构基于哪些信号做判断
    # 例: if(sel_a) → ["sel_a"]
    # 例: case(sel_b) → ["sel_b"]  
    # 例: sel ? a : b → ["sel"]
    condition_signals: list[str]
    
    # 分支列表
    branches: list[SelectBranch]
    
    # 嵌套关系: 如果这个选择结构在另一个选择结构内部
    # 例: case(sel_d) { if(sel_f) y <= a; } 
    #     → SelectGroup("if_else", parent="sg_outer")
    parent_group_id: str = ""   # 外层 SelectGroup ID


@dataclass
class TraceEdge:
    # ... 现有字段 ...
    
    # [V7.0 NEW] 条件信息
    condition_chain: list[str] = []    # 嵌套条件累积 ["sel_d==0", "sel_f"]
    select_group_id: str = ""          # 指向 SelectGroup 表
    select_branch: int = 0             # 在 SelectGroup.branches 中的序号
```

---

## 三种选择结构的处理

### 1. 三目运算符

```verilog
assign y = sel ? a : b;
```

产生:
```python
SelectGroup(
    id="sg_1", kind="ternary",
    condition_signals=["sel"],
    branches=[
        SelectBranch(condition="sel"),
        SelectBranch(condition="!sel", is_negation=True),
    ])

TraceEdge(a→y, condition_chain=["sel"], select_group_id="sg_1", select_branch=0)
TraceEdge(b→y, condition_chain=["!sel"], select_group_id="sg_1", select_branch=1)
```

control 图渲染:
```
      ┌── sel=1 ──▶ a ──┐
sel ──┤                  ├──▶ y
      └── sel=0 ──▶ b ──┘
```

### 2. if/else

```verilog
if (en)      y <= a;
else         y <= b;
```

产生:
```python
SelectGroup(
    id="sg_2", kind="if_else",
    condition_signals=["en"],
    branches=[
        SelectBranch(condition="en"),
        SelectBranch(condition="!en", is_negation=True),
    ])

TraceEdge(a→y, condition_chain=["en"], select_group_id="sg_2", select_branch=0)
TraceEdge(b→y, condition_chain=["!en"], select_group_id="sg_2", select_branch=1)
```

control 图渲染:
```
      ┌── en=1 ──▶ a ──┐
en ───┤                 ├──▶ y
      └── en=0 ──▶ b ──┘
```

### 3. case

```verilog
case (sel_b)
    2'd0:    y <= a;
    2'd1:    y <= b;
    default: y <= c;
endcase
```

产生:
```python
SelectGroup(
    id="sg_3", kind="case",
    condition_signals=["sel_b"],
    branches=[
        SelectBranch(condition="sel_b == 2'd0"),
        SelectBranch(condition="sel_b == 2'd1"),
        SelectBranch(condition="default", is_default=True),
    ])

TraceEdge(a→y, condition_chain=["sel_b == 2'd0"], select_group_id="sg_3", select_branch=0)
TraceEdge(b→y, condition_chain=["sel_b == 2'd1"], select_group_id="sg_3", select_branch=1)
TraceEdge(c→y, condition_chain=["sel_b == default"], select_group_id="sg_3", select_branch=2)
```

control 图渲染:
```
        ┌── 2'd0 ──▶ a ──┐
        ├── 2'd1 ──▶ b ──┤
sel_b ──┤                  ├──▶ y
        └── default ──▶ c ─┘
```

---

## 嵌套情况的处理

```verilog
case (sel_d)              // SelectGroup A
    2'd0: y <= (sel_f ? a : b);  // SelectGroup B, parent=A
    2'd1: y <= (sel_f ? c : d);  // SelectGroup C, parent=A
endcase
```

产生:
```python
SelectGroup A: case, condition_signals=["sel_d"], branches=[2'd0, 2'd1]
    SelectGroup B: ternary, condition_signals=["sel_f"], parent_group_id="A"
        branch 0: "sel_f"      → TraceEdge(a→y, condition_chain=["sel_d==0", "sel_f"])
        branch 1: "!sel_f"     → TraceEdge(b→y, condition_chain=["sel_d==0", "!sel_f"])
    SelectGroup C: ternary, condition_signals=["sel_f"], parent_group_id="A"
        branch 0: "sel_f"      → TraceEdge(c→y, condition_chain=["sel_d==1", "sel_f"])
        branch 1: "!sel_f"     → TraceEdge(d→y, condition_chain=["sel_d==1", "!sel_f"])
```

**condition_chain 是如何得到的**: 遍历 SelectGroup 树，从根到当前分支：
- 节点在 A.branches[0] 下 → chain = ["sel_d == 2'd0"]
- 节点在 A.branches[0].B.branches[1] 下 → chain = ["sel_d == 2'd0", "!sel_f"]

**为什么同时存在 condition_chain 和 select_group_id？**
- condition_chain 是"衍生数据"——从 SelectGroup 树推导出来。让 dataflow 图直接读，不需要递归遍历 SelectGroup 树。
- select_group_id 是"源数据"——让 control 图知道哪些边是互斥的，属于同一个 mux/case。

---

## 没有 else 的 if (无互斥)

```verilog
if (en) y <= a;
// 没有 else
```

只有一条边:
```python
TraceEdge(a→y, condition_chain=["en"], select_group_id="", select_branch=0)
```

select_group_id 为空 → control 图不画 mux 结构，只画简单条件:
```
en ──▶ y (a 驱动)
```

---

## select_group 存储位置

```python
class SignalGraph(networkx.DiGraph):
    select_groups: dict[str, SelectGroup] = {}  # id → SelectGroup
```

renderer 从 SignalGraph 一次性获取图和选择表:
```python
graph = tracer.build_graph()
edges = graph.edges()
select_groups = graph.select_groups

for edge in edges:
    if edge.select_group_id:
        group = select_groups[edge.select_group_id]
        # 渲染互斥结构
```

---

## 字段总结

TraceEdge 新增:
- `condition_chain: list[str]` — 条件累积链 (dataflow 控制虚线 + control 简单条件)
- `select_group_id: str` — 选择组 ID (control 图 mux/case 互斥渲染)
- `select_branch: int` — 分支序号

SignalGraph 新增属性:
- `select_groups: dict[str, SelectGroup]` — 选择组索引表

VizEdge 新增:
- `condition_chain: list[str]` — 透传
- `select_group_id: str` — 透传
- `select_branch: int` — 透传
