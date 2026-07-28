# DataFlow 分析架构方案

> 创建时间: 2026-05-24
> 更新: 2026-05-31
> 状态: ✅ 已实现 (反映实际实现)

---

## 📝 实现说明 (2026-05-31 更新)

实际实现的 `DataFlowSegment` 与原设计有以下差异：

| 字段 | 原设计 | 实际实现 |
|------|--------|----------|
| driver | `SignalResult` 对象 | `Optional[str]` 字符串 |
| condition | `ConditionInfo` 对象 | `Optional[str]` 字符串 |
| is_blocking | ✅ 有 | ❌ 用 `assign_type` 替代 |
| effective_condition | ❌ 无 | ✅ 有 |
| assign_type | ❌ 无 | ✅ 有 |
| distance | ❌ 无 | ✅ 有 |

---

## 核心洞察

**数据流分析本质上是 GRAPH 问题，不是 Visitor 问题。**

| 层次 | 解决的问题 | 技术手段 |
|------|-----------|----------|
| Visitor | AST 遍历 → 信号提取 | 遍历模式 |
| Graph 算法 | 路径搜索 → 数据流分析 | networkx |

---

## 三层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 路径层 (Path Level)                               │
│  DataFlowResult → DataFlowPath → DataFlowSegment            │
│  算法: nx.all_simple_paths()                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: 段层 (Segment Level)                               │
│  DataFlowSegment = from + to + driver + condition + timing  │
│  来源: StatementCollectorVisitor                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: 节点层 (Node Level)                                │
│  SignalResult = primary + all_signals + kind + op + ...    │
│  来源: SignalExpressionVisitor.extract()                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心数据结构

### Layer 1: SignalResult (已实现)

```python
@dataclass
class SignalResult:
    # 核心结果
    primary: Optional[str]              # 单信号名
    all_signals: List[str]              # 所有信号（去重）
    
    # 表达式元信息
    kind_name: Optional[str]            # 'BinaryOp', 'NamedValue'
    op_name: Optional[str]              # 'Add', 'Subtract'
    
    # 位置信息
    source_range: Optional[tuple]        # ((line, col), (line, col))
    
    # 未来扩展（数据流相关）
    condition_signals: List[str]        # 条件信号
    timing: Optional[str]               # '@posedge clk'
    condition_expr: Optional[str]       # 条件表达式原文
```

### Layer 2: DataFlowSegment (NEW)

```python
@dataclass
class DataFlowSegment:
    """单步驱动关系: from_signal → to_signal"""
    
    from_signal: str                    # 起点信号
    to_signal: str                      # 终点信号
    
    driver: SignalResult                 # 驱动表达式结果
    condition: Optional[ConditionInfo]   # 条件信息
    timing: Optional[str]               # '@posedge clk'
    is_blocking: bool                   # 是否阻塞赋值
```

### ConditionInfo (NEW)

```python
@dataclass
class ConditionInfo:
    """条件信息"""
    
    kind: str                           # 'if', 'case', 'conditional_op'
    expr: str                           # 条件表达式原文
    signals: List[str]                  # 条件涉及的信号
    true_branch: str                    # 真分支值
    false_branch: Optional[str]         # 假分支值
```

### Layer 3: DataFlowPath / DataFlowResult (NEW)

