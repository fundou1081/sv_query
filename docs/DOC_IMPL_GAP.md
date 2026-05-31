# 文档与实现差异记录

> 创建时间: 2026-05-31
> 状态: 进行中
> 来源: 文档审查 + 代码实现对比

---

## 📋 差异概览

| # | 类别 | 文档状态 | 实现状态 | 用户决策 |
|---|------|----------|----------|----------|
| 1 | DataFlowSegment.effective_condition | ❌ 未提到 | ✅ 已有 | ✅ 更新文档 (反映实现) |
| 2 | SignalChain.control_dependencies | ❌ 未提到 | ✅ 已有 | 无需操作 |
| 3 | SignalChain.state_transitions | ❌ 未提到 | ✅ 已有 | 无需操作 |
| 4 | DataFlowGraph vs data_models.py | 分散 | 分散 | 无需操作 |
| 5 | base.py 拆分 P0/P1 | 建议拆分 | 未实施 | ✅ 更新文档 (暂停) |
| 6 | SVA/Coverage 生成 | 规划中 | 未实现 | ✅ 更新文档 (暂停) |
| 7 | 单dispatch架构 | 提案 | 未实施 | ✅ 更新文档 (暂停) |
| 8 | DataFlowSegment.driver 类型 | SignalResult | str | ✅ 更新文档 (反映实现) |

---

## 差异详情

### #1: DataFlowSegment.effective_condition

**文档提案**: 未提到此字段

**实际实现**:
```python
@dataclass
class DataFlowSegment:
    from_signal: str
    to_signal: str
    driver: Optional[str] = None
    condition: Optional[str] = None
    effective_condition: Optional[str] = None  # ← 实现独有
    timing: Optional[str] = None
    assign_type: str = "continuous"
    distance: int = 1
```

**说明**: `effective_condition` 是判断清除后的条件，只保留直接相关的条件

**选项**:
- [A] 保留 - 有实际用途
- [B] 删除 - 增加复杂度且文档未规划
- [C] 移到文档 - 更新文档

---

### #2: SignalChain.control_dependencies

**文档提案**: 未提到此字段

**实际实现**:
```python
@dataclass
class SignalChain:
    # ...
    control_dependencies: Dict[str, List[str]] = field(default_factory=dict)  # ← 实现独有
```

**说明**: ControlFlow 支持，存储控制依赖关系

**选项**:
- [A] 保留 - 为 ControlFlow 准备
- [B] 移动到 controlflow_models.py - 分离关注点
- [C] 删除 - 尚未使用

---

### #3: SignalChain.state_transitions

**文档提案**: 未提到此字段

**实际实现**:
```python
@dataclass
class SignalChain:
    # ...
    state_transitions: List[StateTransition] = field(default_factory=list)  # ← 实现独有
```

**说明**: ControlFlow 支持，存储状态机状态转换

**选项**:
- [A] 保留 - 为 ControlFlow 准备
- [B] 移动到 controlflow_models.py - 分离关注点
- [C] 删除 - 尚未使用

---

### #4: DataFlow 相关类分散在两个文件

**现状**:
- `src/trace/core/graph/dataflow.py`: DataFlowGraph, DataFlowSegment, DataFlowPath, DataFlowResult
- `src/trace/core/data_models.py`: SignalChain (增强版，含 paths, conditions 等)

**问题**: 两个文件都包含 DataFlow 相关功能，职责不清晰

**选项**:
- [A] 保持现状 - 两套 API 服务不同场景
- [B] 合并到 dataflow_models.py - 统一管理
- [C] 文档说明分工 - SignalChain 简单场景，DataFlowResult 复杂场景

---

---

## 差异 #2: CONTROL_FLOW_ANALYSIS.md vs controlflow.py

### 文档 vs 实现对比

| 组件 | 文档提案 | 实际实现 | 状态 |
|------|----------|----------|------|
| ControlFlowResult | ✅ | ✅ | 已实现 |
| ConditionInfo | ✅ | ⚠️ 部分在 data_models.py | 分散 |
| StateTransition | ✅ | ✅ (在 controlflow_models.py) | 已实现 |
| ControlFlowGraph | ✅ | ✅ | 已实现 |
| ControlBlock | ❌ | ✅ 独有 | 实现扩展 |
| BranchResult | ❌ | ✅ 独有 | 实现扩展 |
| StateMachineAnalysis | ❌ | ✅ 独有 | 实现扩展 |
| Z3Result | ❌ | ✅ 独有 | 实现扩展 |
| Contradiction/LintWarning | ❌ | ✅ 独有 | 实现扩展 |

