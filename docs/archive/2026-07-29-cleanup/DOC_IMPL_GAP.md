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
| 15 | DATAFLOW_IMPLEMENTATION_PLAN.md | ✅ 基本准确 | 无需操作 |

---

## 新增差异条目 (2026-05-31 下午)

### 差异 #16: CONTROL_FLOW_IMPROVEMENTS.md vs 实际实现

| 问题 | 文档描述 | 实际状态 |
|------|----------|----------|
| 嵌套三元条件 | 方案 A/B 提案 | ✅ `get_signals_with_conditions` 已实现 (line 6534) |
| Case selector 为空 | 方案 A/B 提案 | ✅ `_get_case_selector` 已支持 IdentifierNameSyntax (line 1161) |

### 差异 #17: CODE_DISCIPLINE_REVIEW.md vs 实际状态

| 项目 | 状态 | 说明 |
|------|------|------|
| 铁律遵守率 | ✅ 95%+ | 无重大违反 |
| graph_builder.py if-elif | ✅ 已优化 | StatementVisitor 处理 |

### 差异 #18: GRAPH_CATALOG.md vs 实际实现

| 图类型 | 文档描述 | 实际状态 |
|--------|----------|----------|
| SignalGraph | ✅ | ✅ |
| ClassGraph | ✅ | ✅ |
| CovergroupGraph | ✅ | ✅ |
| CallGraph | ✅ | ✅ |
| UVMTestbenchGraph | ✅ | ✅ |
| SVA 图 | 待实现 | ✅ 已实现 (sva_models.py) |

### 新增组件 (文档未明确标注)

| 组件 | 实际实现 | 说明 |
|------|----------|------|
| ControlFlowGraph | ✅ | 控制流图 |
| DataFlowGraph | ✅ | 数据流分析图 |
| Analyzer 子包 | ✅ | cdc_analyzer, timing_analyzer |

---

### 差异 #19: DESIGN_COVERGROUP_EXTRACTION.md vs 实际实现

| 组件 | 文档描述 | 实际状态 |
|------|----------|----------|
| CovergroupInfo | ✅ | ✅ 已实现 |
| CoverpointInfo | ✅ | ✅ 已实现 |
| BinsInfo | ✅ | ✅ 已实现 |
| CovergroupExtractor | ✅ | ✅ 已实现 |

### 差异 #20: ARCHITECTURE_EVOLUTION.md vs 实际状态

| 阶段 | 文档描述 | 实际状态 |
|------|----------|----------|
| 阶段 7: TraversalStrategy 抽象 | 待解决 | ❌ 未实现 |
| 阶段 7: NodeAccessor 抽象 | 待解决 | ❌ 未实现 |
| Handler 简化 | 待解决 | ❌ 未实现 |

---

### 差异 #21: PROJECT_PLAN.md vs 实际状态

### 文档状态: ⚠️ 部分过时

| 项目 | 文档描述 | 实际状态 |
|------|----------|----------|
| 测试数量 | 996 passed | ✅ 1267 passed |
| 测试状态 | 996 passed, 0 failed | ✅ 1267 passed, 0 failed |
| 项目列表 | OpenTitan 176题 | ✅ 已完成，其他进行中 |

---

### 差异 #22: INDEX.md vs 实际文档状态

### 文档状态: 基本准确 ✅

INDEX.md 是入口文档，分类正确。实际文档都已存在。

---

### 差异 #23: REQUIREMENT_SVA_ANALYSIS.md vs sva_extractor.py

### 文档状态: ✅ 基本准确

| 组件 | 文档描述 | 实际状态 |
|------|----------|----------|
| SVAExtractor | 需实现 | ✅ 已实现 |
| SVAReport | 需实现 | ✅ 已有数据结构 |
| Sequence/Property/Assert 提取 | 需实现 | ✅ 已实现 |
| signal_assertion_map | 需实现 | ✅ 已有 |

**文件**: `src/trace/core/sva_extractor.py` (20929 bytes, 2026-05-29)

---

### 差异 #24: REQ5_6_7_8_DRIVER_LOAD_ANALYSIS.md vs 实际状态

### 文档状态: ⚠️ 部分过时

| Req | 文档描述 | 实际状态 |
|------|----------|----------|
| Req-5 generate 内实例 | 需增强 | ✅ `get_generate_instances()` 已实现 |
| Req-6 函数内部逻辑 | 需新增 FunctionExtractor | ✅ `SubroutineExpander` 已实现 |
| Req-7 always block 语句 | 需增强 | ✅ DriverExtractor 已处理 |
| Req-8 SignalTracer | 依赖上述 | ✅ 已实现 |

