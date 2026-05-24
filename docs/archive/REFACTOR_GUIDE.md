# sv_query 重构指南

版本：1.4 日期：2024-05-18
基于：SLANG_API_EVALUATION.md 的评估结论

## 背景

sv_query 仅使用了 pyslang 三层结构中的 Layer 1（语法层 SyntaxTree），完全绕过了 Layer 2（语义层 Compilation/AST）和 Layer 3（数据流分析 AnalysisManager）。这导致了约 1500 行臃肿的手写 AST 遍历代码，参数化位宽无法正确赋值，字符串 kind 匹配在 pyslang 版本升级时频繁失效。

本文档提供一条可执行的重构路径。

## 核心原则

- 不重写，替换地基：669 个测试是资产。图模型（TraceNode/TraceEdge/NetworkX）保留，只替换数据来源层。
- 逐步迁移：每步完成运行回归测试，确认基线再继续。
- 测试失败优先看新 API：原测试的"金标准"是基于错误实现标定的，失败可能意味发现了原来的 bug。
- AST 用在正确的地方：Layer 3 负责数据流结构（驱动关系），AST 负责控制流上下文（guard 条件）；不用 AST 做 Layer 3 已经做好的事，也不期望 Layer 3 替代 AST 做条件提取。

## 架构原则：AST vs Layer 3 各司其职

重构的目标不是"消灭 AST 使用"，而是把 AST 用在正确的地方。重构前，sv_query 用 AST 做所有事（找信号、找驱动、找路径），但这些都是 Layer 2/3 已经做好的事。真正只有 AST 能做的是控制流条件提取。

| 层次 | 回答的问题 | sv_query 用途 |
|------|-----------|--------------|
| Layer 3 AnalysisManager | 谁驱动谁（数据结构、位范围、赋值类型） | 替换 DriverExtractor / LoadExtractor [Step 3] |
| Layer 2 AST（类型化节点） | 在什么条件下驱动（if/case/三元guard） | ConditionExtractor [Step 9] |
| Layer 1 SyntaxTree | 用 AST 做结构分析 | 重构后不再直接使用 |

两者互补，职责不重叠：
- `am.getDrivers(var)` → "top.src_a" 驱动 top.out，位范围 [7:0]（不含条件）
- `ConditionExtractor(proc)` → "top.src_a -> top.out" 成立当且仅当 sel=1（不含位范围）
- 合并后的 TraceEdge → src_a -> out，[7:0]，条件：sel=1

## 改造目标

**现状：**
```
SyntaxTree -> [1500 行手写遍历] -> SignalGraph（信号级，无位精度，无条件）
```

**改造后：**
```
SyntaxTree
↓
Compilation（elaboration，激发语义分析）
├─> AnalysisManager.getDrivers() → 驱动结构 + 位范围
└─> ProceduralBlock AST 遍历 → guard 条件
↓ 合并
[~400 行桥接代码] -> SignalGraph（位精确，条件感知）
```

---

## 第一步：建立正确的编译入口

**工作量：1 天 文件：新建 src/trace/core/compiler.py**

所有入口目前是：
```python
tree = pyslang.SyntaxTree.fromText(source)（只得到语法树，没有任何语义信息。）
```

新建统一编译入口：

```python
# src/trace/core/compiler.py
import sys
sys.path.insert(0, 'D:/Project_Dv_2026/slang-netlist/build/win-release/deps/slang-build/lib')
import pyslang
from pyslang.ast import Compilation
from pyslang.analysis import AnalysisManager

def compile_sv(sources: dict) -> tuple:
    """
    sources: {filename: sv_code_string}
    返回已 elaborated 的 Compilation 和分析好的 AnalysisManager
    """
    comp = Compilation()
    for fname, code in sources.items():
        tree = pyslang.SyntaxTree.fromText(code, fname)
        comp.addSyntaxTree(tree)

    # 触发 elaboration（必须）
    diags = comp.getSemanticDiagnostics()
    errors = [d for d in diags if d.isError()]
    if errors:
        report = pyslang.DiagnosticEngine.reportAll(comp.sourceManager, errors)
        raise ValueError(f"Compilation errors:\n{report}")

    am = AnalysisManager()
    am.analyze(comp)
    return comp, am
```

UnifiedTracer 改为：

```python
# src/trace/unified_tracer.py
from .core.compiler import compile_sv

class UnifiedTracer:
    def __init__(self, sources: dict):
        self.comp, self.am = compile_sv(sources)
        self.root = self.comp.getRoot()
```

---

## 第二步：用 root.visit() 替换所有手写遍历

**工作量：3 天 替换文件：graph_builder.py, base.py**

