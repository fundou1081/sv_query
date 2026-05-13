# sv_query - SystemVerilog 信号追踪查询引擎

**Version**: 0.1.0  
**Status**: Active Development  
**License**: MIT  
**Maintainer**: The sv_query team

---

## 项目简介

`sv_query` 是一个基于 **pyslang AST** 的 SystemVerilog 信号追踪查询引擎，旨在为 IC 验证工程师提供精确、可靠的硬件信号分析和可视化能力。

### 核心能力

- **Driver 追踪**：从任意信号出发，追踪其所有驱动源（连续赋值、时序逻辑、组合逻辑）
- **Load 追踪**：从信号出发，追踪其所有负载（被驱动的信号）
- **位选追踪**：精确追踪 `data[7:4]` 等位选择信号的父子关系和位范围
- **Class OOP 支持**：支持 SystemVerilog 面向对象编程的类、继承、组合、约束追踪
- **Constraint 追踪**：支持随机约束的解析、SUPER_CALL 边追踪、约束覆盖分析

### 技术栈

| 组件 | 技术 |
|------|------|
| AST 解析 | [pyslang](https://github.com/MikePopoloski/pyslang) |
| 图结构 | NetworkX |
| 验证工具 | Verilator, Verible |
| 测试框架 | pytest |

---

## 开发背景

### 问题

在 IC 验证环境中，经常需要回答以下问题：
- `top.u_cpu.data_out[31:16]` 信号由什么驱动？
- `tb.dut.u_axi.write_enable` 的时钟域是什么？
- `transaction.c1` 约束调用了父类的哪个约束？
- `outer.my_inner.status` 信号的完整路径是什么？

传统方法依赖：
- 人工阅读源码
- grep/sed 等文本工具（无法处理嵌套、宏、位选）
- 商业可视化工具（昂贵、不可扩展）

### 解决方案

`sv_query` 通过 pyslang 精确解析 SystemVerilog AST，构建信号图，实现：
- **AST 唯一数据源**：所有分析基于语法树，不依赖字符串解析
- **位精确性**：保留 `data[7:4]` 和 `data[3:0]` 的完整区分
- **语义完整性**：理解 always_ff、assign、constraint 等语义上下文

---

## 架构设计

### 核心组件

```
src/trace/
├── unified_tracer.py        # 统一入口，协调各组件
├── core/
│   ├── graph_builder.py      # 模块/信号图构建 (DriverExtractor, LoadExtractor)
│   ├── graph_models.py       # 数据模型 (TraceNode, TraceEdge, EdgeKind)
│   ├── base.py               # PyslangAdapter - AST 操作封装
│   ├── class_graph_builder.py # Class OOP 图构建 (约束、继承、组合)
│   ├── bit_select_handler.py  # 位选节点处理 (追踪父子关系)
│   └── query_*.py            # 查询接口 (signal, load, clock_domain, module)
└── visitors/
    └── constraint_visitor.py # 约束表达式解析器
```

### 数据流

```
SV Source Files
       ↓
  pyslang Parser
       ↓
  SyntaxTree (AST)
       ↓
  ┌─────────────────────────────────────┐
  │           UnifiedTracer             │
  │  ┌──────────────────────────────┐   │
  │  │       GraphBuilder           │   │
  │  │  - DriverExtractor           │   │
  │  │  - LoadExtractor             │   │
  │  │  - ConnectionExtractor       │   │
  │  └──────────────────────────────┘   │
  │  ┌──────────────────────────────┐   │
  │  │     BitSelectHandler          │   │
  │  │  - signal_widths extraction   │   │
  │  │  - bit range tracking        │   │
  │  └──────────────────────────────┘   │
  │  ┌──────────────────────────────┐   │
  │  │    ClassGraphBuilder          │   │
  │  │  - constraint parsing        │   │
  │  │  - inheritance (extends)     │   │
  │  │  - composition (has-a)      │   │
  │  └──────────────────────────────┘   │
  └─────────────────────────────────────┘
       ↓
   SignalGraph (NetworkX)
       ↓
  Query APIs (SignalTracer, LoadTracer, ...)
```

### 关键设计原则

| 铁律 | 说明 |
|------|------|
| AST唯一数据源 | 所有分析基于 pyslang AST，禁止字符串正则解析源码 |
| 位精确性 | `data[7:4]` 和 `data[3:0]` 是不同的硬件信号 |
| 原子化 | 每个语法节点类型对应独立的解析器/collector |
| 不可信则不输出 | 无法解析时返回 `confidence: "uncertain"` |

---

## 已实现功能

### 模块级追踪

- [x] Port 声明解析 (`input [7:0] d`)
- [x] 连续赋值 (`assign a = b`)
- [x] always_ff/always_comb/always_latch 块
- [x] 实例化连接 (`u_inst.port`)
- [x] 时钟域识别

### 位选追踪

- [x] 位选节点创建 (`data[3:0]` → node)
- [x] 父子关系建立 (`data[3:0]` → `data`)
- [x] BIT_SELECT 边
- [x] bit_range 属性 (`"[3:0]"`)
- [x] parent_bit_start/end (`0`, `3`)
- [x] Port/Internal Signal 位宽提取

### Class OOP 支持

| 功能 | 状态 |
|------|------|
| Class 节点 | ✅ |
| ClassPropertyDeclaration | ✅ |
| extends 继承关系 | ✅ |
| IS_INSTANCE_OF 边 (组合) | ✅ |
| Constraint 解析 | ✅ |
| SUPER_CALL 边 | ✅ |
| Constraint 覆盖 (augmentation/replacement) | ✅ |
| Virtual function/task 检测 | ✅ |

### Constraint 追踪

- [x] ExpressionConstraint 解析
- [x] ConditionalConstraint (if/else)
- [x] ImplicationConstraint (`a -> b`)
- [x] UniquenessConstraint (`unique {a, b}`)
- [x] SolveBeforeConstraint
- [x] ForeachConstraint
- [x] 多语句 block 展开
- [x] Variable 提取

---

## 开发进度

### 2026-05-12 更新

**Bit Select Handler**
- 新增 `_scan_constraint_bit_selects()` 支持约束中的位选追踪
- 支持 `constraint c1 { data[7:4] == 4'hF; }` 中的位选解析

**Class OOP 扩展**
- IS_INSTANCE_OF 边支持组合关系
- SUPER_CALL 边支持约束增量扩展
- 多层继承场景验证

### 提交记录 (17 commits ahead of main)

```
4f3c4fd feat(bit_select): support constraint bit select tracking
34f66ba feat(bit_select): add BitSelectHandler for bit range tracking
7022bfd docs: update DEVELOPMENT.md with new features
8b64ff9 test: add complex inheritance gold standard test
9fc1b3c fix(test): remove invalid syntax test
fb2fb6b feat(constraint): support SUPER_CALL edge
19c6da8 test(composition): add 13 complex test cases
dd33c14 feat(composition): support IS_INSTANCE_OF edge
...
```

---

## 长期计划

### Phase 1: 基础功能 ✅

- [x] 模块级信号追踪 (Driver/Load)
- [x] Port/Internal Signal 位宽
- [x] always_ff/always_comb/always_latch

### Phase 2: Class OOP ✅

- [x] ClassDeclaration 节点
- [x] ConstraintDeclaration 解析
- [x] extends 继承关系
- [x] has-a 组合关系 (IS_INSTANCE_OF)
- [x] SUPER_CALL 约束调用

### Phase 3: 高级追踪

- [ ] Generate block 追踪
- [ ] Function/Task 内联展开
- [ ] Interface/modport 追踪
- [ ] 跨时钟域路径分析

### Phase 4: 可视化 & CI

- [ ] Graphviz 可视化导出
- [ ] HTML 报告生成
- [ ] GitHub Actions CI
- [ ] 覆盖率分析集成

---

## 测试框架

### 测试结构

```
sim/
├── tests/
│   ├── unit/           # 单元测试 (graph_models, base, etc.)
│   ├── integration/    # 集成测试 (模块、类、约束)
│   └── regression/     # 回归测试 (边界条件、复杂场景)
├── TEST_REPORT.md      # 测试报告
└── conftest.py         # pytest 配置
```

### 测试统计

```
Unit tests:      30 tests
Integration:    111 tests
Regression:     528 tests
─────────────────────────
Total:          669 tests (all passing)
```

### 验证工具

| 工具 | 版本 | 用途 |
|------|------|------|
| Verilator | 5.048 | SV 语法验证 |
| Verible | v0.0-4053 | SV 语法验证 (双重验证) |

所有 RTL 测试通过 Verilator + Verible 双重验证。

---

## 使用示例

### 1. 基础信号追踪

```python
import pyslang
from trace.unified_tracer import UnifiedTracer

source = '''
module top;
    logic [7:0] data;
    logic [3:0] slice;
    assign slice = data[3:0];
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

# 查询 data[3:0] 的父节点
data_slice = graph.get_node('top.data[3:0]')
print(f"bit_range: {data_slice.bit_range}")      # "[3:0]"
print(f"parent: {data_slice.parent}")            # "top.data"
print(f"parent_bit_start: {data_slice.parent_bit_start}")  # 0
print(f"parent_bit_end: {data_slice.parent_bit_end}")      # 3

# 查询 drivers
drivers = graph.find_drivers('top.slice')
for d in drivers:
    print(f"Driver: {d.id}")  # "top.data[3:0]"
```

### 2. 跨模块实例追踪 (MIG)

```python
import pyslang
from trace.unified_tracer import UnifiedTracer

source = '''
module child(output [7:0] out);
endmodule

module parent;
    wire [7:0] w;
    child u_child(.out(w));
endmodule

module top;
    parent u_parent();
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
mig = tracer._module_graph

# 获取实例节点 (集中索引)
inst = mig.get_instance('top.u_parent')
print(f"id: {inst.id}")          # "top.u_parent"
print(f"module_type: {inst.module_type}")  # "parent"
print(f"parent: {inst.parent}")  # "top"

# 父子关系查询
children = mig.get_child_instances('top')
print(f"top's children: {[c.id for c in children]}")  # ["top.u_parent"]

# 获取所有实例
all_insts = mig.get_all_instances()  # ["top.u_parent", "top.u_parent.u_child"]

# 层级遍历
def print_hierarchy(parent_id, indent=0):
    for child in mig.get_child_instances(parent_id):
        print("  " * indent + f"{child.id} ({child.module_type})")
        print_hierarchy(child.id, indent + 1)

print_hierarchy('top')
# Output:
#   top.u_parent (parent)
#     top.u_parent.u_child (child)
```

**MIG 核心 API**：

| API | 说明 |
|-----|------|
| `mig.get_instance(path)` | 获取实例节点 (`ModuleInstanceNode`) |
| `mig.get_child_instances(parent_id)` | 获取子实例列表 |
| `mig.get_all_instances()` | 获取所有实例 ID |
| `node.ports[port_name]` | 获取端口信息 (`PortInfo`) |
| `mig.get_internal_signal(port_path)` | 端口→内部信号 |

### 3. 跨模块 Driver/Load 追踪

```python
import pyslang
from trace.unified_tracer import UnifiedTracer

# 跨模块 driver 链: clk_gen.clk → top.u_gen.clk → top.clk → top.u_driver.clk → driver.clk
source = '''
module clk_gen(output logic clk);
    assign clk = 1'b0;
endmodule

module driver(input logic clk, output logic [7:0] data);
    always_comb data = 8'hA5;
endmodule

module load(input logic [7:0] data);
    logic [7:0] reg_data;
    logic clk;
    always_ff @(posedge clk) reg_data <= data;
endmodule

module top;
    logic clk;
    logic [7:0] data;
    
    clk_gen u_gen(.clk(clk));
    driver u_driver(.clk(clk), .data(data));
    load u_load(.data(data));
endmodule
'''

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

# 追踪 top.data 的 driver
print("=== Drivers of top.data ===")
drivers = graph.find_drivers('top.data')
for d in drivers:
    print(f"  {d.id}")  # top.u_driver.data

# 追踪 top.clk 的 driver 链
print("\n=== Drivers of top.clk ===")
drivers = graph.find_drivers('top.clk')
for d in drivers:
    print(f"  {d.id}")  # top.u_gen.clk

# 追踪 top.u_driver.clk 的 driver (跨模块边界)
print("\n=== Drivers of top.u_driver.clk ===")
drivers = graph.find_drivers('top.u_driver.clk')
for d in drivers:
    print(f"  {d.id}")  # driver.clk

# 追踪 load 的 loads
print("\n=== Loads of top.clk ===")
loads = graph.find_loads('top.clk')
for l in loads:
    print(f"  {l.id}")  # top.u_driver.clk

# 查看跨越模块边界的边
print("\n=== Cross-module edges ===")
for src, dst in graph.edges():
    edge = graph.get_edge(src, dst)
    # DRIVER 边跨越模块边界: 内部信号 → 实例端口 或 实例端口 → 实例端口
    if edge.kind.name == 'DRIVER' and ('.' in src and '.' in dst):
        src_parts = src.split('.')
        dst_parts = dst.split('.')
        # 内部信号到实例端口的跨越
        if len(src_parts) == 2 and len(dst_parts) >= 3:
            print(f"  {src} --DRIVER--> {dst} (internal → instance port)")
        # 实例端口到实例端口的跨越
        elif len(src_parts) >= 3 and len(dst_parts) >= 3 and src_parts[0] != dst_parts[0]:
            print(f"  {src} --DRIVER--> {dst} (instance port → instance port)")
```

**跨模块 Driver/Load 追踪要点**：
- 实例端口节点：`top.u_driver.clk` (顶层路径 + 实例名 + 端口名)
- 模块内部信号：`driver.clk` (模块名 + 端口名)
- DRIVER 边跨越模块边界：
  - `driver.data --DRIVER--> top.u_driver.data` (内部信号 → 实例端口)
  - `clk_gen.clk --DRIVER--> top.u_gen.clk` (内部信号 → 实例端口)
- CONNECTION 边表示信号连接：`top.clk --CONNECTION--> top.u_driver.clk`
- 使用 `graph.find_drivers(signal_id)` 追踪驱动源
- 使用 `graph.find_loads(signal_id)` 追踪负载

---

## 设计文档

| 文档 | 说明 |
|------|------|
| `DEVELOPMENT.md` | 开发规范、铁律、测试要求 |
| `DESIGN_composition_chain.md` | 组合链 (has-a) 设计方案 |
| `EXAMPLES.md` | 完整使用示例 (8 个场景 + MIG 高级 API) |
| `docs/code_framework_analysis.md` | 模块实例图架构分析 |
| `docs/CONNECTION_vs_MIG_analysis.md` | ConnectionExtractor vs MIG 对比分析 |

---

## 参与贡献

1. Fork 项目
2. 创建 Feature Branch (`git checkout -b feature/xxx`)
3. 遵循铁律开发 (见 DEVELOPMENT.md)
4. 添加测试 (金标准测试 + 负面测试)
5. 验证 (Verilator + Verible + pytest)
6. 提交 Pull Request

---

## 联系方式

- 维护者: The sv_query team
- GitHub: https://github.com/fundou1081/sv_query