```python
@dataclass
class DataFlowPath:
    """单条完整路径"""
    
    path_id: int
    segments: List[DataFlowSegment]
    distance: int                      # 跳数
    has_conditional: bool

class TimingAnalysisResult:
    """路径时序分析结果"""
    
    # 时钟域信息
    path_clock_domains: List[str] = field(default_factory=list)  # 路径经过的时钟域
    dominant_clock_domain: Optional[str] = None  # 主时钟域
    cross_clock_domain: bool = False  # 是否跨时钟域
    
    # 寄存器信息
    register_stages: int = 0  # 寄存器级数
    registers_in_path: List[str] = field(default_factory=list)  # 路径中的寄存器
    
    # 时序路径
    timing_paths: List[List[str]] = field(default_factory=list)  # 寄存器→寄存器路径
    estimated_latency_cycles: int = 0  # 估计延迟（周期数）
    
    # 关键路径
    critical_path: Optional[List[str]] = None  # 关键路径（最长路径）
    
    # 风险评估
    path_timing_risk: str = "safe"  # 路径风险级别: safe/low/medium/high/critical


@dataclass
class DataFlowResult:
    """数据流分析完整结果"""
    
    from_signal: str
    to_signal: str
    
    # 数据流
    paths: List[DataFlowPath] = field(default_factory=list)
    is_reachable: bool = False
    paths_count: int = 0
    
    # 中间信号
    intermediate_signals: Set[str] = field(default_factory=set)
    
    # 条件信息
    all_conditions: List[ConditionInfo] = field(default_factory=list)
    
    # 时序分析 (融合时序分析结果)
    timing_analysis: Optional[TimingAnalysisResult] = None
    clock_domain: Optional[str] = None
    path_timing_risk: str = "safe"
    
    # 便捷属性
    @property
    def cross_clock_domain(self) -> bool:
        """是否跨时钟域"""
        return self.timing_analysis.cross_clock_domain if self.timing_analysis else False
    
    @property
    def register_stages(self) -> int:
        """路径寄存器级数"""
        return self.timing_analysis.register_stages if self.timing_analysis else 0
    
    @property
    def latency_cycles(self) -> int:
        """路径延迟周期数"""
        return self.timing_analysis.estimated_latency_cycles if self.timing_analysis else 0
```

---

## API 设计

```python
class DataFlowAnalyzer:
    """数据流分析器"""
    
    def __init__(self, graph: SignalGraph, adapter: PyslangAdapter):
        self.graph = graph
        self.adapter = adapter
    
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        """
        主入口: 分析 from → to 的数据流
        
        步骤:
        1. Path finding (networkx)
        2. Build DataFlowSegment for each hop
        3. Enrich with condition/timing info
        4. Return DataFlowResult
        """
        # 1. 路径搜索
        paths = self._find_all_paths(from_signal, to_signal)
        
        # 2. 构建路径
        data_flow_paths = []
        for path_id, path in enumerate(paths):
            segments = self._build_segments(path)
            df_path = DataFlowPath(
                path_id=path_id,
                segments=segments,
                distance=len(path) - 1,
                has_conditional=any(s.condition for s in segments)
            )
            data_flow_paths.append(df_path)
        
        # 3. 汇总信息
        return DataFlowResult(
            from_signal=from_signal,
            to_signal=to_signal,
            paths=data_flow_paths,
            is_reachable=len(paths) > 0,
            paths_count=len(paths),
            intermediate_signals=self._collect_intermediate(paths),
            all_conditions=self._collect_conditions(data_flow_paths),
            all_timings=self._collect_timings(data_flow_paths)
        )
    
    def _find_all_paths(self, from_signal, to_signal) -> List[List[str]]:
        """使用 networkx 找所有路径"""
        G = self.graph.to_networkx()
        return list(nx.all_simple_paths(G, from_signal, to_signal, cutoff=20))
    
    def _build_segments(self, path: List[str]) -> List[DataFlowSegment]:
        """构建路径段列表"""
        segments = []
        for i in range(len(path) - 1):
            from_sig = path[i]
            to_sig = path[i + 1]
            
            # 查找驱动信息
            driver_stmt = self._get_driver_statement(from_sig, to_sig)
            timing = self._get_timing(driver_stmt)
            condition = self._get_condition(driver_stmt)
            
            segment = DataFlowSegment(
                from_signal=from_sig,
                to_signal=to_sig,
                driver=driver_stmt,
                condition=condition,
                timing=timing
            )
            segments.append(segment)
        
        return segments
```

---

## 与现有系统的集成

```
现有系统                              集成点
────────                            ────────
SignalGraph                         DataFlowAnalyzer.graph
DriverExtractor                     DataFlowSegment 查找
SignalExpressionVisitor.extract()  SignalResult
StatementCollectorVisitor           ConditionInfo 提取
```

### 现有组件

