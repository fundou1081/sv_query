# sv_query - SystemVerilog 信号追踪查询引擎

**让验证工程师直接问"这个信号谁驱动的"，而不是去读代码。**

---

## 🚀 5 分钟快速上手

### 1. 安装

```bash
pip install -e .
```

### 2. 准备一个 SV 文件

```systemverilog
// top.sv
module top(input clk, rst_n, input [7:0] data, output [7:0] result);
    logic [7:0] temp;
    always_ff @(posedge clk) begin
        if (!rst_n)
            temp <= 8'h0;
        else
            temp <= data;
    end
    assign result = temp;
endmodule
```

### 3. 查询信号驱动

```bash
sv_query trace-driver top.result --files top.sv
```

**输出示例：**

```
=== Drivers for top.result ===
Source Signal | Condition | Source File
--------------+-----------+------------
top.temp | Always | top.sv:8
        ↓ (via always_ff)
top.clk | Rising Edge | top.sv:1
top.rst_n | Active Low | top.sv:1

Confidence: Certain
```

---

## 用户场景

你是验证工程师，带着问题来，不是来学习架构的。

### 🔍 场景 1：我找不到这个信号是谁驱动的

```bash
sv_query trace-driver top.result --files "**/*.sv"
```

### 📦 场景 2：我改了这个信号，会影响下游哪些逻辑？

```bash
sv_query trace-load top.data --files "**/*.sv"
```

### 🛤️ 场景 3：这个数据从 A 到 B 经过哪些路径？

```bash
sv_query find-path --from top.data_in --to top.fifo.wr_data --files "**/*.sv"
```

输出示例：

```
=== Dataflow Path ===
1. top.data_in [always_comb] → @ adapter.sv:20
 └─> 2. top.adapter.data_out [assign] → @ adapter.sv:15
      └─> 3. top.fifo.wr_data [assign] → @ fifo.sv:8

Path Length: 3 hops
Confidence: Certain
```

### 🎯 场景 4：这个约束到底调用了哪个父类约束？

```bash
sv_query trace-constraint transaction::c_data --files "**/*.sv"
```

### 🐛 场景 5：RTL 信号报错，快速定位影响范围

RTL 仿真失败，定位到 `data_reg` 信号行为异常。需要快速回答：
- 哪些 input port 影响它？
- 它影响哪些 output port？

```python
from sv_query import trace_signal_debug

result = trace_signal_debug(graph, 'pipeline.data_reg')
print(f"影响它的 input port: {result['affecting_ports']}")
print(f"它影响的 output port: {result['affected_ports']}")
# 影响它的 input port: ['pipeline.data_in', 'pipeline.en']
# 它影响的 output port: ['pipeline.data_out']
```

支持多跳追踪：`a → b → c → d`，追踪 `c` 能找到 `a` 和 `d`。

### 🔗 场景 6：约束的条件变量，自动转为 Coverage Cross

约束中 `if (mode == 0) { addr < 100; }`，`mode` 是条件变量，
应该和 `addr` 做 cross coverage，但手写容易遗漏。

```python
from sv_query import extract_true_conditions, conditions_to_coverage_suggestions

conditions = extract_true_conditions(graph, 'packet.addr')
# → [{"condition_vars": ["packet.mode"], "branch": "consequent"}]

suggestions = conditions_to_coverage_suggestions(conditions, 'addr')
# → [{"type": "cross", "suggested_bins": "cross addr, mode"}]
```

支持：if/else、嵌套 if、implication（`->`）。

### 📊 场景 7：RTL 层次自动生成 Coverage 建议

给定 RTL 模块，自动识别 control/data 信号，生成 coverage bins 建议：

```python
from sv_query import generate_coverage_report

report = generate_coverage_report(graph)

print("Control Path:")  
for cp in report['control_path']:
    print(f"  {cp['signal']}: {[b['name'] for b in cp['bins']]}")
# valid: [valid_idle, valid_active]
# ready: [ready_idle, ready_active]

print("Data Path:")
for dp in report['data_path']:
    print(f"  {dp['signal']}: {[b['name'] for b in dp['bins']]}")
# data_in: [data_in_zero, data_in_low, data_in_mid, data_in_max]
```

### 🔍 场景 8：Covergroup ↔ Constraint 一致性检查

covergroup 的 bins 是否覆盖了 constraint 的合法空间？
条件约束是否有对应的 illegal_bins？