### 关键实现

- `SubroutineExpander` (line 2474) - 函数展开器
- `get_generate_instances()` (line 2084, 2108) - generate 实例支持
- `_get_generate_block_name()` (line 2017-2018) - generate block 命名

---

### 差异 #25: REFACTOR_GUIDE_v2.md vs 实际状态

### 文档状态: ⚠️ 部分过时

| 变化点 | 文档描述 (v2.0) | 实际状态 |
|--------|-----------------|----------|
| RTL 数据源 | slang-netlist NetlistGraph | ❌ 未使用，仍用 pyslang |
| 图结构位精确化 | Phase 2 | ⚠️ 简化实现 |
| Visitor 目录 | 删 statement+assignment | ⚠️ 都保留了 |
| DFA 能力 | 等待 slang-netlist bug 修复 | ❌ 未使用 slang-netlist |

### 实际实现

- 使用 pyslang Semantic AST (Compilation + getRoot())
- 不使用 slang-netlist
- GraphBuilder 整合多个 extractor

---

### 差异 #26: SIGNAL_EXPRESSION_VISITOR_TEST_STATUS.md vs 实际状态

### 文档状态: ✅ 准确 (今天更新)

本文档是我今天创建的状态报告，反映实际测试情况：
- 187 tests 新增
- 534 个 [NOT TESTED] 方法
- 5 个测试文件

---

### 差异 #27: ISSUES_SUMMARY.md vs 实际状态

### 文档状态: ⚠️ 部分过时 (2026-05-18)

大部分 Issue 已修复或标记为 design constraint：
- Issue 21 ✅ 已修复
- Issue 22 ✅ 已修复
- Issue 27 ✅ 已修复
- Issue 28 ✅ 已修复
- Issue 33 ✅ 已修复
- Issue 36 ✅ 已修复
- Issue 43 ✅ 已修复

| Issue | 状态 |
|-------|------|
| Issue 17-43 | 大部分已处理 |
| 新 Issue 44+ | 需查看 OPENCHIP_QA_ROUND4_REPORT |

---

### 差异 #28: README.md vs 实际状态

### 文档状态: ✅ 基本准确

README.md 与 PROJECT_PLAN.md 内容类似，都描述项目总览。当前测试数 1267，项目列表基本准确。

---

### 差异 #29: OPENCHIP_QA_ROUND4_REPORT.md + ROUND4_ISSUES.md vs 实际状态

### 文档状态: ✅ 已处理

Round 4 报告和 Issue 汇总中的问题已在 ISSUES_SUMMARY.md 中跟踪：
- Issue 17-20 ✅ 已处理
- 新问题 21-43 ✅ 大部分已修复或标记为 design constraint

---

### 差异 #30: HANDLER_WRITING_GUIDE.md + DESIGN_BOUNDARY_CONTROL.md

### 文档状态: ⚠️ 描述提案，未实施

| 文档 | 描述 | 实际状态 |
|------|------|----------|
| HANDLER_WRITING_GUIDE.md | 单dispatch + @on() 装饰器 | ❌ 未实施 (仍用双接口) |
| DESIGN_BOUNDARY_CONTROL.md | VisitAction.Skip 边界控制 | ❌ 未实施 |

与 ARCHITECTURE_IMPROVEMENT.md 的单dispatch提案相同 - 已标记为暂停。

---

### 差异 #31: REFACTOR_DETAILED_PLAN.md + PROPOSAL_REFLECTION_BASED_HANDLER.md + SIGNAL_GRAPH_ANALYSIS_REQUIREMENTS.md

### 文档状态: ⚠️ 都是提案，未实施

| 文档 | 描述 | 实际状态 |
|------|------|----------|
| SIGNAL_GRAPH_ANALYSIS_REQUIREMENTS.md | 需求讨论，基于 pyslang.visit() + VisitAction.Skip | ❌ 未实施 |
| REFACTOR_DETAILED_PLAN.md | 单dispatch重构细化方案 | ❌ 未实施 |
| PROPOSAL_REFLECTION_BASED_HANDLER.md | 反射 @on Handler 提案 | ❌ 未实施 |

这些都涉及 SignalExpressionVisitor 的重构，已在 ARCHITECTURE_IMPROVEMENT.md 中标记为暂停。

---

## 📋 已完成的文档差异分析 (共31个)