| 组件 | 已有功能 | 数据流分析中的角色 |
|------|----------|-------------------|
| `SignalGraph` | nodes + edges | 路径搜索基础 |
| `DriverExtractor` | get_drivers() | 查找 from→to 驱动源 |
| `SignalExpressionVisitor` | extract() | 生成 SignalResult |
| `StatementCollectorVisitor` | 收集语句上下文 | 生成 ConditionInfo |

### 新增组件

| 组件 | 职责 |
|------|------|
| `DataFlowAnalyzer` | 主分析器，路径搜索 |
| `DataFlowResult` | 结果封装 |
| `DataFlowPath` | 单条路径封装 |
| `DataFlowSegment` | 单步驱动封装 |
| `ConditionInfo` | 条件信息封装 |

---

## 实现优先级

### P1: 核心功能

1. **DataFlowSegment** - 单步驱动数据结构
2. **DataFlowAnalyzer._find_all_paths()** - 路径搜索
3. **DataFlowAnalyzer.analyze()** - 主入口

### P2: 上下文丰富

1. **ConditionInfo** - 条件信息
2. **DataFlowSegment.condition** - 填充条件
3. **DataFlowSegment.timing** - 填充时序

### P3: 高级功能

1. 多路径分析
2. 循环检测
3. 条件覆盖分析

---

## 示例

### 输入

```
module pipeline(input clk, input [7:0] data_in, output [7:0] data_out);
    logic [7:0] stage1, stage2;
    
    always_ff @(posedge clk) begin
        stage1 <= data_in;
        stage2 <= stage1;
    end
    
    assign data_out = stage2;
endmodule
```

### 调用

```python
analyzer = DataFlowAnalyzer(graph, adapter)
result = analyzer.analyze('data_in', 'data_out')
```

### 输出

```python
DataFlowResult:
  from_signal: 'data_in'
  to_signal: 'data_out'
  paths_count: 1
  
  # 数据流
  paths: [
    DataFlowPath:
      path_id: 0
      distance: 3
      segments: [
        DataFlowSegment(from='data_in', to='stage1', timing='@posedge clk'),
        DataFlowSegment(from='stage1', to='stage2', timing='@posedge clk'),
        DataFlowSegment(from='stage2', to='data_out', timing=None)
      ]
  ]
  intermediate_signals: {'stage1', 'stage2'}
  
  # 时序分析 (新增)
  timing_analysis:
    path_clock_domains: ['clk']
    dominant_clock_domain: 'clk'
    cross_clock_domain: False
    register_stages: 2
    registers_in_path: ['stage1', 'stage2']
    estimated_latency_cycles: 2
    critical_path: ['data_in', 'stage1', 'stage2', 'data_out']
    path_timing_risk: 'safe'
  
  clock_domain: 'clk'
  path_timing_risk: 'safe'
```

## 与现有组件的关系

| 组件 | 关系 |
|------|------|
| ClockDomainTracer | 被 DataFlowAnalyzer 复用，复用其 _build_timing_chain 等逻辑 |
| SignalTracer | SignalTracer 是单信号查询，DataFlow 是信号对查询 |
| EdgeKind.CLOCK | 被用于识别时钟驱动的边 |
| NodeKind.REG | 被用于识别路径中的寄存器 |# Designer Workflow: 看 A→B 的 Dataflow + Controlflow

**Audience**: RTL designer / verification engineer 接手新 RTL 项目时, 想看 signal A 到 signal B 的数据流跟 if/case 条件.

**Status**: 当前用 3 命令组合 (A 方案). 需要时升级到 1 复合命令 (B 方案).

**Last updated**: 2026-07-04

---

## 🎯 这个 doc 解决什么问题

新人接手 RTL 项目 (e.g. CPU core, bus, FIFO), 最常问的 3 个问题:

1. **"signal A 到 signal B 怎么连?"** (dataflow)
2. **"中间过哪些 if/case 条件?"** (controlflow)
3. **"这段 path 几个 cycle 延迟?"** (latency)

传统方法: 读 always_ff + grep if/case, 5-10 min/段.

**A 方案**: 3 命令组合, 30s 看 1 段. **10x 加速**.