```python
from pyslang.ast import (
    SymbolKind, VariableSymbol, ProceduralBlockSymbol, InstanceSymbol, PortSymbol
)

class SymbolCollector:
    def collect(self, root):
        ports = []
        vars_ = []
        procs = []
        insts = []

        root.visit(lookup_table={
            SymbolKind.Port: ports.append,
            SymbolKind.Variable: vars_.append,
            SymbolKind.ProceduralBlock: procs.append,
            SymbolKind.Instance: insts.append,
        })
        return ports, vars_, procs, insts
```

控制遍历深度（需要跳过某些子树时）：

```python
root.visit(lookup_table={
    SymbolKind.Instance: lambda n: VisitAction.Skip if n.name == "u_blackbox" else None,
    SymbolKind.Variable: vars_.append,
})
```

---

## 第三步：用 AnalysisManager.getDrivers() 替换 DriverExtractor

**工作量：3 天 替换文件：graph_builder.py 的 DriverExtractor（约 400 行）**

```python
def build_driver_edges(root, am, result):
    variables = []
    root.visit(lookup_table={SymbolKind.Variable: variables.append})

    ec = EvalContext(root)

    for var in variables:
        drivers = am.getDrivers(var)
        if not drivers:
            continue

        dst_id = var.getHierarchicalPath()
        for d in drivers:
            lo, hi = d.bounds
            assign_type = "continuous" if "Continuous" in str(d.kind) else "nonblocking"
            src_path = d.path.toString(ec)

            result.edges.append(TraceEdge(
                src=src_path,
                dst=dst_id,
                kind=EdgeKind.DRIVER,
                assign_type=assign_type,
                bit_lo=lo,
                bit_hi=hi,
            ))
```

---

## 第四步：用语义 API 替换字符串解析

**工作量：2 天 替换文件：graph_builder.py, base.py**

端口方向：

```python
# 替换前
if "output" in direction.lower(): kind = NodeKind.PORT_OUT

# 替换后
from pyslang.ast import ArgumentDirection
for p in ports:
    if p.direction == ArgumentDirection.In:
        kind = NodeKind.PORT_IN
    elif p.direction == ArgumentDirection.Out:
        kind = NodeKind.PORT_OUT
    else:
        kind = NodeKind.PORT_INOUT
```

端口和信号位宽：

```python
# 替换前
port_width = self.fd_adapter.extract_port_width(port_decl, scope=module)

# 替换后
width = p.type.bitWidth  # 整数，参数化模块中 elaboration 后自动求值
```

always_ff 时钟与复位识别（使用 SensitivityListKind.Explicit 的 reads）：

```python
for p in procs_analyzed:
    sl = p.sensitivityList
    if sl.kind == SensitivityListKind.Explicit:
        for rr in sl.reads:
            clock_signals.add(rr.symbol.name)
```

always_if 时序条件提取（利用 TimedStatement）：

```python
for proc in procs:
    if proc.procedureKind != ProceduralBlockKind.AlwaysFF: continue
    if not isinstance(proc.body, TimedStatement): continue

    clocks = []
    def collect(obj):
        if isinstance(obj, SignalEventControl):
            clocks.append( f"{obj.expr.getSymbolReference().name} {str(obj.edge)}" )
    proc.body.timing.visit(collect)
```

---

## 第五步：用 getHierarchicalPath() 替换手写路径构建

**工作量：2 天 替换文件：graph_builder.py 的 ConnectionExtractor（约 250 行）**

```python
insts = []
root.visit(lookup_table={SymbolKind.Instance: insts.append})

for inst in insts:
    path = inst.getHierarchicalPath()
    for port_conn in inst.getPortConnections():
        port = port_conn.port
        if port.kind != SymbolKind.Port: continue

        port_symbol = port.as_port()
        inst_port_id = f"{path}.{port_symbol.name}"

        # 连接表达式（父模块端的信号）
        conn_expr = port_conn.getExpression()
```

---

## 第六步：图结构位精确化

**工作量：4 天 依赖：第三步 替换文件：src/trace/core/graph/models.py**

问题根源：现有图中，一个节点代表整根导线。

### 6.1 图换成 MultiDiGraph

DiGraph 在一对节点之间只允许一条边，无法表示同一信号被多个源驱动不同位范围的情况：

```python
class SignalGraph:
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.node_data: Dict[str, TraceNode] = {}
        self.edge_data: Dict[tuple, TraceEdge] = {}
```

### 6.2 TraceNode 和 TraceEdge 增加字段