| # | 文档 | 状态 |
|---|------|------|
| 1-30 | (之前) | 略 |
| 31 | REFACTOR + PROPOSAL + SIGNAL_GRAPH_ANALYSIS requirements | ⚠️ 提案未实施 |

---

### 差异 #32: RISK_ANALYSIS.md vs signal_graph_viewer.py

### 文档状态: ⚠️ 部分过时

| 公式 | 文档描述 | 实际状态 |
|------|----------|----------|
| 功能逻辑复杂度 | 完整公式含 width×0.3, 无SVA/无Cov 惩罚 | 简化: fan_in×3 + fan_out×2 + 15(汇聚) + 10(发散) |
| 时序复杂度 | 含 pipeline_depth×5, 无SVA 惩罚 | 简化: 15(寄存器) + fan_in×2 |

**实际实现** (signal_graph_viewer.py line 158-188): 简化版风险评分

---

## 📋 已完成的文档差异分析 (共32个)

| # | 文档 | 状态 |
|---|------|------|
| 1-31 | (之前) | 略 |
| 32 | RISK_ANALYSIS.md | ⚠️ 公式过于复杂，实际简化实现 |

---

### 差异 #33: SIGNAL_QUERY_IMPROVEMENT_PLAN.md vs 实际状态

### 文档状态: ✅ 基本准确

P0-1 (Condition 提取) 和 P0-2 (Driver Expression 提取) 已完成，文档准确。

---

## 📋 已完成的文档差异分析 (共33个)

| # | 文档 | 状态 |
|---|------|------|
| 1-32 | (之前) | 略 |
| 33 | SIGNAL_QUERY_IMPROVEMENT_PLAN.md | ✅ 基本准确 (P0-1/P0-2 已完成) |

---

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-31 | ... (前32个文档) ... |
| 2026-05-31 | 添加 33 号文档差异 (SIGNAL_QUERY_IMPROVEMENT_PLAN) |
| 2026-05-31 | 已分析 33 个文档，还有约 34 个待分析 |
### 差异 #34: DISCIPLINE_VIOLATIONS.md vs 实际状态

### 文档状态: ✅ 已修复

| 问题 | 文档描述 | 实际状态 |
|------|----------|----------|
| CovergroupInfo.errors 字段 | 待补充 | ✅ 已添加 (covergroup_models.py:46) |
| UVMTestbench.errors 字段 | 待补充 | ✅ 已添加 (uvm_models.py:62) |

---

## 📋 已完成的文档差异分析 (共34个)

| # | 文档 | 状态 |
|---|------|------|
| 1-33 | (之前) | 略 |
| 34 | DISCIPLINE_VIOLATIONS.md | ✅ 已修复 |

---

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-31 | ... (前33个文档) ... |
| 2026-05-31 | 添加 34 号文档差异 (DISCIPLINE_VIOLATIONS.md) |
| 2026-05-31 | 已分析 34 个文档 |

### 差异 #35: GRAPH_BUILDER_REVIEW.md vs 实际状态

### 文档状态: ✅ 准确

| Class | 文档描述 | 实际行数 |
|-------|----------|----------|
| DriverExtractor | 🔴 1554行，真正的巨无霸 | ✅ 1554行 (line 25开始) |
| GraphBuilder | 🟢 370行，正常 | ✅ 370行 |
| LoadExtractor | 🟡 409行，可接受 | ✅ 409行 (line 1579) |
| ConnectionExtractor | 🟡 402行，可接受 | ✅ 402行 (line 1988) |

文档准确。结论：不需要拆分 GraphBuilder。

---

## 📋 已完成的文档差异分析 (共35个)

| # | 文档 | 状态 |
|---|------|------|
| 1-34 | (之前) | 略 |
| 35 | GRAPH_BUILDER_REVIEW.md | ✅ 准确 |

---

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-31 | ... (前34个文档) ... |
| 2026-05-31 | 添加 35 号文档差异 (GRAPH_BUILDER_REVIEW.md) |
| 2026-05-31 | 已分析 35 个文档 |

---

# 📊 代码与文档同步状态 (2026-06-01)

## 总体状态

| 维度 | 状态 |
|------|------|
| 代码测试 | ✅ 1265 通过, 0 失败, 1 跳过 |
| 文档总数 | 67 个 (.md) |
| 已分析文档 | 35 个 |
| 待分析文档 | ~32 个 (主要在 architecture/ 子目录) |
| Git commits ahead | 5 个待推送 |

## ⚠️ 未文档化的新功能 (2026-05-31 ~ 2026-06-01 新增)

### 1. filelist 完整支持 (compiler.py)