---

## 🚀 Quick Start (3 命令组合)

### 场景: 看 `A` → `B` 的 dataflow + if/case + 源码

```bash
# 1️⃣ dataflow: 找 A→B 路径 + segments + latency
sv_query -q dataflow analyze A B --no-strict --file x.sv --json
# 输出: latency_cycles, primary_is_async, paths[].segments[], 每个 segment 含 condition

# 2️⃣ controlflow: 看 A 跟 B 的 if/case 条件
sv_query -q controlflow analyze A --no-strict --file x.sv --json
sv_query -q controlflow analyze B --no-strict --file x.sv --json
# 输出: conditioned_drivers[].conditions[].expr (e.g. "push_i && !full_o")

# 3️⃣ evidence: 拿 A 或 B 所在 always/if 源码
sv_query -q trace evidence B --no-strict --file x.sv --json
# 输出: source_location (line), enclosing_if, enclosing_always, source_text
```

### 跑 1 段: 12 命令, ~30s

> 1 个 dataflow + 2 个 controlflow (A + B) + 1 个 evidence = 4 命令/段
> 跑 3 段 (e.g. CPU 5-stage IF/ID/EX) = 12 命令, ~30s

---

## 📊 Step-by-step 例子: darkriscv 5-stage RISC-V

**目标**: 看 4 段 pipeline 路径, 找 IF/ID/EX stage 的 if/case 条件.

### 输入

```bash
DARKRISCV=~/my_dv_proj/darkriscv/rtl/darkriscv.v
```

### 段 1: IF stage - PC 怎么输出

```bash
sv_query -q dataflow analyze darkriscv.IFPC darkriscv.IADDR \
  --no-strict --file $DARKRISCV --json | jq '.result | {latency: .primary_latency_cycles, async: .primary_is_async, note: .paths[0].latency_note, segments: [.paths[0].segments[] | {from: .from_signal, to: .to_signal, condition}]}'
```

**实际输出**:
```json
{
  "latency": 0,
  "async": false,
  "note": "no register boundary (combinational only)",
  "segments": [{"from": "darkriscv.IFPC", "to": "darkriscv.IADDR", "condition": ""}]
}
```

**结论**: PC → 地址输出是 **combinational** (0 cycle), 不是 1 cycle. **没 if 条件** (assign).

### 段 2: ID stage - 指令怎么到 ID reg

```bash
sv_query -q dataflow analyze darkriscv.IDATA1 darkriscv.IDATA2 \
  --no-strict --file $DARKRISCV --json | jq '.result | {latency: .primary_latency_cycles, segments: [.paths[0].segments[] | {from: .from_signal[-15:], to: .to_signal[-15:], condition}]}'
```

**实际输出**:
```json
{
  "latency": 1,
  "segments": [{"from": "darkriscv.IDATA1", "to": "darkriscv.IDATA2", "condition": "HLT2^HLT"}]
}
```

```bash
# controlflow 找 B 的 if 条件
sv_query -q controlflow analyze darkriscv.IDATA2 \
  --no-strict --file $DARKRISCV --json | jq '.result.conditioned_drivers[].conditions[].expr'
# 输出: "HLT2^HLT" (重复 2 次)
```

```bash
# evidence 拿源码
sv_query -q trace evidence darkriscv.IDATA2 \
  --no-strict --file $DARKRISCV --json | jq '.result.signals[0].evidence | {line: .source_location.line_start, if: .enclosing_if.text, always: .enclosing_always.text}'
```

**实际输出**:
```json
{
  "line": 178,
  "if": "if(HLT2^HLT) IDATA2 <= IDATA1;",
  "always": "(none)"
}
```

**结论**: ID stage 关键 if 是 **`HLT2 XOR HLT`** (halt 同步). 1 cycle latency.

### 段 3: EX stage - 怎么到 EX reg

```bash
sv_query -q dataflow analyze darkriscv.IDATA2 darkriscv.XIDATA \
  --no-strict --file $DARKRISCV --json | jq '.result | {latency: .primary_latency_cycles, segs: [.paths[0].segments[] | {from: .from_signal[-15:], to: .to_signal[-15:]}]}'
```