```python
from sv_query import CovergroupAnalyzer

analyzer = CovergroupAnalyzer(graph, covergroups)
gaps = analyzer.analyze()

for gap in gaps:
    print(f"[{gap.kind}] {gap.description}")
# [missing_cross] 条件约束引用了 mode 和 addr，但 covergroup 缺少 cross
# [missing_illegal_bins] 条件约束 + cross 存在但缺少 illegal_bins
```

### 🏗️ 场景 9：UVM Testbench 静态结构提取

从 UVM 验证环境源码中提取组件层次、TLM 连接、factory override：

```python
from sv_query import UVMTestbenchExtractor

extractor = UVMTestbenchExtractor({'my_env.sv': source})
tb = extractor.extract()

# 组件层次
for name, comp in tb.components.items():
    print(f"  {name}: {comp.class_name} (parent={comp.parent})")

# TLM 连接
for conn in tb.connections:
    print(f"  {conn.source_port} → {conn.target_port}")

# 输出 DOT 图
print(tb.to_dot())
```

已通过 OpenTitan 10 个模块实测验证（lc_ctrl、dma、i2c 等）。

---

## 核心优势

### 🔬 底层使用 pyslang，数据可信

`sv_query` 基于 [pyslang](https://github.com/MikePopoloski/pyslang)（业界标准的 SystemVerilog 解析器）构建 AST，保证分析结果的可信度：

- **语义优先于语法**：使用 `Compilation.getRoot()` 获取语义 AST，而非原始语法树
- **精确的硬件语义理解**：区分 `always_ff`、`always_comb`、`assign` 的赋值语义
- **条件上下文保留**：完整提取 if/case/三元运算符的条件分支

### 🎯 位精确追踪

```systemverilog
assign y[7:4] = a;
assign y[3:0] = b;
// y[7:4] 和 y[3:0] 是不同的驱动节点，不会混淆
```

### 🔗 完整数据流路径

追踪信号从 A 到 B 的完整路径，支持：
- 多路径分支
- 条件判断提取
- 时钟域分析

---

## CLI 命令参考

### controlflow - 控制流分析

分析信号的条件驱动逻辑，显示所有条件分支路径。

```bash
# 分析信号的条件驱动
python run_cli.py controlflow analyze demo.out -f demo.sv
```

**输出示例：**

```
ControlFlow Analysis: demo.out

  Conditional Drivers:
    when sel == 2'b00: demo.a → demo.out

  Conditional Drivers:
    when sel == 2'b01: demo.b → demo.out

  Conditional Drivers:
    when sel == 2'b10: demo.c → demo.out

  Conditional Drivers:
    when default: demo.d → demo.out
```

对应的 SystemVerilog 代码：

```systemverilog
module demo(input logic [1:0] sel, input [7:0] a, b, c, d, output [7:0] out);
    always_comb begin
        case (sel)
            2'b00: out = a;
            2'b01: out = b;
            2'b10: out = c;
            default: out = d;
        endcase
    end
endmodule
```

### dataflow - 数据流路径分析

分析信号从源到目标的完整数据流路径。

```bash
# 分析数据流路径
python run_cli.py dataflow analyze dataflow_demo.data_in dataflow_demo.data_out -f demo.sv
```

**输出示例：**

```
DataFlow: dataflow_demo.data_in → dataflow_demo.data_out
  Reachable: True
  Paths: 1
  Clock Domain: clk
  Timing Risk: safe
  Intermediate Signals (2):
    - dataflow_demo.stage1
    - dataflow_demo.stage2

  Path Details:

    Path 0: distance=3 [conditional]
      dataflow_demo.data_in → dataflow_demo.stage1
        driver: data_in
        condition: !!rst_n && enable
        timing: clk
        assign: nonblocking
      dataflow_demo.stage1 → dataflow_demo.stage2
        driver: stage1
        condition: !!rst_n
        timing: clk
        assign: nonblocking
      dataflow_demo.stage2 → dataflow_demo.data_out
        driver: stage2
        timing: (none)
        assign: continuous
```

对应的 SystemVerilog 代码：

```systemverilog
module dataflow_demo(input clk, rst_n, enable, input [7:0] data_in, output [7:0] data_out);
    logic [7:0] stage1, stage2;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) stage1 <= 8'h00;
        else if (enable) stage1 <= data_in;
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) stage2 <= 8'h00;
        else stage2 <= stage1 + 8'h01;
    end

    assign data_out = stage2;
endmodule
```

| 命令 | 说明 |
|------|------|
| `sv_query trace-driver <signal>` | 查询信号的驱动源 |
| `sv_query trace-load <signal>` | 查询信号的所有负载 |
| `sv_query find-path --from <A> --to <B>` | 查询 A 到 B 的数据流路径 |
| `sv_query trace-constraint <class>::<constraint>` | 查询约束的父类调用链 |
| `sv_query controlflow analyze <signal>` | 分析信号的条件驱动逻辑 |
| `sv_query dataflow analyze <from> <to>` | 分析 A 到 B 的数据流路径 |

### 全局参数

| 参数 | 说明 |
|------|------|
| `--files` | SV 文件列表或 glob 模式 |
| `--format json` | JSON 格式输出（默认是表格） |
| `--verbose` | 显示详细分析过程 |

---

## Python API

```python
from sv_query import SVQuery

# 初始化项目
proj = SVQuery.from_files(["top.sv", "tb.sv"])

# 查询驱动
drivers = proj.get_drivers("top.result")
for d in drivers:
    print(f"{d.source_signal} → condition: {d.condition}")

# 查询负载
loads = proj.get_loads("top.data")

# 查询路径
paths = proj.find_path("top.data_in", "top.fifo.wr_data")
```

返回的 `DriverInfo` 对象是干净的业务数据，已过滤：
- 字面量常量（`1'b0`、`4'hF`）单独归类
- 位选拼接的中间边已合并

---

## 支持的 SV 特性

### ✅ 完全支持

| 特性 | 说明 |
|------|------|
| `assign` 连续赋值 | 组合逻辑驱动 |
| `always_ff` | 时序逻辑，含时钟和复位 |
| `always_comb` | 组合逻辑，含 case/if 条件 |
| `always_latch` | 锁存逻辑 |
| 位选 `data[7:4]` | 精确位范围追踪 |
| 位拼接 `{a, b}` | 自动展开为多条边 |
| Port/Interface 连接 | 实例化信号连接 |
| Class OOP | 继承、约束、虚函数、实例化、成员访问、组合关系、约束继承传播 |
| **函数/任务内联展开** | if/else/case/return/三元运算符展开 |
| **约束详情查询** | 条件链追踪、if/else 上下文、foreach/solve before |

### ⚠️ 部分支持

| 特性 | 说明 |
|------|------|
| 拼接运算 `{...}` | 可能存在冗余边 |
| Struct 成员 | 整体赋值展开为成员赋值 |

### ❌ 暂不支持

| 特性 | 替代方案 |
|------|----------|
| 复杂宏替换 | 预处理后分析 |
| `bind` 语句 | 计划中 |
| Graphviz 可视化导出 | 计划中 |
| Package 多文件支持 | 计划中 |

---

## 输出格式

### 表格输出（默认）

```
=== Drivers for top.result ===
Source Signal | Condition | Confidence
--------------+-----------+----------
top.temp | Always | Certain
top.clk | Rising Edge | Certain
```

### JSON 输出（程序调用）

```bash
sv_query trace-driver top.result --format json
```

```json
{
  "signal": "top.result",
  "drivers": [
    {
      "source_signal": "top.temp",
      "condition": "Always",
      "clock_domain": "clk",
      "confidence": "certain",
      "source_location": "top.sv:8"
    }
  ]
}
```

---

## 项目结构

```
sv_query/
├── src/trace/
│   ├── unified_tracer.py     # 统一入口
│   ├── core/
│   │   ├── graph_builder.py  # 信号图构建
│   │   ├── dataflow.py       # 数据流路径分析
│   │   ├── controlflow.py    # 控制流条件分析
│   │   ├── base.py           # pyslang 封装
│   │   ├── class_graph_builder.py  # Class OOP 图构建
│   │   ├── class_hierarchy.py      # 继承链管理
│   │   └── builder/
│   │       ├── subroutine_expander.py  # 函数/任务内联展开
│   │       └── expression_builder.py   # 表达式构建
│   └── visitors/
│       ├── signal_expression_visitor.py  # 表达式解析
│       ├── statement_collector_visitor.py # 语句收集
│       └── constraint_visitor.py         # 约束表达式解析
├── sim/tests/                # 968 个测试
└── docs/                     # 详细设计文档
```

---

## 参与贡献

1. Fork 并克隆仓库
2. 安装开发依赖：`pip install -e ".[dev]"`
3. 运行测试：`pytest sim/tests/ -v`
4. 提交前确保所有测试通过

---

## 许可

MIT License