| 特性 | 实现位置 | 文档记录 |
|------|----------|----------|
| `+incdir+PATH` | add_filelist | ❌ 未文档化 |
| `-F/-f FILELIST` 嵌套 | add_filelist | ❌ 未文档化 |
| `${VAR}` / `$VAR` 环境变量 | _expand_env | ❌ 未文档化 |
| `+define+VAR=VAL` 宏定义 | add_filelist | ❌ 未文档化 |
| `+libext+EXT` (跳过) | add_filelist | ❌ 未文档化 |
| 循环引用保护 | already_loaded | ❌ 未文档化 |

**应更新**: `docs/README.md` (可视化章节) + 新建 `docs/FILELIST.md`

### 2. CLI 新选项 (visualize.py)

| 选项 | 用途 | 文档记录 |
|------|------|----------|
| `--include / -I` | include 搜索路径 (逗号分隔) | ❌ 未文档化 |
| `--filelist` | Verilator 风格 filelist | ❌ 未文档化 |

**应更新**: `docs/README.md`

### 3. UnifiedTracer 新参数 (unified_tracer.py)

| 参数 | 用途 | 文档记录 |
|------|------|----------|
| `include_dirs` | include 搜索路径列表 | ❌ 未文档化 |

**应更新**: `docs/ARCHITECTURE.md`, `docs/USER_GUIDE.md`

### 4. 容错处理 (semantic_adapter.py)

| 改动 | 目的 | 文档记录 |
|------|------|----------|
| UnicodeDecodeError 防护 | CVA6 触发的 pyslang bug | ❌ 未文档化 |
| 占位符 `_inst_`, `_bad_`, `_unknown_` | 优雅降级 | ❌ 未文档化 |

**应更新**: `docs/DISCIPLINE_VIOLATIONS.md`, `docs/CODE_DISCIPLINE_REVIEW.md`

### 5. 可视化改进 (signal_graph_viewer.py)

| 改动 | 目的 | 文档记录 |
|------|------|----------|
| `size=10` | 正方形布局 | ✅ 已记录 (README.md) |
| `ratio=compress` | 不裁剪压缩布局 | ✅ 已记录 (README.md) |

## 📊 同步矩阵

| 类别 | 代码 | 文档 | 状态 |
|------|------|------|------|
| 核心架构 | ✅ | ✅ | 同步 |
| 数据流 | ✅ | ✅ | 同步 |
| 控制流 | ✅ | ⚠️ | 部分同步 |
| CDC | ✅ | ✅ | 同步 |
| Timing | ✅ | ✅ | 同步 |
| SVA | ✅ | ✅ | 同步 |
| Covergroup | ✅ | ✅ | 同步 |
| Class Graph | ✅ | ✅ | 同步 |
| Call Graph | ✅ | ✅ | 同步 |
| UVM | ✅ | ✅ | 同步 |
| 验证问题 | ✅ | ✅ | 同步 |
| **filelist 支持** | ✅ | ❌ | **未同步** |
| **CLI 新选项** | ✅ | ❌ | **未同步** |
| **Unicode 容错** | ✅ | ❌ | **未同步** |
| 可视化正方形 | ✅ | ✅ | 同步 |
| 测试数 (1265) | ✅ | ⚠️ | 部分同步 (PROJECT_PLAN 写的 996) |

## 🎯 建议的文档更新

### 优先级 P0 (核心功能)

1. **新建 `docs/FILELIST.md`** - 完整 filelist 格式文档
2. **更新 `docs/README.md`** - 添加 `--include` / `--filelist` 选项
3. **更新 `docs/PROJECT_PLAN.md`** - 测试数 996 → 1265
4. **更新 `docs/USER_GUIDE.md`** - 添加 CLI 章节

### 优先级 P1

5. **更新 `docs/ARCHITECTURE.md`** - mention `include_dirs` 参数
6. **更新 `docs/DISCIPLINE_VIOLATIONS.md`** - 添加 UnicodeDecodeError 处理
7. **更新 `docs/SIGNAL_GRAPH_ANALYSIS_REQUIREMENTS.md`** - 反映 CVA6 经验

### 优先级 P2

8. 重新分析剩余 32 个文档
9. 同步 visualization/architecture 子目录
10. 添加 CVA6 等工业项目适配指南

## 📝 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-31 | 第一波分析 (35 个文档) |
| 2026-06-01 | 添加 5 个新 commit (filelist/CLI/Unicode 防护/可视化) |
| 2026-06-01 | **代码领先文档 5 个新功能** |