**实际输出**:
```json
{
  "latency": 1,
  "segs": [
    {"from": "darkriscv.IDATA2", "to": "darkriscv.IDATAX"},
    {"from": "darkriscv.IDATAX", "to": "darkriscv.XIDATA"}
  ]
}
```

**结论**: EX stage 内部 2 segments, 中间 signal `IDATAX`. 1 cycle latency.

### 段 4: 跨 stage 不可达 (真信息)

```bash
sv_query -q dataflow analyze darkriscv.IFPC darkriscv.IDATA2 \
  --no-strict --file $DARKRISCV --json | jq '.result.is_reachable'
# 输出: false
```

**结论**: PC 跟 inst 走**不同 data flow** (PC 走 IF → IADDR → 外部 memory; inst 从 IDATA input 回来). **designer 用此确认 stage 边界**, 不是 bug.

---

## 📚 4 命令 output schema 详解

### `dataflow analyze A B`

```json
{
  "result": {
    "is_reachable": true,
    "paths_count": 3,
    "primary_latency_cycles": 1,         // 关键: 几 cycle 延迟
    "primary_is_async": false,            // 关键: 是否跨 clk
    "intermediate_signals": [...],
    "all_conditions": [...],
    "clock_domain": "clk_i",
    "timing_risk": "safe",
    "paths": [
      {
        "path_id": 0,
        "segments": [
          {
            "from_signal": "darkriscv.IDATA1",
            "to_signal": "darkriscv.IDATA2",
            "driver": "IDATA1",            // 驱动表达式
            "condition": "HLT2^HLT",       // 关键: if 条件
            "timing": "clk_i",
            "assign_type": "nonblocking",
            "distance": 1
          }
        ],
        "distance": 1,
        "latency_cycles": 1,
        "is_async_crossing": false,
        "latency_note": "1 sync stages (cycle latency)",
        "stage_breakdown": [...]           // 复用 detect_pipeline, 标 stage_id
      }
    ]
  }
}
```

**关键字段**:
- `primary_latency_cycles`: 主路径 cycle 数. 异步返 `null`.
- `primary_is_async`: 是否跨 clk.
- `paths[].segments[].condition`: **每个 segment 的 if 条件** (e.g. "HLT2^HLT", "push_i && !full_o")
- `paths[].latency_note`: "N sync stages" / "no register boundary" / "async crossing"

### `controlflow analyze <sig>`

```json
{
  "result": {
    "signal": "darkriscv.IDATA2",
    "conditioned_drivers": [
      {
        "to_node": "darkriscv.IDATA2",
        "conditions": [
          {
            "expr": "HLT2^HLT",           // 关键: if 表达式
            "edge": {
              "src": "darkriscv.clk_i",
              "dst": "darkriscv.IDATA2",
              "kind": "CLOCK",
              "condition": "HLT2^HLT"
            }
          }
        ]
      }
    ]
  }
}
```

**关键字段**:
- `conditioned_drivers[]`: 这个 signal 的所有条件驱动
- `conditions[].expr`: **if/case 表达式文本**
- `conditions[].edge.condition`: 边上的条件 (与 expr 一致)

### `trace evidence <sig>`

```json
{
  "result": {
    "signals": [
      {
        "evidence": {
          "source_location": {
            "file": "...",
            "line_start": 178,
            "line_end": 178,
            "column": 9
          },
          "enclosing_if": {                // 注意: 是 dict, 不是 str
            "file": "...",
            "line_start": 178,
            "text": "if(HLT2^HLT) IDATA2 <= IDATA1;"
          },
          "enclosing_always": {
            "file": "...",
            "line_start": 174,
            "text": "always @(posedge CLK or negedge RES) begin\n  HLT2 <= HLT; ... if(HLT2^HLT) IDATA2 <= IDATA1; ..."
          }
        }
      }
    ]
  }
}
```

**关键字段**:
- `source_location.line_start`: **源码行号**
- `enclosing_if.text`: **if 表达式源码**
- `enclosing_always.text`: 整个 always block 源码 (含 if 嵌套)