### 实现独有的类 (文档未规划)

```python
# controlflow_models.py 中实现独有的类

@dataclass
class ControlBlock:
    """控制块 - 同时包含控制变量和数据变量"""
    file: str = ""
    line: int = 0
    condition_expr: str = ""
    control_vars: List[str] = field(default_factory=list)
    data_vars: List[str] = field(default_factory=list)
    branches: List[Branch] = field(default_factory=list)
    nested_blocks: List['ControlBlock'] = field(default_factory=list)

@dataclass
class BranchResult:
    """分支结果"""
    condition: str = ""
    action: str = ""
    covered: bool = False
    signal_sources: List[str] = field(default_factory=list)

@dataclass
class StateMachineAnalysis:
    """状态机分析结果"""
    name: str = ""
    all_states: List[str] = field(default_factory=list)
    has_deadlock: bool = False
    transitions: List[StateTransition] = field(default_factory=list)


@dataclass
class Z3Result:
    """Z3 求解结果"""
    satisfiable: bool = True
    contradictions: List[Contradiction] = field(default_factory=list)

@dataclass
class Contradiction:
    """矛盾条件"""
    type: str = ""
    expr: str = ""
    reason: str = ""

@dataclass
class LintWarning:
    """代码审查警告"""
    severity: str = "warning"
    rule: str = ""
    message: str = ""
```

### 文档中 ConditionInfo 在 data_models.py

```python
# data_models.py 已有
@dataclass
class ConditionInfo:
    kind: str = ""
    expr: str = ""
    signals: List[str] = field(default_factory=list)
    true_branch: str = ""
    false_branch: Optional[str] = None
    branches: List[str] = field(default_factory=list)
    is_covered: bool = False
    coverage_percentage: float = 0.0
```

### ⚠️ 问题: ConditionInfo 重复定义

| 位置 | 类名 | 说明 |
|------|------|------|
| `data_models.py` | ConditionInfo | DataFlow/ControlFlow 通用 |
| `controlflow_models.py` | (无 ConditionInfo) | 实际只有 StateTransition |

### 选项:
- [A] 合并 ConditionInfo 到 controlflow_models.py - 统一管理
- [B] 保持现状 - 两个模块职责分离
- [C] 文档更新 - 说明分工

---

## 📊 已实现但未在文档规划的功能

### ControlFlow 额外功能

| 功能 | 位置 | 说明 |
|------|------|------|
| ControlBlock | controlflow_models.py | 同时包含控制变量和数据变量 |
| BranchResult | controlflow_models.py | 分支结果 |
| StateMachineAnalysis | controlflow_models.py | 状态机完整分析 |
| Z3Result | controlflow_models.py | Z3 求解结果 |
| Contradiction | controlflow_models.py | 矛盾条件检测 |
| LintWarning | controlflow_models.py | 代码审查警告 |
| ControlFlowGraph | controlflow.py | 基于 NetworkX 的控制流图 |
| ControlFlowNode | controlflow_models.py | 控制流节点 (含 condition/case/state 类型) |
| ControlFlowEdge | controlflow_models.py | 控制流边 (含 COND_TRUE/COND_FALSE/CASE_MATCH) |

---

## 差异 #3: ARCHITECTURE_DEEP_REVIEW.md 建议 vs 未实现

### 文档建议的实际行动

```
| 优先级 | 行动 | 理由 |
|--------|------|------|
| 🔴 P0 | 加强 signal_expression_visitor 测试 | 50+ [NOT TESTED] 是隐患 |
| 🟠 P1 | 拆分 base.py PyslangAdapter | 2050 行太大，职责多 |
| 🟡 P2 | 理清 semantic_adapter vs base.py | 减少重复职责 |
```

### 实际实现状态

| 行动 | 状态 | 说明 |
|------|------|------|
| signal_expression_visitor 测试 | ✅ 部分完成 | 187 个单元测试已添加，仍有 534 个 [NOT TESTED] |
| 拆分 base.py PyslangAdapter | ❌ 不实施 | 决策: 暂停架构重构，当前系统运行稳定 |
| 理清 semantic_adapter vs base.py | ❌ 不实施 | 决策: 暂停架构重构 |

### ✅ 用户决策 (2026-05-31)

