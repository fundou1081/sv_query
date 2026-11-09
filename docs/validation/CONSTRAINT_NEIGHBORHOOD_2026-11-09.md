# Constraint neighborhood（P132）

**日期**: 2026-11-09
**问题**: 一次查询跨多个 constraint block，找出某个 random 变量与其他变量的关系，
用于学习/诊断重要度，评估是否核心节点。
**结果**: 新增 `trace constraint-neighborhood`；synthetic chain + OpenTitan I2C 实测通过。

---

## 1. 命令

```bash
sv_query trace constraint-neighborhood <property> \
  --file/-f <file> 或 --filelist <f> \
  [--max-depth 6] [--max-nodes 200] [--json]
```

property 支持：

```text
class 类型级：rnd_item.b / i2c_item.rcont
实例级：top.e.p.addr（解析到类型级）
```

## 2. 算法

```text
root = resolve(property)
queue = [root]
while queue:
  current = pop
  for block in trace(current):
    members = block.vars + block.conditions
    for other in members:
      add co-constraint edge current-other (label block)
      if other not visited and depth <= max_depth:
        add node + parent path
compute:
  direct_degree, block_count, reachable_count, paths,
  relation list, degree_centrality
```

关键语义：

- 边是 **co-constraint**（同一 block 共同出现），不是精确表达式依赖；
- `if (c) d inside ...` 会把 `c` 和 `d` 连起来；
- 跨 block 通过共享变量传递（a-b-c-d）；
- 不是数据流 fanin，不进入 SignalGraph 边。

## 3. 输出 schema

```json
{
  "ok": true,
  "command": "trace_constraint_neighborhood",
  "result": {
    "root": "rnd_item.b",
    "nodes": [
      {"id": "rnd_item.b", "depth": 0, "blocks": [], "neighbors": [],
       "path": ["rnd_item.b"], "block_count": 2, "degree": 2}
    ],
    "relations": [
      {"source": "rnd_item.a", "target": "rnd_item.b",
       "blocks": ["rnd_item.c_ab"]}
    ],
    "paths": {"rnd_item.d": ["rnd_item.b", "rnd_item.c", "rnd_item.d"]},
    "summary": {
      "node_count": 4,
      "relation_count": 3,
      "direct_degree": 2,
      "reachable_count": 3,
      "max_depth": 2,
      "degree_centrality": 0.6667,
      "importance_metrics": {
        "block_count": 2,
        "direct_degree": 2,
        "reachable_count": 3,
        "degree_centrality": 0.6667
      }
    }
  }
}
```

## 4. 实测

### Synthetic chain

```text
constraint c_ab { a < b; }
constraint c_bc { b == c + 1; }
constraint c_cd { if (c > 0) d inside {[1:10]}; }
constraint c_de { e dist ...; }
```

从 `rnd_item.b` 一次查询：

```text
node_count=4
paths: b->a, b->c, b->c->d
direct_degree=2 (a,c)
block_count=2
```

从 `rnd_item.a`：

```text
a->b->c->d
direct_degree=1
```

这说明 `b`/`c` 比 `a`/`d` 更接近“核心节点”。

### OpenTitan I2C

`i2c_item.rcont`：

```text
nodes: rcont, read, stop
block: i2c_item.rcont_c
direct_degree=2
block_count=1
```

一次查询就能看到 `rcont` 与 `read`/`stop` 共同受约束。

## 5. 重要度指标

当前输出：

```text
block_count         直接涉及的 constraint block 数
direct_degree       直接 co-constraint 邻居数
reachable_count     可到达变量数
max_depth           BFS 最大深度
degree_centrality   direct_degree / (node_count-1)
```

用途：

- 同一 class 内相对比较；
- 判断某变量是否是约束图的“枢纽”；
- 辅助学习 constraint 结构；
- 不给出自动“核心/非核心”硬阈值。

## 6. 边界

- 边 = 同一 block 共同出现，**不是** solver 语义的因果/强度；
- 没有 distribution/solve-order 权重；
- 条件变量只按 block 共同出现建模；
- `max_depth`/`max_nodes` 截断时结果不完整；
- 依赖 class_graph 的约束提取，继承/嵌套约束可能不完整；
- 不是 coverage、不是 randomize 结果、不是仿真；
- 只能 CLI；尚未接入 constrained `svq_query` tool。

## 7. 测试

```text
test_constraint_neighborhood.py: 3 passed
synthetic chain + isolated var + not_found
OpenTitan I2C rcont manual smoke
```

## 8. 版本

post-freeze v0.4 实验；不属于 `v0.3.0-agent-query` tag。