```python
@dataclass
class TraceNode:
    id: str
    name: str
    module: str
    kind: NodeKind
    width: int = 1
    decl_loc: Optional[SourceLoc] = None  # 信号声明的源码位置

@dataclass
class TraceEdge:
    src: str
    dst: str
    kind: EdgeKind
    assign_type: str = ""
    clock_domain: str = ""
    bit_lo: Optional[int] = None
    bit_hi: Optional[int] = None
    assign_loc: Optional[SourceLoc] = None  # 赋值的源码位置
    condition_expr: Optional[str] = None
    condition_vars: list = field(default_factory=list)
```

### 6.3 位感知查询 API

```python
def find_drivers(self, signal_id: str, bit_lo: int = None, bit_hi: int = None) -> List[TraceNode]:
    # 查找后门的驱动源
    drivers = []
    for src, dst, key, _ in self.graph.in_edges(signal_id, data=True, keys=True):
        edge = self.edge_data.get((src, dst, key))
        if edge and edge.kind == EdgeKind.DRIVER:
            if bit_lo is not None and bit_hi is not None:
                if not edge.overlaps(bit_lo, bit_hi):
                    continue
            node = self.node_data.get(src)
            if node: drivers.append(node)
    return drivers

def get_bit_coverage(self, signal_id: str) -> Dict[tuple, list[str]]:
    # 返回信号各位范围的驱动来源映射
    coverage = {}
    for src, dst, key, _ in self.graph.in_edges(signal_id, data=True, keys=True):
        edge = self.edge_data.get((src, dst, key))
        if edge and edge.kind == EdgeKind.DRIVER and edge.bit_lo is not None:
            coverage[(edge.bit_lo, edge.bit_hi)] = [src]
    return coverage
```

---

## 第七步：清理死代码与设计快速修复

**工作量：3 天（原 1 天死代码清理 + 2 天设计快速修复）**

- 7.1 删除废弃文件：`src/trace/core/pyslang_adapter.py`（已无用），`src/trace/core/visitors/` 整个目录。
- 7.2 删除死代码：`graph_builder.py` 第 489 行 return 后的代码。
- 7.3 删除死 Visitor 层：`src/trace/core/visitors/` 未被 import 或调用，属无效代码。
- 7.4 修复 Extractor 被调用两次：将 `extract()` 的调用结果缓存到变量，避免两次构建。
- 7.5 显式化构建顺序依赖：在 graph 构建阶段添加 `assert len(self.graph.nodes) > 0`。
- 7.6 合并重复的端口处理逻辑：DriverExtractor 和 LoadExtractor 中重复的 `_build_port_nodes` 逻辑合并。
- 7.7 收窄 except 范围：不要吞掉所有异常，只捕获 AttributeError 等特定异常。

---

## 第八步：边语义统一（CONNECTION vs DRIVER）

**工作量：1 周（含测试更新） 替换文件：src/trace/core/graph/models.py**

背景：
当前 EdgeKind 有两类概念混用：DRIVER（信号被赋值）与 CONNECTION（模块端口连接）。本质上都是"谁驱动谁"的关系。

新的边类型分类法：

```python
class EdgeKind(Enum):
    # 驱动关系（统一的"谁驱动谁"）
    DRIVES = "drives"  # 替换原 DRIVER + CONNECTION
    CLOCKED = "clocked"  # always_ff 中的寄存器赋值

    # 结构关系
    BIT_PART = "bit_part"  # 替换原 BIT_SELECT
    INSTANCE = "instance"  # 模块实例化
```

迁移方式：
将 CONNECTION 改造后输出 DRIVES 边（而非 CONNECTION），统一 `find_drivers()`。

---

## 第九步：条件感知图（ConditionExtractor）

**工作量：1 周 新建文件：src/trace/core/condition_extractor.py**

背景：`am.getDrivers()` 回答"谁驱动谁"（数据结构），但不回答"在什么条件下驱动"（控制流上下文）。条件信息存在于 ProceduralBlock 的 AST 里。

### 9.1 条件节点数据结构

```python
from dataclasses import dataclass, field
CondNode = Union[CondExpr, CondEqual, CondNot, CondAnd]
```

### 9.2 ConditionExtractor

核心：递归累积 `cond_stack`
遍历 ProceduralBlock 的 AST，为每个赋值语句提取 guard 条件。

### 9.3 边构建策略：Method A（主路径）

直接把 `am.getDrivers()` 作为边的数据源，只用来查询位范围。完全绕过手写 AST。

```python
def build_driver_edges_with_conditions(root, am, comp, result):
    # Step 1: 用 am.getDrivers() 预建 (dst, src) -> bounds 索引
    # Step 2: ConditionExtractor 遍历所有 ProceduralBlock，提取 (lhs_path, rhs_path, cond, stmt_loc)
    # Step 3: 连续赋值 (assign) 由 am.getDrivers 覆盖，ConditionExtractor 不遍历
```