**选项 [C]**: 更新文档 - 将 base.py 拆分标记为 deprecated/low priority

**原因**: 当前系统运行稳定 (1080+ 测试通过)，架构问题不影响运行时正确性。

### 更新后的文档

ARCHITECTURE_DEEP_REVIEW.md 已更新，标记 P0/P1 项为 deprecated/not planned。

---

## 差异 #4: DATAFLOW_ANALYSIS_ARCHITECTURE.md vs dataflow.py

### 文档状态: ✅ 已实现 (声称)

### DataFlowSegment 关键差异

| 字段 | 文档提案 | 实际实现 |
|------|----------|----------|
| driver | `SignalResult` (对象) | `Optional[str]` (字符串) |
| condition | `Optional[ConditionInfo]` (对象) | `Optional[str]` (字符串) |
| is_blocking | ✅ 有 | ❌ 无 (用 assign_type 替代) |
| effective_condition | ❌ 未提到 | ✅ 独有 |
| assign_type | ❌ 未提到 | ✅ 独有 |
| distance | ❌ 未提到 | ✅ 独有 |

**文档提案**:
```python
@dataclass
class DataFlowSegment:
    from_signal: str
    to_signal: str
    driver: SignalResult                 # ← SignalResult 对象
    condition: Optional[ConditionInfo]   # ← ConditionInfo 对象
    timing: Optional[str]
    is_blocking: bool                   # ← is_blocking
```

**实际实现**:
```python
@dataclass
class DataFlowSegment:
    from_signal: str
    to_signal: str
    driver: Optional[str] = None         # ← str，不是 SignalResult
    condition: Optional[str] = None      # ← str，不是 ConditionInfo
    effective_condition: Optional[str] = None  # ← 实现独有
    timing: Optional[str] = None
    assign_type: str = "continuous"      # ← assign_type
    distance: int = 1                    # ← 实现独有
```

### DataFlowResult 差异

| 字段 | 文档提案 | 实际实现 |
|------|----------|----------|
| all_conditions | `List[ConditionInfo]` | `List[str]` |
| timing_analysis | ✅ 有 | ✅ 有 (但类型可能不同) |
| 便捷属性 | ✅ 有 | ✅ 有 |

### DataFlowGraph 类 (文档未规划)

| 类 | 文档 | 实际 |
|----|------|------|
| DataFlowAnalyzer | ✅ 文档有 | ❌ 未实现 (只有 DataFlowGraph) |
| DataFlowGraph | ❌ 未规划 | ✅ 实现独有 |

文档描述的是 `DataFlowAnalyzer`，但实际实现的是 `DataFlowGraph`。两者职责相似但名称不同。

### ⚠️ 问题: 类型丢失

```python
# 文档期望
segment.driver.kind_name  # 'BinaryOp', 'Add'
segment.condition.expr    # 'en && valid'

# 实际实现
segment.driver = 'sreg_d'  # 只有字符串，无法知道表达式类型
segment.condition = 'en'    # 只有字符串，无法知道条件结构
```

**影响**: 调用者无法知道驱动表达式的结构（是加法还是乘法？），只能得到原始字符串。

### ✅ 用户决策 (2026-05-31)

**选项 [C]**: 更新文档 - 说明实际使用 str 类型

### 更新内容

DATAFLOW_ANALYSIS_ARCHITECTURE.md 已更新：
- `DataFlowSegment.driver` 类型注明为 `str`
- `DataFlowSegment.condition` 类型注明为 `str`
- 新增字段 `effective_condition`、`assign_type`、`distance` 已记录

---

## 差异 #5: DESIGNER_PLAN.md vs 实际实现

### P0 优先级 - 可信度修复

| 项目 | 文档描述 | 实际状态 |
|------|----------|----------|
| P3-1 Part-Select 驱动边 | ✅ 设计决策 | ✅ 实现 |
| P3-2 字面量作为驱动边 | ✅ 设计决策 | ✅ 实现 |
| P3-5 边信息缺失 | ✅ 已修复 | ✅ 实现 |
| P3-6 驱动语句组装 | ✅ 已修复 | ✅ 实现 |

### P0 优先级 - 重构/ECO影响分析

| 功能 | 文档描述 | 实际状态 |
|------|----------|----------|
| 跨模块追踪完善 | ✅ 已完成 | ✅ 实现 |
| `trace impact` 命令 | ✅ 已完成 | ✅ 实现 (在 trace.py) |
| 条件驱动增强 | 规划中 | ❌ 未实现 |