---

## 🎯 真实使用场景

### 场景 1: 接手新 CPU, 看 5-stage pipeline
- 跑 4-5 段: PC → IF_reg → ID_reg → EX_reg → MEM_reg → WB
- 找每段的 if 条件 (stall, flush, branch)
- 看 if/case 是否合理
- **时间**: 5 min (vs 30 min 读代码)

### 场景 2: 改一个 signal 之前
- 跑 `dataflow impact <sig>` 看影响范围
- 跑 `dataflow analyze <sig> <destination>` 看具体 path
- 跑 `controlflow` 找 if 条件 (改了条件要改哪里)
- 跑 `evidence` 确认源码位置
- **时间**: 1 min/段

### 场景 3: 写 SVA 之前
- 找关键 signal 路径
- 看 if 条件 (SVA 要覆盖所有 if 分支)
- 跑 `risk analyze` 排高风险 signal 优先
- **时间**: 5 min/段

### 场景 4: 找 CDC 风险
- 跑 `dataflow analyze` 跨 clk signal
- 看 `is_async_crossing=true` 自动标
- 找哪些路径没 synchronizer
- **时间**: 1 min/段

---

## ⚠️ 限制 (诚实)

1. **`dataflow analyze A B` 的 `condition` 字段**: 是驱动条件 (e.g. `push_i && !full_o`), 跟"if 嵌套"不同. 复杂嵌套 if (e.g. `if (a) begin if (b) c = d; end`) 看不到 b.
2. **`controlflow analyze <sig>` 只看单 signal**, 不看 A→B path. 需要对 path 上每个 signal 各跑一次.
3. **跨 stage 不可达是**真信息, designer 要能理解 (e.g. PC 跟 inst 走不同 path).
4. **`enclosing_always` 是 dict** (含 file/line/text), 不是简单 string. 提取源码用 `.text` 字段.
5. **大项目 (CVA6 137K 行)**: filelist 不全会报"missing submodule" warnings, 跑慢 (~10-15s), 但仍能用 --no-strict.
6. **pyslang 内存敏感**: 200K+ 行项目在 8GB MBA 上可能 OOM. 建议每个 CPU core 跑一次, 不要一次跑整个 SoC.

---

## 🚀 高级用法

### 批量跑多段 (shell loop)

```bash
# 跑 CPU 5 stage pipeline 5 段
DARKRISCV=~/my_dv_proj/darkriscv/rtl/darkriscv.v
for seg in "IFPC IADDR" "IDATA1 IDATA2" "IDATA2 XIDATA" "XIDATA REGS[0]"; do
  set -- $seg
  echo "=== $1 → $2 ==="
  sv_query -q dataflow analyze darkriscv.$1 darkriscv.$2 \
    --no-strict --file $DARKRISCV --json | \
    jq '.result | {lat: .primary_latency_cycles, async: .primary_is_async, segs: [.paths[0].segments[] | {from: .from_signal[-20:], to: .to_signal[-20:], cond: .condition}]}'
done
```

### 跑 1 段全 pipeline (3 命令串起来)

```bash
run_path() {
  local A=$1 B=$2 FILE=$3
  echo "=== $A → $B ==="
  echo "  [dataflow]"
  sv_query -q dataflow analyze $A $B --no-strict --file $FILE --json | \
    jq -r '.result | "  latency=\(.primary_latency_cycles) async=\(.primary_is_async) | \(.paths[0].latency_note)"'
  echo "  [controlflow B]"
  sv_query -q controlflow analyze $B --no-strict --file $FILE --json | \
    jq -r '.result.conditioned_drivers[]?.conditions[]?.expr' | head -3 | sed 's/^/    if: /'
  echo "  [evidence B]"
  sv_query -q trace evidence $B --no-strict --file $FILE --json | \
    jq -r '.result.signals[0].evidence | "    line \(.source_location.line_start): \(.enclosing_if.text // "(no if)")"'
}

run_path "darkriscv.IFPC" "darkriscv.IDATA2" "~/my_dv_proj/darkriscv/rtl/darkriscv.v"
```

