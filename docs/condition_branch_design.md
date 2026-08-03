# ConditionBranch — 条件分支数据层设计

## 核心思想

`condition_chain` 是 TraceEdge 上的一个 `list[str]` 字段，携带嵌套条件累积 AND 语义。

**不需要显式的 `select_group_id`**。互斥关系从 `condition_chain` 自动推导：
- 按 `(dst, chain[:-1])` 分组
- 每组 ≥ 2 条边 → 互斥组（mux / case / if-else）
- 单独 1 条边 → 简单条件（偏 if）

---

## 数据结构

```python
@dataclass  
class TraceEdge:
    # ... 现有 17 个字段不变 ...
    
    # [V7.0 NEW] 嵌套条件累积链
    # 例: ["sel_d == 2'd0", "sel_e == 2'd0"]
    # 渲染时 " && ".join(chain) → 标签
    condition_chain: list[str] = []
```

只改 TraceEdge，不改其他任何类。不需要 SelectGroup、不需要 ConditionBranch 类，不需要显式 group_id。

---

## 互斥分组算法

```python
def group_edges(dst_to_edges: dict[str, list]) -> list:
    """自动检测互斥关系。
    
    对于所有边，按 (dst, chain[:-1]前缀) 分组。
    每组 >= 2 条边 → 互斥组 → control 图渲染为 mux/case 菱形节点。
    单条边 → 简单条件 → control 图渲染为简单条件标注。
    """
    result = []
    for dst, edges in dst_to_edges.items():
        by_prefix = {}
        for e in edges:
            chain = e.condition_chain
            prefix = tuple(chain[:-1]) if len(chain) > 1 else ()
            by_prefix.setdefault(prefix, []).append(e)
        
        for prefix, group in by_prefix.items():
            result.append({
                "dst": dst,
                "parent": list(prefix),  # 外层条件（嵌套时）
                "branches": group,       # ≥2 → mux, ==1 → simple
                "is_mux": len(group) >= 2
            })
    return result
```

## 算法工作原理

| 场景 | edges | 分组 key | 结果 |
|------|-------|----------|------|
| `sel ? a : b` → y | a→y["sel"], b→y["!sel"] | `(y, ())` → 2条 | mux |
| `if(en) y<=a; else y<=b` | a→y["en"], b→y["!en"] | `(y, ())` → 2条 | mux |
| `if(en) y<=a;` (无else) | a→y["en"] | `(y, ())` → 1条 | simple |
| `case(sel_b) { d0:a, d1:b, def:c }` | a→y, b→y, c→y | `(y, ())` → 3条 | case |
| `case(d){ d0:if(e)y<=a; }` (嵌套) | a→y["d0","e"] | `(y, ("d0",))` → 1条 | simple |

---

## 各场景详解

### 1. 三目运算符

```verilog
assign y = sel ? a : b;
```

```python
TraceEdge(a→y, condition_chain=["sel"])
TraceEdge(b→y, condition_chain=["!sel"])
```

group → mux, 渲染为双分支选择:
```
      ┌── sel ──▶ a ──┐
sel ──┤                ├──▶ y
      └── !sel ──▶ b ──┘
```

### 2. if/else

```verilog
if (en) y <= a;
else    y <= b;
```

```python
TraceEdge(a→y, condition_chain=["en"])
TraceEdge(b→y, condition_chain=["!en"])
```

渲染同上。

### 3. case

```verilog
case (sel_b)
  2'd0:    y <= a;
  2'd1:    y <= b;
  default: y <= c;
endcase
```

```python
TraceEdge(a→y, condition_chain=["sel_b == 2'd0"])
TraceEdge(b→y, condition_chain=["sel_b == 2'd1"])
TraceEdge(c→y, condition_chain=["default"])  # default分支
```

渲染为多分支菱形:
```
         ┌── 2'd0 ──▶ a ──┐
         ├── 2'd1 ──▶ b ──┤
sel_b ───┤                 ├──▶ y
         └── default ──▶ c ─┘
```

### 4. 偏 if（无 else）

```verilog
if (en) y <= a;
// 无 else 分支
```

```python
TraceEdge(a→y, condition_chain=["en"])
# 按 (y, ()) 分组 → 1 条边 → simple
```

渲染为简单条件节点 → 目标:
```
en ──▶ y (a 驱动)
```

### 5. 嵌套选择

```verilog
case (sel_d)
  2'd0: y <= (sel_f ? a : b);
  2'd1: y <= (sel_f ? c : d);
endcase
```

```python
TraceEdge(a→y, condition_chain=["sel_d == 2'd0", "sel_f"])
TraceEdge(b→y, condition_chain=["sel_d == 2'd0", "!sel_f"])
TraceEdge(c→y, condition_chain=["sel_d == 2'd1", "sel_f"])
TraceEdge(d→y, condition_chain=["sel_d == 2'd1", "!sel_f"])
```

group 结果:
```
key=(y, ("sel_d==0",)) → [a→y, b→y] → mux (内层 sel_f)
key=(y, ("sel_d==1",)) → [c→y, d→y] → mux (内层 sel_f)
外层的 sel_d case 由两个 mux 组的 parent 推导
```

渲染为嵌套 mux:
```
         ┌── sel_f ──▶ a ──┐
sel_d=0 ─┤                 ├──▶ y
         ├── !sel_f ──▶ b ──┤
         │                   │
sel_d=1 ─┤                   │
         ├── sel_f ──▶ c ──┤
         └── !sel_f ──▶ d ──┘
```

---

## 5 张图如何消费

| 图 | 读取方式 |
|------|----------|
| **signal** | 忽略 condition_chain |
| **dataflow** | `condition_chain` → 控制虚线标注 |
| **structure** | 忽略 |
| **control** | 自动分组 (dst + 前缀) → 互斥 mux / case / 简单条件 |
| **pipeline** | `stage_id` / `cycle` 区分时序边 |

---

## 实施改动

只动 4 个位置:

| 文件 | 改动 |
|------|------|
| `graph/models.py` | TraceEdge 加 `condition_chain: list[str]` |
| `driver_extractor.py` | `_flatten_conditional`: cond_stack 列表写入 field（保留拆分逻辑而非 join 为字符串） |
| `viz_data_models.py` | VizEdge 加 `condition_chain: list[str]` |
| `viz_data_builder.py` | 透传字段 |