### P1 优先级 - CDC/时序/面积量化

| 功能 | 文档描述 | 实际状态 |
|------|----------|----------|
| CDC 量化统计表 | ✅ 已完成 | ✅ 实现 |
| Timing 周期估算 | ✅ 已完成 | ✅ 实现 |
| 扇出排行榜 | ✅ 已完成 | ✅ 实现 |

### P2 优先级 - SVA/Coverage 代码生成

| 功能 | 文档描述 | 实际状态 |
|------|----------|----------|
| SVA skeleton 生成 | 待开发 | ❌ 未实现 |
| Covergroup skeleton 生成 | 待开发 | ❌ 未实现 |
| SVA skeleton 命令 | 待开发 | ❌ 未实现 |
| Covergroup skeleton 命令 | 待开发 | ❌ 未实现 |

### P2 优先级 - 可视化增强

| 功能 | 文档描述 | 实际状态 |
|------|----------|----------|
| 模块聚类 | ✅ 已完成 | ✅ 实现 |
| 跨模块边用虚线区分 | ✅ 已完成 | ✅ 实现 |
| rank 约束智能处理 | ✅ 已完成 | ✅ 实现 |
| neato 力导向布局 | 待开发 | ❌ 未实现 |
| 高风险区域聚焦模式 | 待开发 | ❌ 未实现 |
| 分层切图 | 待开发 | ❌ 未实现 |
| SVG/HTML 交互式缩放 | 待开发 | ❌ 未实现 |
| CI 集成模板 | 待开发 | ❌ 未实现 |
| 设计工程师文档 | 待开发 | ❌ 未实现 |

### ✅ 用户决策 (2026-05-31)

**选项 [B]**: 暂停开发，更新文档

### 更新内容

DESIGNER_PLAN.md 已更新：
- SVA skeleton 生成 → 移至 Future Roadmap
- Covergroup skeleton 生成 → 移至 Future Roadmap
- 其他未实现项 → 标记为 deferred

---

## 差异 #6: ARCHITECTURE_IMPROVEMENT.md - 重构提案未实施

### 文档状态: 待实施

### 提案的核心改进

| 改进项 | 文档描述 | 实际状态 |
|--------|----------|----------|
| 单一结果类型 SignalResult | ✅ 提案 | ❌ 未实现 (仍是 visit()/get_all_signals() 双接口) |
| 注册式分派 @on() 装饰器 | ✅ 提案 | ❌ 未实现 (仍是 if/elif 分派) |
| 单个 Handler 替代双 handler | ✅ 提案 | ❌ 未实现 (仍需 visit + get_all) |
| 别名映射统一 | ✅ 提案 | ❌ 未实现 (alias_map 仍在多处) |
| 移除 fallback | ✅ 提案 | ❌ 未实现 (generic_visit() 仍在) |

### 当前架构 (实际)

```python
# 仍然使用双接口 + if/elif 分派
class SignalExpressionVisitor:
    def visit(self, node) -> Optional[str]:
        # if/elif 分派
        if kind_name == 'BinaryOp':
            return self.visit_binary_expression(node)
        # ... 其他类型
        return self.generic_visit(node)  # ← fallback 仍在
    
    def get_all_signals(self, node) -> List[str]:
        # 另一个双接口方法
        pass
```

### SignalResult 类 (文档提案)

```python
@dataclass(frozen=True)
class SignalResult:
    primary: Optional[str]
    all_signals: List[str]
    all_signals_unique: List[str]
    # 单一类型替代双接口
```

### ✅ 用户决策 (2026-05-31)

**选项 [C]**: 更新文档 - 将重构提案标记为 deprecated/low priority

### 更新内容

ARCHITECTURE_IMPROVEMENT.md 已更新：
- 状态改为 "暂停实施"
- 原因: 当前架构已足够使用，双接口模式工作正常
- v6 单dispatch架构 → 标记为 future consideration

---

## 差异 #7: CONTROL_FLOW_DESIGN.md vs 实际实现

### 文档状态: 设计阶段

### 文档描述的核心组件

| 组件 | 文档提案 | 实际状态 |
|------|----------|----------|
| ControlFlowGraph | ✅ 需实现 | ✅ 已实现 |
| ControlFlowAnalyzer | ✅ 需实现 | ❌ 未实现 |
| Z3 Solver | ✅ 需实现 | ❌ 未实现 |
| ControlFlowResult | ✅ 需实现 | ✅ 已实现 (在 controlflow_models.py) |
| ControlBlock (交叉定位) | ✅ 需实现 | ✅ 已实现 |