### 用 LLM 批量分析 (LLM-friendly schema)

`dataflow analyze` 的 JSON output 已经是 LLM-friendly:

```json
{
  "primary_latency_cycles": 1,
  "primary_is_async": false,
  "latency_note": "1 sync stages (cycle latency)",
  "paths": [{
    "segments": [{
      "from_signal": "...",
      "to_signal": "...",
      "condition": "HLT2^HLT"  // LLM 看得懂
    }]
  }]
}
```

LLM 可以直接:
- 解释: "从 A 到 B 经过 1 cycle, 中间条件是 HLT2^HLT"
- 提 SVA: "always @(posedge clk) if (HLT2^HLT) IDATA2 == IDATA1"
- 找 bug: "HLT2^HLT 是 XOR, 但 HLT 持续 1 cycle, 漏 cycle"

---

## 🔄 何时升级到 B 复合命令

**当前 A 方案够用**, 但**升级触发点**:

| 场景 | 命令数 | 升级建议 |
|------|--------|----------|
| 偶尔看 1 段 | 4 命令 | 不用升级 |
| 看 5 段 (1 CPU stage) | 20 命令 | 考虑 B |
| 看 25 段 (5 stage × 5 path) | 100 命令 | **B 必须** |
| 每次 review 都看 1 段 | 4 命令/次 | 考虑 B |

**B 复合命令** (计划中, 1h):
```bash
sv_query -q dataflow-controlflow analyze A B --no-strict --file x.sv --json
```
输出 1 个 JSON 含 path + latency + 所有 if/case + 源码. 不用 3 命令 join.

**C 复合命令** (B + evidence, 2h): 加 evidence 源码, 不用额外跑.

如果你**经常**跑 A→B 路径, 1 周跑 10+ 次, 升级 B 1h 值得. 否则 A 够用.

---

## 📚 相关 doc

- `docs/CONTROL_FLOW_ANALYSIS.md` - controlflow 详细原理
- `docs/DATAFLOW_ANALYSIS_ARCHITECTURE.md` - dataflow 架构
- `docs/CDC_ANALYSIS.md` - 跨 clk 检测
- `docs/CONTROL_FLOW_DESIGN.md` - controlflow 设计意图
- `sim/tests/integration/test_dataflow_latency_open_source.py` - 13 tests + 1 golden (金标准验证)

---

## 🪞 真实使用反馈

实测 darkriscv 5-stage RISC-V 4 段:
- 4 path × 3 命令 = 12 命令, **~30s**
- 关键 if 条件 (`HLT2^HLT`) 自动识别
- EX stage 内部 2 segments (via IDATAX) 完整追踪
- 跨 stage 不可达是**真信息** (PC 跟 inst 走不同 path)

**对比传统读代码**: 4 段 5-10 min/段 = 20-40 min vs 30s = **40-80x 加速**.

**限制**: 复杂嵌套 if 不能完整还原, 大项目 OOM, 跨 stage 不可达需要 designer 理解.

---

## 📅 维护

- 创建: 2026-07-04 (A 方案实跑 darkriscv 验证后)
- 更新: 升级到 B 复合命令时
- 反馈: 跑更多真项目 (OpenTitan / CVA6 / vortex) 后, 加案例

---

**TL;DR**: 跑 A→B 用 3 命令 (`dataflow` + `controlflow` + `evidence`), 30s 看 1 段完整 dataflow + if/case + 源码. 比读代码快 10-80x.
# DataFlowGraph Implementation Plan

## 目标
实现基于 SignalGraph + MIG 的 DataFlowGraph，支持跨模块的完整数据流分析。

## 文件位置
`src/trace/core/graph/dataflow.py`

## 核心数据结构

### DataFlowSegment
```python
@dataclass
class DataFlowSegment:
    from_signal: str           # 完整 hierarchy path
    to_signal: str             # 完整 hierarchy path
    driver: Optional[str]       # 驱动表达式
    condition: Optional[str]   # 驱动条件
    timing: Optional[str]      # 时钟域
    assign_type: str           # continuous/always_ff/always_comb
    distance: int              # 距离（跳数）
```