### 9.4 条件感知查询 API

```python
def find_drivers_under(self, signal_id: str, conditions: dict, bit_lo: int = None, bit_hi: int = None):
    # 在给定条件约束下查找驱动源
    if not condition_satisfied(edge.condition_expr, edge.condition_vars, conditions):
        continue
```

---

## 执行计划

| 周 | 任务 | 完成标志 |
|----|------|----------|
| Week 1 | 第一步 ~ 第七步 | compile_sv() 可用，死 Visitor 层删除；Extractor 调用缓存修复；except 收窄；669 测试基线确认 |
| Week 2 | 第二步 | root.visit(lookup_table) 替换手写遍历，测试回归 |
| Week 3 | 第三步 | am.getDrivers() 替换 DriverExtractor/LoadExtractor，bit_lo/bit_hi 写入边，测试回归 |
| Week 4 | 第四步 + 第五步 | 语义 API 全替换，ClockDomainExtractor 合并进主流程，参数化模块测试通过 |
| Week 5 | 第六步 | MultiDiGraph、位感知查询 API、BitSelectHandler 语义化，位精确测试通过 |
| Week 6 | 第八步 | DRIVES/CLOCKED/BIT_PART 统一边类型，测试 gold standard 全部更新 |
| Week 7 | 第九步 | ConditionExtractor（含 sm 参数）+ Method A 直接建边 + Method B SourceRange 回填 + 条件感知查询 API（trace_chain_under） |

---

## 关于测试失败的处理策略

重构过程中出现测试失败时，按以下顺序判断：

1. **失配参数化位宽相关**：原测试断言的是字符串（如 `w-1`），新 API 返回整数（如 `7`），更新测试断言，新行为是正确的。
2. **失配信号路径格式**：原测试可能用 `"module_name.signal"` 格式，`getHierarchicalPath()` 返回完整路径 `"top.u_inst.signal"`。检查哪个格式更符合业务需求，统一更新。
3. **失配驱动数很多时**：`am.getDrivers()` 可能返回比手写遍历更多的驱动源（原实现漏掉了某些赋值类型）。验证新结果是否正确，更新测试的 gold standard。
4. **失配驱动数很少时**：检查 `comp.getSemanticDiagnostics()` 是否有错误，可能是 SV 代码本身有语义问题，原实现没有发现。
5. **第八步后失败在 EdgeKind 不匹配**：旧 `EdgeKind.CONNECTION` / `.DRIVER` 已重命名，用 `grep` 搜索 EdgeKind 并全局替换。
6. **第九步后失败在条件未匹配**：检查 `fill_conditions` 是否成功回填。

---

## 改造后的收益

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 核心逻辑代码量 | ~1500 行 | ~250 行 |
| 参数化位宽 | 返回字符串如 `"w-1"` | 返回整数 7 |
| 跨文件引用 | 可能混模块名 | `getHierarchicalPath()` 唯一 |
| generate block | 不支持 | `isInstantiated` 自动处理 |
| pyslang 版本兼容 | 字符串匹配随时失效 | 枚举比较，编译期报错 |
| 驱动精度 | 信号级，部分赋值漏掉 | 位精确，`d.bounds` 给出范围 |
| 部分位驱动查询 | 不支持 | `find_drivers("x", bit_lo=4, bit_hi=7)` |
| 位覆盖分析 | 不支持 | `get_bit_coverage("x")` 返回区间映射 |
| 多源驱动同一信号 | DiGraph 叠加边 | MultiDiGraph 保留所有并行边 |
| 边类型语义 | DRIVER/CONNECTION 混用 | 统一 DRIVES，查询去歧义 |
| 端口连接的位精度 | CONNECTION 边无位范围 | DRIVES 边统一带 `bit_lo/bit_hi` |
| Extractor 调用成本 | 每次 build_graph() 遍历两端 | 缓存结果，遍历一次 |
| 无效代码 | 约 300 行死 Visitor 层 + 废弃适配器 | 全量删除 |
| 构建隐式依赖 | 隐式、未文档化 | 显式断言 + 步骤顺序固化 |
| 条件驱动查询 | 不支持 | `trace_chain_under("out", {"sel":1})` 返回条件路径 |
| 信号声明位置 | 不支持 | `node.decl_loc` -> `"rtl/datapath.sv:42"` |
| 赋值语句位置 | 不支持 | `edge.assign_loc` -> `"rtl/datapath.sv:42"` |
| AST 使用方式 | 用 AST 做一切（结构+条件），脆弱 | AST 专用于条件提取，类型化遍历，稳定 |