### ControlFlowAnalyzer 类 (文档提案)

```python
class ControlFlowAnalyzer:
    def analyze(
        self,
        control_var: str,      # 控制变量 (en)
        data_var: str,          # 数据变量 (q)
        module: str = None,
    ) -> ControlFlowResult:
        """分析 control_var 如何控制 data_var 的数据流"""
        pass

    def find_control_blocks(
        self,
        control_var: str,
        data_var: str,
    ) -> List[ControlBlock]:
        """找到同时包含 control_var 和 data_var 的控制块"""
        pass
```

**实际**: `ControlFlowAnalyzer` 类不存在，只有 `ControlFlowGraph` 类。

### Z3 Solver (文档提案)

```python
class Z3Solver:
    def check_satisfiability(self, conditions: List[str]) -> bool:
        """检查条件是否可满足"""
        pass

    def find_conflicts(self, conditions: List[str]) -> List[Contradiction]:
        """找矛盾条件"""
        pass
```

**实际**: `Z3Solver` 类不存在。

### ControlFlowGraph (实际实现)

```python
class ControlFlowGraph:
    def __init__(self, module_name: str = ""):
        self.graph = nx.DiGraph()
        self.nodes: Dict[str, ControlFlowNode] = {}
        self.edges: Dict[str, ControlFlowEdge] = {}
        # ...
```

**已实现的功能**:
- 节点/边管理 (add_node, add_edge, get_node)
- 条件依赖追踪 (get_condition_dependencies, get_condition_vars)
- NetworkX 图集成

**未实现的功能**:
- ControlFlowAnalyzer 类
- Z3 Solver 集成
- 死锁检测 (has_deadlock 属性存在，但无实际检测逻辑)

### 选项
- [A] 实现 ControlFlowAnalyzer - 按文档设计实现
- [B] 保持现状 - 当前 ControlFlowGraph 已足够
- [C] 更新文档 - 将 ControlFlowAnalyzer/Z3 标记为 future roadmap

---

## 差异 #8: PENDING_FEATURES.md vs 实际实现

### 文档状态: 需更新 (2026-05-26)

### 关键功能状态对比

| 功能 | 文档描述 | 实际状态 | 需更新 |
|------|----------|----------|--------|
| ControlFlow 控制流分析 | ✅ 已完成 | ⚠️ 部分 - ControlFlowGraph 有, ControlFlowAnalyzer 无 | ✅ |
| Interface/modport 追踪 | ✅ 已完成 | ✅ 已实现 | 无需 |
| Function/Task 内联展开 | ✅ 已完成 | ✅ 81 tests | 无需 |
| Generate block 追踪 | ✅ 已完成 | ✅ 26 tests | 无需 |
| 跨时钟域路径分析 | ✅ 已完成 | ✅ DataFlow 已支持 | 无需 |
| Class 实例化成员追踪 | ✅ 已完成 | ✅ MEMBER_SELECT | 无需 |
| SignalExpressionVisitor 单 dispatch | 讨论中 | ⏸️ 暂停 | ✅ |
| Visitor 组合模式 | P3 | 未开始 | 无需 |
| StatementCollectorVisitor 对齐 | P3 | 未开始 | 无需 |

### ControlFlow 详细差异

| 组件 | 文档描述 | 实际状态 |
|------|----------|----------|
| ControlFlowGraph | 需要实现 | ✅ 已实现 |
| ControlFlowAnalyzer | 需要实现 | ❌ 未实现 |
| Z3 Solver | 需要实现 | ❌ 未实现 |
| 条件使能分析 | 目标功能 | ❌ 未实现 |
| 分支覆盖分析 | 目标功能 | ❌ 未实现 |

### SignalExpressionVisitor 单 dispatch

| 状态 | 说明 |
|------|------|
| 原文档 | 讨论中，建议在有明确扩展需求时进行 |
| 实际状态 | ⏸️ 暂停实施 (2026-05-31 决策) |

---

## 差异 #9: CDC_ANALYSIS.md vs cdc_analyzer.py

### 文档状态: 部分过时

### 文档描述 vs 实际实现