### DataFlowPath
```python
@dataclass
class DataFlowPath:
    path_id: int
    segments: List[DataFlowSegment]
    distance: int             # 总跳数
    has_conditional: bool
```

### DataFlowResult
```python
@dataclass
class DataFlowResult:
    from_signal: str
    to_signal: str
    paths: List[DataFlowPath]
    is_reachable: bool
    paths_count: int
    intermediate_signals: Set[str]
    all_conditions: List[str]
    clock_domain: Optional[str]
    timing_risk: str          # safe/low/medium/high/critical
```

## DataFlowGraph 类

```python
class DataFlowGraph:
    def __init__(self, signal_graph: SignalGraph, mig: ModuleInstanceGraph):
        self.signal_graph = signal_graph
        self.mig = mig
        self._segment_cache: Dict[Tuple[str, str], DataFlowSegment] = {}
    
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        """分析 from → to 的完整数据流路径"""
        
    def get_segment(self, from_signal: str, to_signal: str) -> DataFlowSegment:
        """获取单步驱动信息（带缓存）"""
        
    def _build_segment(self, from_signal: str, to_signal: str) -> DataFlowSegment:
        """构建段信息"""
        
    def _find_paths(self, from_signal: str, to_signal: str) -> List[List[str]]:
        """使用 networkx 找所有路径（允许循环）"""
        
    def _resolve_cross_module(self, signal: str) -> str:
        """解析跨模块信号，返回内部信号"""
```

## 实现步骤

### Phase 1: 基础结构
1. 创建 `dataflow.py`
2. 实现 `DataFlowSegment`, `DataFlowPath`, `DataFlowResult` 数据类
3. 实现 `DataFlowGraph.__init__`
4. 实现 `_find_paths` 路径搜索

### Phase 2: 段构建
1. 实现 `get_segment` 带缓存
2. 实现 `_build_segment`
3. 从 SignalGraph edge 获取 condition/timing

### Phase 3: 跨模块支持
1. 实现 `_resolve_cross_module`
2. 集成 MIG 的 port_to_internal 映射

### Phase 4: 结果组装
1. 实现 `analyze` 方法
2. 组装 DataFlowResult
3. 收集 intermediate_signals, all_conditions

## 与现有组件的集成

```python
# 在 unified_tracer.py 或新建 dataflow_analyzer.py
from .graph.dataflow import DataFlowGraph

class DataFlowAnalyzer:
    def __init__(self, signal_graph, mig):
        self.dfg = DataFlowGraph(signal_graph, mig)
    
    def analyze(self, from_signal, to_signal):
        return self.dfg.analyze(from_signal, to_signal)
```

## 待实现
- [x] 创建 dataflow.py
- [x] 数据类定义 (DataFlowSegment, DataFlowPath, DataFlowResult)
- [x] DataFlowGraph 基础结构
- [x] 路径搜索 (_find_paths)
- [x] 段构建与缓存 (get_segment, _build_segment)
- [x] 跨模块信号解析 (_resolve_cross_module)
- [x] analyze() 方法
- [x] 时钟域提取 (_extract_clock_domain)
- [x] 路径风险评估 (_evaluate_timing_risk)
- [x] 缓存统计 (get_cache_stats)
- [x] 集成到 graph/__init__.py
- [x] BIT_SELECT 节点处理 (byte_data[3:0] → byte_data 路径扩展)
- [x] Struct 成员展开 (pkt1.data → pkt2.data 成员赋值展开)
- [x] MEMBER_SELECT 边 (struct.member → struct 父节点追踪)

## 测试结果 (2026-05-26)

| 测试用例 | 结果 |
|---------|------|
| `byte_data → byte_low` (位选择) | ✅ |
| `byte_data → byte_high` (位选择) | ✅ |
| `pkt1.data → pkt2.data` (struct 赋值) | ✅ |
| `data_in → data_out` (完整 struct 路径) | ✅ (6条路径) |
| 循环检测 (组合逻辑环) | ✅ |
| 循环检测 (寄存器环) | ✅ |
| 839 tests passed | ✅ |