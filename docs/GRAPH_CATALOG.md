# sv_query 图谱总览

> 创建时间: 2026-05-29
> 状态: 活跃维护

---

## 核心思想

sv_query 的本质是**用图描述硬件设计中的各种关系**，然后在图上回答验证工程师的问题。

每种图解决一类基本问题：

---

## 1. SignalGraph（信号图）

**解决的基本问题**：信号之间的驱动/负载关系是什么？

```
信号 A → 信号 B → 信号 C
(driver)  (load)
```

| 查询 | 回答 |
|------|------|
| 这个信号谁驱动的？ | fanin 追踪 |
| 这个信号影响谁？ | fanout 追踪 |
| A 到 B 的数据流路径？ | path finding |
| 信号属于哪个时钟域？ | clock domain |
| 跨模块的信号连接？ | cross-module tracking |

**数据源**：RTL 源码（assign, always_ff, always_comb, port 连接）

---

## 2. ClassGraph（Class 约束图）

**解决的基本问题**：Class 的变量、约束、继承关系是什么？

```
Class A extends B
  ├── 变量: addr, data
  ├── 约束: c_addr { addr < 100; }
  └── 继承: B 的变量和约束
```

| 查询 | 回答 |
|------|------|
| 这个变量在哪些约束中？ | Q1: variable → constraints |
| 这个约束影响哪些变量？ | Q2: constraint → variables |
| 两个变量有共同约束吗？ | Q3: variable ↔ variable |
| 约束的条件链是什么？ | condition chain |

**数据源**：Class 定义（constraint, rand, extends）

---

## 3. CovergroupGraph（覆盖率图）

**解决的基本问题**：Covergroup 的 bins 是否覆盖了 constraint 的合法空间？

```
constraint: addr < 200
coverpoint: bins low={[0:99]}, high={[100:255]}
                ↑ 有覆盖          ↑ 超出约束范围
```

| 查询 | 回答 |
|------|------|
| bins 覆盖了 constraint 的多少？ | coverage gap |
| 有 illegal_bins 吗？ | missing illegal bins |
| 条件变量有 cross 吗？ | missing cross |
| data 信号的 bins 合理吗？ | bins 质量检查 |

**数据源**：Covergroup 定义 + ClassGraph

---

## 4. CallGraph（调用图）

**解决的基本问题**：函数/任务的调用链是什么？哪里有 randomize？

```
body()
├── create("req")
├── start_item(req)
├── req.randomize()  ← [RANDOMIZE]
└── finish_item(req)
```

| 查询 | 回答 |
|------|------|
| 这个函数调用了什么？ | call chain |
| 哪里有 randomize？ | randomize 标记 |
| 这是 sequence 还是 driver？ | pattern 识别 |
| fork 有哪些并发分支？ | fork 分析 |

**数据源**：Class 中的 function/task 定义

---

## 5. UVMTestbenchGraph（UVM 结构图）

**解决的基本问题**：UVM 验证环境的组件层次和连接关系是什么？

```
my_test
└── my_env
    ├── my_agent
    │   ├── my_driver
    │   └── my_monitor
    └── my_scoreboard
```

| 查询 | 回答 |
|------|------|
| env 里有哪些组件？ | component hierarchy |
| monitor 连到了哪里？ | TLM connections |
| 用了哪个 sequence？ | sequence binding |
| factory override 了什么？ | overrides |

**数据源**：UVM 验证环境源码

---

## 6. SVA 图（待实现）

**解决的基本问题**：信号之间的时序关系是什么？SVA 是否覆盖？

```
sequence s1: a ##1 b
property p1: a |-> b
assert property (p1)
```

| 查询 | 回答 |
|------|------|
| 这个信号有哪些 assertion？ | signal → assertions |
| 这个 assertion 覆盖了哪些信号？ | assertion → signals |
| 信号对之间有时序关系吗？ | timing relationship |
| SVA 覆盖了所有关键信号对吗？ | coverage gap |

**数据源**：SVA (sequence/property/assert)

---

## 图之间的关系

```
RTL 源码 ──→ SignalGraph ──→ 信号驱动/负载关系
                ↓
Class 源码 ──→ ClassGraph ──→ 约束/变量/继承关系
                ↓
Covergroup ──→ CovergroupGraph ──→ bins 覆盖分析
                ↓
function/task ──→ CallGraph ──→ 调用链/randomize
                ↓
UVM 源码 ──→ UVMTestbenchGraph ──→ 组件层次/连接
                ↓
SVA ──→ SVA 图 ──→ 时序关系/assertion 覆盖（待实现）
```

**核心价值**：所有图共享同一个 pyslang 语义 AST，可以跨图查询。

例如：
- SignalGraph 告诉你 `data` 信号的 driver
- ClassGraph 告诉你 `data` 的约束
- CovergroupGraph 告诉你 `data` 的 coverage bins
- SVA 图告诉你 `data` 相关的 assertion

**一个问题，多图回答**："这个信号的行为是否被完整验证？"