| 功能 | 文档描述 | 实际实现 |
|------|----------|----------|
| 时钟域识别 | 简化方法 | ✅ 完整实现 |
| 域传播 BFS | 简化方法 | ✅ 完整实现 (CLOCK 边传播) |
| CDC 路径检测 | 简单检测 | ✅ 完整实现 |
| 同步器识别 | 简化 (信号名含 sync) | ✅ 升级 - 2-FLOP/3-FLOP 结构识别 |
| sync_type | ❌ 未提到 | ✅ 已实现 (NONE, 2-FLOP, 3-FLOP 等) |
| sync_flops | ❌ 未提到 | ✅ 已实现 |
| domain_pairs | ❌ 未提到 | ✅ 已实现 |
| high_risk_paths | ❌ 未提到 | ✅ 已实现 |
| timing_report | ❌ 未提到 | ✅ 已实现 |

### 实际实现的功能 (CDCAnalyzer)

```python
class CDCAnalyzer:
    def identify_clock_domains(self) -> Dict[str, Set[str]]
    def assign_domains(self) -> Dict[str, str]
    def analyze_cdc(self) -> CDCReport
    def timing_report(self) -> str  # 新增
```

**CDCReport 包含**:
- `sync_type`: 同步器类型 (NONE, 2-FLOP, 3-FLOP)
- `sync_flops`: 寄存器链长度
- `sync_type_stats`: 各类型路径数量统计
- `domain_pairs`: 跨时钟域路径分组统计
- `high_risk_paths`: 高风险 CDC 路径列表

### ✅ 用户决策

**选项**: 更新 CDC_ANALYSIS.md 反映实际实现

---

## 差异 #10: ARCHITECTURE.md (核心架构文档)

### 文档状态: 基本准确

### 核心组件对照

| 组件 | 文档描述 | 实际状态 |
|------|----------|----------|
| UnifiedTracer | 统一入口 | ✅ 已实现 |
| GraphBuilder | Module 级构建 | ✅ 已实现 |
| ClassGraphBuilder | Class 级构建 | ✅ 已实现 |
| SignalGraph | NetworkX 图 | ✅ 已实现 |
| DataFlowGraph | 数据流分析 | ✅ 已实现 |
| SignalExpressionVisitor | 表达式→信号 | ✅ 已实现 (7341行) |
| StatementCollectorVisitor | 语句收集 | ✅ 已实现 |
| SubroutineExpander | 函数内联展开 | ✅ 已实现 |

### 新增组件 (文档未覆盖)

| 组件 | 实际实现 | 说明 |
|------|----------|------|
| ControlFlowGraph | ✅ | 控制流图 |
| ModuleInstanceGraph | ✅ | 模块实例图 |
| CovergroupExtractor | ✅ | Covergroup 提取 |
| SVAExtractor | ✅ | SVA 提取 |

### ⚠️ 可能需要更新

ARCHITECTURE.md 的分层架构图可能需要更新以反映新增的组件。

---

## 差异 #11: TODO.md vs 实际状态

### 文档状态: 部分过时

### SignalExpressionVisitor 单 dispatch 重构

| 状态 | 说明 |
|------|------|
| 原文档 | 描述为 P2 可选优化，建议有明确扩展需求时进行 |
| 实际状态 | ⏸️ 暂停实施 (2026-05-31 决策) |
| 参考 | ARCHITECTURE_IMPROVEMENT.md 状态已更新 |

### ControlFlow 控制流分析

| 状态 | 说明 |
|------|------|
| 原文档 | 描述为"待实现"，功能目标包含条件使能、分支覆盖、状态机 |
| 实际状态 | ✅ 部分完成 - ControlFlowGraph 已实现 (17 测试通过) |
| 未完成 | ControlFlowAnalyzer、Z3 Solver 未实现 |

---

## 差异 #12: KNOWN_LIMITATIONS.md vs 实际状态

### 文档状态: 基本准确

所有失败测试已修复，996+ 测试通过。无需更新。

---

## 差异 #13: TIMING_ANALYSIS.md vs timing_analyzer.py

### 文档状态: ✅ 基本准确

### 文档描述 vs 实际实现

| 功能 | 文档描述 | 实际实现 |
|------|----------|----------|
| 寄存器级图构建 | ✅ | ✅ |
| 寄存器深度估计 | ✅ | ✅ |
| SCC 缩点 | ✅ | ✅ |
| DAG 最长路径 | ✅ | ✅ |
| 关键路径输出 | ✅ | ✅ |
| cycle_estimate | ❌ 未提到 | ✅ 已实现 |
| combo_delay_estimate | ❌ 未提到 | ✅ 已实现 |
| risk_level | ❌ 未提到 | ✅ 已实现 (CRITICAL/HIGH/MEDIUM/LOW) |
| violation_risk | ❌ 未提到 | ✅ 已实现 |

### TimingAnalyzer 增强功能 (2026-05-30)

```python
class TimingAnalyzer:
    def analyze(self) -> Dict:
        # 包含:
        # - cycle_estimate: 预估时钟周期数
        # - combo_delay_estimate: 组合逻辑延迟
        # - risk_level: 时序风险 (CRITICAL/HIGH/MEDIUM/LOW)
        # - violation_risk: 时序违例风险
```

### ✅ 用户决策

**选项**: 可选更新 - 添加增强功能说明到 TIMING_ANALYSIS.md

---

## 📋 已完成的文档差异分析

| # | 文档 | 状态 | 行动 |
|---|------|------|------|
| 1 | FINAL_SCHEMA_DECISION.md | ✅ 已实现 | 无需操作 |
| 2 | SCHEMA_COMPARISON_V2.md | ✅ 已分析 | 无需操作 |
| 3 | CONTROL_FLOW_ANALYSIS.md | ✅ 已实现 | 无需操作 |
| 4 | ARCHITECTURE_DEEP_REVIEW.md | ❌ 不实施 | ✅ 已更新文档 |
| 5 | DATAFLOW_ANALYSIS_ARCHITECTURE.md | ✅ 已实现 | ✅ 已更新文档 |
| 6 | DESIGNER_PLAN.md | ⚠️ 部分完成 | ✅ 已更新文档 |
| 7 | ARCHITECTURE_IMPROVEMENT.md | ❌ 暂停 | ✅ 已更新文档 |
| 8 | CONTROL_FLOW_DESIGN.md | ⚠️ 部分实现 | 无需操作 |
| 9 | PENDING_FEATURES.md | ⚠️ 需更新 | 待处理 |
| 10 | CDC_ANALYSIS.md | ⚠️ 部分过时 | ✅ 已更新 |
| 11 | ARCHITECTURE.md | ✅ 基本准确 | 无需操作 |
| 12 | TODO.md | ⚠️ 部分过时 | ✅ 已更新差异 |
| 13 | KNOWN_LIMITATIONS.md | ✅ 准确 | 无需操作 |
| 14 | TIMING_ANALYSIS.md | ✅ 基本准确 | 无需操作 |

---

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-31 | 创建差异记录文档 |
| 2026-05-31 | 添加 CONTROL_FLOW_ANALYSIS.md 差异 |
| 2026-05-31 | 添加 ARCHITECTURE_DEEP_REVIEW.md 差异 |
| 2026-05-31 | 添加 DATAFLOW_ANALYSIS_ARCHITECTURE.md 差异 |
| 2026-05-31 | 添加 DESIGNER_PLAN.md 差异 |
| 2026-05-31 | 添加 ARCHITECTURE_IMPROVEMENT.md 差异 |
| 2026-05-31 | 添加 CONTROL_FLOW_DESIGN.md 差异 |
| 2026-05-31 | 添加 PENDING_FEATURES.md 差异 |
| 2026-05-31 | 添加 CDC_ANALYSIS.md 差异 |
| 2026-05-31 | 添加 ARCHITECTURE.md 差异 |
| 2026-05-31 | 添加 TODO.md 差异 |
| 2026-05-31 | 添加 KNOWN_LIMITATIONS.md 差异 |
| 2026-05-31 | 添加 TIMING_ANALYSIS.md 差异 |
| 2026-05-31 | ✅ 更新 ARCHITECTURE_DEEP_REVIEW.md - P0/P1 标记为 deprecated |
| 2026-05-31 | ✅ 更新 DATAFLOW_ANALYSIS_ARCHITECTURE.md - 反映实际 str 类型 |
| 2026-05-31 | ✅ 更新 DESIGNER_PLAN.md - SVA/Coverage 移至 future roadmap |
| 2026-05-31 | ✅ 更新 ARCHITECTURE_IMPROVEMENT.md - 标记为暂停实施 |
| 2026-05-31 | ✅ 更新 CDC_ANALYSIS.md - 反映 CDCAnalyzer 实际功能 | | | | |