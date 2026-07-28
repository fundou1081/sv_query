# 控制流分析架构提案

> 创建时间: 2026-05-24
> 状态: 已实现 (DataFlow + ControlFlow 均已完成)
> 测试: 17 个 controlflow 测试全部通过
> 相关文档: `DATAFLOW_ANALYSIS_ARCHITECTURE.md`, `ARCHITECTURE_COMPARISON.md`

---

## 一、控制流 vs 数据流 - 基本区别

| 维度 | 数据流 (Data Flow) | 控制流 (Control Flow) |
|------|-------------------|---------------------|
| 关注点 | 信号如何传递 | 逻辑执行顺序和条件 |
| 核心问题 | A → B → C 的路径是什么？ | 在什么条件下数据流动？ |
| 答案 | 管道深度、延迟、驱动关系 | if/case 条件、分支覆盖、状态机 |
| 典型输出 | DataFlowResult | ControlFlowResult |

```
数据流:  data_in → stage1 → stage2 → data_out
控制流:  if (en) stage1 <= data_in; if (valid) stage2 <= stage1;
完整分析: en && valid 时数据才流动
```

---

## 二、典型场景

### 2.1 条件使能分析

```systemverilog
always_ff @(posedge clk) begin
    if (en) q <= d;
end
```

**控制流问题**:
- en 为真时数据流动
- en 为假时 q 保持
- en 的来源是什么？

### 2.2 多路选择分析

```systemverilog
always_comb begin
    case (sel)
        0: out = a;
        1: out = b;
        default: out = 0;
    endcase
end
```

**控制流问题**:
- sel=0/1/default 时的数据路径
- 条件覆盖是否完整？
- default 是否必要？

### 2.3 状态机分析

```systemverilog
always_ff @(posedge clk) begin
    case (state)
        IDLE: if (start) state <= RUN;
        RUN: if (done) state <= IDLE;
        default: state <= IDLE;
    endcase
end
```

**控制流问题**:
- 状态转换条件
- 状态覆盖路径
- default 状态是否必要？

### 2.4 控制依赖链

```systemverilog
if (a && b) q <= d;
```

**控制流问题**:
- a 和 b 的控制关系
- 哪个是主要使能信号？
- 控制依赖链: a → en, b → en, en → q

---

## 三、现有系统支持

### 3.1 已有能力

| 组件 | 支持的控制流功能 |
|------|-----------------|
| SignalExpressionVisitor | 条件表达式信号提取 |
| StatementCollectorVisitor | if/case/conditional 语句收集 |
| TraceEdge.condition | 边的条件信息 |

### 3.2 缺失能力

| 缺失 | 影响 |
|------|------|
| 条件分支完整路径 (if → else) | 无法分析完整条件覆盖 |
| 条件覆盖分析 | 无法知道哪些分支没覆盖 |
| 状态机状态转换图 | 无法分析状态机控制流 |
| 控制流与数据流关联 | 数据流不知道执行条件 |

---

## 四、控制流分析的数据结构

### 4.1 ConditionInfo (条件信息)

```python
@dataclass
class ConditionInfo:
    """条件信息"""
    
    # 基本信息
    kind: str               # 'if', 'case', 'conditional_op'
    expr: str               # 条件表达式原文
    signals: List[str]       # 条件涉及的信号
    
    # 分支信息
    true_branch: str        # 为真时的值/语句
    false_branch: Optional[str]  # 为假时的值/语句 (if)
    branches: Optional[List[str]]  # case 分支列表
    
    # 覆盖信息
    is_covered: bool = False
    coverage_percentage: float = 0.0
    
    # 来源信息
    source_file: str = ""
    source_line: int = 0
    block_kind: str = ""     # 'always_ff', 'always_comb', 'assign'
```

### 4.2 StateTransition (状态转换)

```python
@dataclass
class StateTransition:
    """状态机状态转换"""
    
    from_state: str          # 源状态
    to_state: str            # 目标状态
    condition: str           # 转换条件
    signals: List[str]      # 条件涉及的信号
    
    # 覆盖信息
    is_covered: bool = False
    transition_probability: float = 0.0
```

### 4.3 ControlFlowResult (控制流结果)

```python
@dataclass
class ControlFlowResult:
    """控制流分析结果"""
    
    from_signal: str
    to_signal: str
    
    # 控制条件
    conditions: List[ConditionInfo]  # 路径中的所有条件
    
    # 路径条件
    path_conditions: List[str]  # 路径条件表达式列表
    combined_condition: Optional[str]  # 组合条件 (A && B && ...)
    
    # 分支分析
    branches_analyzed: List[str]   # 已分析的分支
    branches_missing: List[str]   # 未覆盖的分支
    branch_coverage: float = 0.0  # 分支覆盖率
    
    # 状态机 (如果有)
    state_transitions: List[StateTransition] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    
    # 控制依赖
    control_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    # {信号: [控制它的条件信号]}
    
    # 便捷属性
    @property
    def is_fully_covered(self) -> bool:
        return self.branch_coverage >= 1.0
    
    @property
    def has_state_machine(self) -> bool:
        return len(self.states) > 0
```

### 4.4 DataFlowResult 扩展 (融合控制流)

```python
@dataclass
class DataFlowResult:
    # ... 现有字段 ...
    
    # 控制流融合 (新增)
    control_flow: Optional[ControlFlowResult] = None
    
    # 便捷属性
    @property
    def all_conditions(self) -> List[ConditionInfo]:
        """所有条件 (从 control_flow 或 all_conditions)"""
        if self.control_flow:
            return self.control_flow.conditions
        return self._all_conditions
    
    @property
    def enable_conditions(self) -> List[str]:
        """使能条件列表"""
        return [c.expr for c in self.all_conditions if c.kind == 'if']
    
    @property
    def data_flow_when(self) -> str:
        """数据流成立的条件"""
        conditions = self.enable_conditions
        if not conditions:
            return "always"
        return " && ".join(f"({c})" for c in conditions)
```

---

## 五、与数据流分析的融合

### 5.1 完整分析 = 数据流 + 控制流

```
完整分析报告:
    ├── 数据流
    │   ├── path: data_in → stage1 → stage2 → data_out
    │   ├── latency: 2 cycles
    │   └── timing: @posedge clk
    │
    └── 控制流
        ├── conditions: [en, valid]
        ├── data_flow_when: (en) && (valid)
        ├── branch_coverage: 75%
        └── control_dependencies: {en: [], valid: [], stage1: [en], stage2: [valid]}
```

### 5.2 使用示例

```python
class DataFlowAnalyzer:
    def analyze(self, from_signal: str, to_signal: str) -> DataFlowResult:
        # 1. 数据流分析
        result = self._analyze_data_flow(from_signal, to_signal)
        
        # 2. 控制流分析 (融合)
        result.control_flow = self._analyze_control_flow(result.paths)
        
        # 3. 关联分析
        result.data_flow_when = self._compute_enable_conditions(result)
        
        return result

# 使用
analyzer = DataFlowAnalyzer(graph, adapter)
result = analyzer.analyze('data_in', 'data_out')

print(f"Path: {result.paths[0]}")
print(f"Latency: {result.latency_cycles} cycles")
print(f"Data flows when: {result.data_flow_when}")
# 输出: Data flows when: (en) && (valid)
```

---

## 六、实现优先级

### P1: 基础控制流

1. **ConditionInfo 数据类**
2. **ControlFlowResult 数据类**
3. **条件提取** (从 StatementCollectorVisitor)
4. **条件信号提取** (复用 SignalExpressionVisitor)

### P2: 分支分析

1. **分支覆盖分析**
2. **if/else 分支配对**
3. **case 分支完整性**

### P3: 状态机分析

1. **StateTransition 数据类**
2. **状态机识别** (从 case(state) 模式)
3. **状态转换图构建**

### P4: 控制依赖链

1. **控制依赖关系图**
2. **enable 条件传播**
3. **关键控制信号识别**

---

## 七、与现有组件的关系

| 组件 | 控制流分析中的角色 |
|------|-------------------|
| StatementCollectorVisitor | 条件语句来源 |
| SignalExpressionVisitor.extract() | 条件信号提取 |
| TraceEdge.condition | 边条件信息 |
| ClockDomainTracer | 状态机状态分析复用 |
| DataFlowResult | 融合控制流结果 |

---

## 八、文档索引

| 文档 | 内容 |
|------|------|
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | 数据流分析架构 |
| `ARCHITECTURE_COMPARISON.md` | 架构对照分析 |
| `SCHEMA_COMPARISON.md` | Schema 对照分析 |
| `CONTROL_FLOW_ANALYSIS.md` | 本文: 控制流分析架构 |

---

## 九、瑞通系统价值

| 场景 | 价值 |
|------|------|
| 验证问题生成 | "当 en=0 时数据是否保持？" |
| 覆盖分析 | "哪些分支没覆盖？" |
| 故障诊断 | "数据流断点的控制原因" |
| 状态机分析 | "状态转换条件和路径" |
| 条件传播 | "关键使能信号识别" |# ControlFlow 调试分析记录

> 创建时间: 2026-05-26
> 更新: 2026-05-26

---

## 目录

1. [else-if 链条件解析](#else-if-链条件解析)
2. [上下文栈机制](#上下文栈机制)
3. [语义 AST vs 字符串判断](#语义-ast-vs-字符串判断)
4. [修复记录](#修复记录)

---

## else-if 链条件解析

### 语义正确性

if-else-if 链的条件逻辑是：

```systemverilog
if (A)
    x = 1;        // 条件：A
else if (B)
    x = 2;        // 条件：!A && B
else
    x = 3;        // 条件：!A && !B
```

**关键点**：else-if 不是独立的 if，它嵌套在上一层的 else 分支里。

### 条件求反规则

| 分支 | 条件计算 | 说明 |
|------|----------|------|
| if (A) | A | 第一层条件 |
| else if (B) | !A && B | 取反父条件 AND 当前条件 |
| else | !A && !B | 取反父条件 AND 当前条件取反 |

### 边界情况：多层嵌套

```systemverilog
if (A)
    if (B)
        x = 1;
    else if (C)
        x = 2;
```

第二层 else-if 的条件是：`!(A && B) && C = !A || !B && C`（根据德·摩根定律）

**但实际求反实现**：直接对累积条件字符串取反
- 父条件：`A && B`
- 求反后：`!(A && B)`
- 与 C 组合：`(!(A && B)) && C`

---

## 上下文栈机制

### 核心数据结构

```python
class StatementCollectorVisitor:
    def __init__(self, adapter):
        self._ctx_stack: List[Dict[str, Any]] = [{}]  # 栈底：空 context
        self._statements: List[Tuple[Any, Dict[str, Any]]] = []
    
    @property
    def current_ctx(self):
        """获取当前上下文（栈顶）"""
        return self._ctx_stack[-1] if self._ctx_stack else {}
```

### 栈操作流程

对于以下代码：

```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n)         // 深度 1
        status <= 4'h0;
    else if (valid)     // 深度 2
        status <= 4'h1;
    else                // 深度 3
        status <= 4'h2;
end
```

**遍历过程**（深度优先 DFS）：

```
1. 进入顶层 if (!rst_n)
   stack: [{}, {"clock": "clk", "condition": ""}]
   
2. 进入 ifTrue 分支 (status <= 4'h0)
   → 栈顶 context: {"clock": "clk", "condition": ""}
   → 当前条件: "!rst_n"
   → 记录：condition = "!rst_n"

3. 遇到 else if (valid)
   → 这是 else 分支里嵌套的 if (ConditionalStatement)
   
   [求反逻辑]
   - parent_cond = "!rst_n"（栈顶 context 中的条件）
   - parent_cond_expr = UnaryOp(!, NamedValue)（语义 AST）
   - _is_simple_expr_for_negation(parent_cond_expr) = True（简单取反）
   - neg_parent = "!" + "!rst_n" = "!!rst_n"
   
   - cond = "valid"
   - _is_simple_expr_for_negation(valid) = True（简单标识符）
   - neg_cond = "!" + "valid" = "!valid"
   
   - new_cond = "!!rst_n" + " && " + "!valid" = "!!rst_n && !valid"
   
   → 压栈：{"clock": "clk", "condition": "!!rst_n && !valid", "_parent_cond_expr": valid_expr}

4. 进入第二层 ifTrue 分支 (status <= 4'h1)
   → 栈顶 context: {"condition": "!!rst_n && !valid"}
   → 记录：condition = "!!rst_n && !valid"

5. 遇到第二层 else
   → 求反逻辑
   - parent_cond = "!!rst_n && !valid"（复杂表达式）
   - neg_parent = "!(!!rst_n && !valid)"
   → 记录：condition = "!(!!rst_n && !valid)"
```

### 为什么用栈追踪父级条件？

**LIFO（后进先出）特性**：

- 第一层 else-if 处理完后弹出，第一层的 context 恢复
- 每一层都只看到自己"祖先们"的条件
- 嵌套多深都能正确追踪

```
当前在第三层：
stack = [第一层ctx, 第二层ctx, 第三层ctx]
                      ↑
                 current_ctx (栈顶)
```

### context 结构

```python
{
    "condition": "!!rst_n && valid && op_mode == 2'b01",  # 累积条件字符串
    "_parent_cond_expr": <Expression object>,            # 父条件表达式（语义AST）
    "clock": "clk",                                       # 时钟域（always_ff）
    "reset": "rst_n",                                     # 复位信号
}
```

`_parent_cond_expr` 用于下一层 else-if 判断是否需要括号。

---

## 语义 AST vs 字符串判断

### 问题：为什么不能用字符串判断？

之前的错误实现：

```python
def needs_parentheses(c: str) -> bool:
    if c.startswith('!'):
        rest = c[1:]
        while rest.startswith('!'):
            rest = rest[1:]
        if rest.replace('_', '').replace('.', '').isalnum():
            return False  # 错误！
```

**问题案例**：

| 条件字符串 | 字符串判断结果 | 实际问题 |
|------------|---------------|----------|
| `!rst_n` | 不需要括号 ✅ | 正确：加一层变成 `!!rst_n` |
| `!!rst_n` | 不需要括号 ❌ | 错误：加一层变成 `!!!rst_n`，但实际 `!rst_n` 的取反应该是 `!rst_n` |

`!!rst_n` 的语义是双重取反 `!(!(rst_n))`，但从字符串看以 `!` 开头，被错误判断为"简单取反"。

### 正确方案：语义 AST 判断

```python
def _is_simple_expr_for_negation(self, expr) -> bool:
    """判断表达式是否为简单条件（可以直接求反，不需要括号）"""
    if expr is None:
        return True
    
    kind = getattr(expr, 'kind', None)
    if not kind:
        return True
    kind_name = kind.name if hasattr(kind, 'name') else str(kind)
    
    # 简单标识符：直接加 !
    if kind_name in ('NamedValue', 'Identifier', 'Reference'):
        return True
    
    # UnaryOp：检查是否简单取反 !identifier
    if 'UnaryOp' in kind_name:
        op = getattr(expr, 'op', None)
        if not op or 'Not' not in (op.name if hasattr(op, 'name') else str(op)):
            return False
        operand = getattr(expr, 'operand', None)
        if operand:
            operand_kind = getattr(operand, 'kind', None)
            if operand_kind:
                operand_name = operand_kind.name if hasattr(operand_kind, 'name') else str(operand_kind)
                # 只有 !identifier 是简单的
                return operand_name in ('NamedValue', 'Identifier', 'Reference')
        return False
    
    # BinaryOp 等：需要括号
    return False
```

### 语义判断示例

| 表达式 | AST类型 | 操作数 | 是否简单 | 求反结果 |
|--------|---------|--------|----------|----------|
| `sel` | NamedValue | - | ✅ | `!sel` |
| `!rst_n` | UnaryOp(Not, NamedValue) | NamedValue | ✅ | `!!rst_n` |
| `!!rst_n` | UnaryOp(Not, UnaryOp) | UnaryOp | ❌ | `!(!!rst_n)` |
| `valid && sel` | BinaryOp | - | ❌ | `!(valid && sel)` |
| `!(valid && sel)` | UnaryOp(Not, BinaryOp) | BinaryOp | ❌ | `!(!(valid && sel))` |

### 关键区别

- **字符串视角**：`!!rst_n` 以 `!` 开头 → 简单取反
- **语义视角**：`!!rst_n` 是 `UnaryOp(Not, UnaryOp(Not, NamedValue))` → 嵌套取反，需要括号

---

## 修复记录

### Issue: else-if 链条件错误 ✅ 已修复 (2026-05-26)

**问题现象**：
```
# 错误输出
when !valid && op_mode == 2'b01 && valid && op_mode == 2'b10: ...
# 矛盾条件：同时有 valid 和 !valid
```

**根本原因**：使用字符串匹配判断是否需要括号

**修复方案**：
1. 新增 `_is_simple_expr_for_negation()` 方法，用语义 AST 判断
2. context 中保存 `_parent_cond_expr`（表达式对象）
3. 访问 else 分支时，根据父条件的语义结构决定是否需要括号

**关键代码**：
```python
# 访问 else-if 时
parent_cond = self.current_ctx.get('condition', '')
parent_cond_expr = self.current_ctx.get('_parent_cond_expr', None)

if parent_cond:
    # 根据语义判断是否需要括号
    if parent_cond_expr and self._is_simple_expr_for_negation(parent_cond_expr):
        neg_parent = "!" + parent_cond  # 简单条件，直接加 !
    else:
        neg_parent = "!(" + parent_cond + ")"  # 复杂条件，加括号
```

**验证结果**：
```
# 正确输出
when !!rst_n && valid && op_mode == 2'b01: ...
when !!!rst_n && !(valid && op_mode == 2'b01) && valid && op_mode == 2'b10: ...
```

---

## 测试结果

```bash
cd ~/my_dv_proj/sv_query
python -m pytest sim/tests/ -v
# ================== 845 passed, 1 skipped, 1 warning ==================
```

---

## 相关文件

- `src/trace/core/visitors/statement_collector_visitor.py`
  - `_is_simple_expr_for_negation()`: 语义 AST 简单性判断
  - `visit_conditional_statement()`: else-if 链处理，栈操作
  - context 中的 `_parent_cond_expr` 字段

- `docs/CONTROL_FLOW_DEBUG.md` (本文档)# ControlFlow 控制流分析功能设计

> 创建时间: 2026-05-26
> 更新日期: 2026-05-26
> 状态: 设计阶段
> 项目路径: /Users/fundou/my_dv_proj/sv_query

---

## 一、设计目标

ControlFlow 分析的核心价值：

| 关注点 | 说明 |
|--------|------|
| **控制条件提取** | 数据在什么条件下流动 |
| **死锁检测** | 状态机是否会卡死（无法到达某状态） |
| **矛盾条件** | 是否有永远无法满足的条件 |
| **优先级符合Spec** | 条件优先级是否符合规格描述 |

---

## 二、核心设计思想

### 2.1 交叉定位

不同于传统的模块级或变量级分析，采用**交叉定位**方式：

> 找到"控制变量操作数据变量"的代码块

```
分析起点: 一对 (控制变量, 数据变量)
    └── "en 控制 q"

目标: 定位同时包含控制变量和数据变量的控制块
    └── if (en) q <= d;  ← 这个块同时有 en 和 q
```

### 2.3 与 DataFlow 的关系

| 层级 | 职责 |
|------|------|
| **DataFlow Graph** | 底层数据，SignalGraph 提供边/节点信息 |
| **ControlFlow** | 上层组装，独立于 DataFlow |

```
┌─────────────────────────────────────────────────────────┐
│                    ControlFlow Layer                    │
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌───────────┐  │
│  │ ControlFlow │    │ ControlFlow │    │ Z3 Solver │  │
│  │    Graph     │ ←→ │   Analyzer  │ ←→ │           │  │
│  └─────────────┘    └─────────────┘    └───────────┘  │
│         ↑                  ↑                            │
│         │                  │                           │
│         └──────────────────┼───────────────────────────┘
│                            │
│                            ↓
│         ┌─────────────────────────────────┐
│         │      SignalGraph (已有)          │
│         │  提供边/节点语义信息              │
│         └─────────────────────────────────┘
```

---

## 三、API 设计

### 3.1 方式 1: 指定控制变量 + 数据变量

```python
class ControlFlowAnalyzer:
    def analyze(
        self,
        control_var: str,      # 控制变量 (en)
        data_var: str,          # 数据变量 (q)
        module: str = None,
    ) -> ControlFlowResult:
        """
        分析 control_var 如何控制 data_var 的数据流
        """
```

**示例**:
```python
# en 如何控制 q 的值
result = analyzer.analyze(control_var="en", data_var="q")
```

### 3.2 方式 2: 批量查找控制块

```python
class ControlFlowAnalyzer:
    def find_control_blocks(
        self,
        control_vars: List[str],    # ["en", "valid"]
        data_vars: List[str],        # ["q", "data_out"]
        module: str = None,
    ) -> List[ControlBlock]:
        """
        找到同时包含控制变量和数据变量的代码块
        """
```

**示例**:
```python
blocks = analyzer.find_control_blocks(
    control_vars=["en", "valid"],
    data_vars=["q", "data_out"],
    module="top"
)
```

### 3.3 DataFlow 集成触发

```python
# DataFlow 分析时自动触发 ControlFlow
df_result = dfg.analyze("data_in", "data_out")
# DataFlow 发现条件变量后，自动提取并触发 ControlFlow
cf_result = df_result.control_flow
```

---

## 四、核心数据结构

### 4.1 ControlBlock

```python
@dataclass
class ControlBlock:
    """控制块 - 同时包含控制变量和数据变量"""
    
    # 位置
    file: str
    line: int
    column: int
    end_line: int
    
    # 控制信息
    condition_expr: str           # "en && valid"
    control_vars: List[str]       # ["en", "valid"]
    
    # 数据信息
    data_vars: List[str]          # ["q", "data_out"]
    data_stmts: List[str]         # ["q <= d", "data_out <= src"]
    
    # 块的 AST 节点
    ast_node: Any
    
    # 块类型
    kind: str                     # 'if', 'case', 'ternary', 'always_ff', 'always_comb'
    
    # 分支信息 (if/case)
    branches: List[Branch] = field(default_factory=list)
    
    # 嵌套的子块
    nested_blocks: List['ControlBlock'] = field(default_factory=list)
```

### 4.2 ControlFlowNodeKind

```python
class ControlFlowNodeKind(Enum):
    """控制流节点类型"""
    
    # 条件节点
    CONDITION = auto()          # if/case/三元条件
    CONDITION_TRUE = auto()     # if 的 then 分支
    CONDITION_FALSE = auto()    # if 的 else 分支
    CONDITION_DEFAULT = auto()  # case 的 default
    
    # 分支节点
    CASE_ITEM = auto()          # case 的某个项
    
    # 状态节点
    STATE = auto()              # 状态机状态
    STATE_ENTRY = auto()        # 进入状态
    STATE_EXIT = auto()         # 退出状态
    
    # 合并节点
    MERGE = auto()              # if/case 后的汇合
    
    # 块节点
    BLOCK = auto()              # 代码块
    SEQUENCE = auto()           # 顺序执行
```

### 4.3 ControlFlowEdgeKind

```python
class ControlFlowEdgeKind(Enum):
    """控制流边类型"""
    
    # 条件分支
    COND_TRUE = auto()          # 条件为真时的边
    COND_FALSE = auto()         # 条件为假时的边
    
    # case 分支
    CASE_MATCH = auto()         # case 匹配某值
    CASE_DEFAULT = auto()        # case default
    
    # 状态转换
    STATE_TRANSITION = auto()   # 状态转换
    
    # 执行顺序
    SEQUENCE = auto()           # 顺序执行
    FALL_THROUGH = auto()        # 穿透执行（无 break）
```

### 4.4 ControlFlowNode

```python
@dataclass
class ControlFlowNode:
    """控制流节点"""
    
    id: str                    # 唯一 ID: "module:line:col:kind"
    kind: ControlFlowNodeKind
    name: str                   # 可读名称: "if (en)", "state=IDLE"
    
    # 位置
    file: str
    line: int
    column: int
    
    # 条件信息（如果是 CONDITION 节点）
    condition_expr: Optional[str] = None    # "en && valid"
    condition_vars: List[str] = field(default_factory=list)  # ["en", "valid"]
    
    # 状态信息（如果是 STATE 节点）
    state_value: Optional[str] = None       # "IDLE"
    
    # case 信息（如果是 CASE_ITEM 节点）
    case_value: Optional[str] = None       # "0", "default"
    
    # 关联的 AST 节点
    ast_node: Optional[Any] = None
```

### 4.5 ControlFlowEdge

```python
@dataclass
class ControlFlowEdge:
    """控制流边"""
    
    id: str
    kind: ControlFlowEdgeKind
    
    # 源节点和目标节点
    from_node: str              # 源节点 ID
    to_node: str                # 目标节点 ID
    
    # 边条件（条件分支边）
    condition_expr: Optional[str] = None   # "en", "sel == 0"
    
    # 优先级（case/if 优先级）
    priority: int = 0
    
    # AST 信息
    ast_node: Optional[Any] = None
```

### 4.6 ControlFlowResult

```python
class ControlFlowResult:
    """控制流分析结果"""
    
    # 输入
    control_var: str              # "en"
    data_var: str                 # "q"
    
    # 控制块信息
    control_block: ControlBlock
    
    # 条件分析
    condition_expr: str           # "en && valid"
    condition_vars: List[str]     # ["en", "valid"]
    condition_sources: Dict[str, str]  # {"en": "top.u_ctrl.en"}
    
    # 分支分析
    branches: List[BranchResult]
    
    # 数据流条件
    data_flow_when: str           # "en == 1"
    
    # Z3 分析 (如果有矛盾条件)
    z3_analysis: Optional[Z3Result]
    
    # 警告
    warnings: List[LintWarning]
    
    # === 死锁/可达性 ===
    state_machine_analysis: Optional[StateMachineAnalysis]
    
    # === 矛盾条件 ===
    contradictions: List[Contradiction]
    
    # === 优先级分析 ===
    priority_analysis: Optional[PriorityAnalysis]
```

### 4.7 BranchResult

```python
@dataclass
class BranchResult:
    """分支结果"""
    
    condition: str               # 分支条件 "en", "sel == 0"
    action: str                  # 执行的动作 "q <= d"
    covered: bool                # 是否覆盖
    signal_sources: List[str]    # 信号的来源
```

### 4.8 StateMachineAnalysis

```python
@dataclass
class StateMachineAnalysis:
    """状态机分析结果"""
    
    name: str                   # "top.state"
    
    # 死锁检测
    has_deadlock: bool
    deadlock_states: List[str]   # 死锁的状态列表
    deadlock_reason: str        # "missing default branch"
    
    # 无法到达的状态
    unreachable_states: List[StateTransition]
    
    # 所有状态
    all_states: List[str]
    reachable_states: List[str]  # 可达的
```

### 4.9 Contradiction

```python
@dataclass
class Contradiction:
    """矛盾条件"""
    
    type: str              # 'impossible_condition', 'duplicate_case'
    expr: str              # "en && !en"
    reason: str            # "en && !en is always false"
    location: Location     # file, line, column
    severity: str          # 'error', 'warning'
    suggestion: str        # "Remove impossible condition"
```

### 4.10 LintWarning

```python
@dataclass
class LintWarning:
    """代码审查警告"""
    
    severity: str               # 'error', 'warning', 'info'
    rule: str                  # 'LATCH_WARNING', 'INCOMPLETE_CASE'
    
    file: str
    line: int
    column: int
    
    message: str               # "if without else may cause latch"
    suggestion: str             # "Add else branch with default value"
```

---

## 五、工作流程

```
analyze(control_var="en", data_var="q")
    │
    ├─→ 1. 在 SignalGraph 中查找 en 的相关边
    │    ├─→ en 作为 DRIVER 边
    │    └─→ en 作为 condition 边
    │
    ├─→ 2. 在 SignalGraph 中查找 q 的相关边
    │    └─→ q 作为 DRIVER/LATCH 边
    │
    ├─→ 3. 交叉定位: 找到 en 和 q 的交集
    │    └─→ if (en) q <= ...; 这条语句
    │
    ├─→ 4. 提取控制流信息
    │    ├─→ 条件表达式: "en"
    │    ├─→ 分支: en=1 → q=d, en=0 → q=保持
    │    └─→ 依赖链: en 的来源
    │
    └─→ 5. 返回 ControlFlowResult
         ├─ control_var: "en"
         ├─ data_var: "q"
         ├─ control_block: if (en) q <= d;
         └─ branches: [BranchResult(cond="en", action="q=d"), ...]
```

---

## 六、Z3 集成

### 6.1 Z3Solver

```python
class Z3Solver:
    """用 Z3 进行条件求解"""
    
    def check_satisfiability(self, conditions: List[str]) -> Z3Result:
        """
        检查条件是否可满足
        
        en && valid  # → satisfiable
        en && !en   # → unsatisfiable (矛盾)
        """
        
    def find_deadlock_states(self, state_var, transitions) -> List[str]:
        """
        找出死锁状态：没有后继的状态
        """
        
    def find_unreachable_states(self, state_var, transitions, init_state) -> List[str]:
        """
        找出不可达状态
        """
```

### 6.2 分析场景

| 场景 | Z3 用途 |
|------|---------|
| 死锁检测 | 检查每个状态是否有后继转换 |
| 矛盾条件 | `en && !en` 永远为 false |
| 不可达状态 | 从初始状态可达的集合 |
| 条件优先级 | spec 优先级 vs code 优先级 |

---

## 七、Spec 驱动分析

### 7.1 Spec 格式

```python
spec = """
Control signals:
- en: enable data flow
- valid: data is valid
- state: FSM state

Transitions:
- IDLE → RUN when en && valid
- RUN → DONE when done

State transition priority:
1. start > stop
2. idle > run
"""
```

### 7.2 PriorityAnalysis

```python
class PriorityAnalysis:
    # 从 spec 解析的优先级
    spec_priorities: List[Tuple[str, str]]
    
    # 代码中的实际优先级
    code_priorities: List[Tuple[str, str]]
    
    # 比对结果
    matches: bool
    mismatches: List[Mismatch]
```

---

## 八、文件结构

```
src/trace/core/
├── graph/
│   ├── __init__.py
│   ├── dataflow.py              # DataFlow 图 (已有)
│   ├── controlflow.py            # ControlFlow 图 (新建)
│   └── controlflow_models.py     # 控制流数据模型 (新建)
│
├── analyzer/
│   ├── __init__.py
│   ├── dataflow_analyzer.py      # DataFlow 分析 (已有)
│   ├── controlflow_analyzer.py   # ControlFlow 分析 (新建)
│   └── z3_analyzer.py            # Z3 求解器 (新建)
│
└── bridge/
    └── flow_bridge.py            # DataFlow ↔ ControlFlow 桥接 (新建)
```

---

## 九、输出示例

### 9.1 分析单个控制-数据对

```python
result = analyzer.analyze(control_var="en", data_var="q")

# 打印
Control Flow Analysis: en → q

Control Block:
  File: top.sv:10
  Code: if (en) q <= d; else q <= 0;
  
Condition: en
  Expression: en
  Source: top.en (from top.u_ctrl)
  
Branches:
  ├─ when en=1: q = d       ✅
  └─ when en=0: q = 0       ⚠️ latch risk (q holds previous value)

Data Flow When: en == 1

Warnings:
  ⚠️ LATCH: q 在 en=0 时保持原值，可能导致 latch
    Suggestion: 明确初始化 q
```

### 9.2 批量查找控制块

```python
blocks = analyzer.find_control_blocks(
    control_vars=["en", "valid"],
    data_vars=["q", "data_out"],
    module="top"
)

# 返回
# [
#   ControlBlock(
#     file="top.sv",
#     line=10,
#     condition="en",
#     data_vars=["q"],
#     stmt="if (en) q <= d;"
#   ),
#   ControlBlock(
#     file="top.sv",
#     line=15,
#     condition="en && valid",
#     data_vars=["data_out"],
#     stmt="if (en && valid) data_out <= src;"
#   ),
# ]
```

---

## 十、实现优先级

### Phase 1: 基础能力

1. [ ] ControlFlow 数据模型 (ControlBlock, ControlFlowResult)
2. [ ] 交叉定位: `find_control_blocks()`
3. [ ] 条件提取和分支分析
4. [ ] Lint 警告 (if without else, case without default)

### Phase 2: 状态机分析

1. [ ] 状态机识别 (case(state) 模式)
2. [ ] 死锁检测
3. [ ] 不可达状态分析
4. [ ] Z3 集成

### Phase 3: Spec 驱动

1. [ ] Spec 解析
2. [ ] 优先级分析
3. [ ] Agent 集成

---

## 十一、相关文档

| 文档 | 说明 |
|------|------|
| `DATAFLOW_ANALYSIS_ARCHITECTURE.md` | DataFlow 分析架构 |
| `ARCHITECTURE.md` | 整体架构文档 |
| `PENDING_FEATURES.md` | 待实现功能清单 |
| `CONTROL_FLOW_ANALYSIS.md` | 旧版控制流架构提案 (参考) |

---

## 更新日志

| 日期 | 操作 |
|------|------|
| 2026-05-26 | 创建文档，基于交叉定位设计思想 |# ControlFlow 改进方案

## 问题 1: 嵌套三元运算符条件

### 根因
**位置**: `SignalExpressionVisitor.get_all_conditional_op()` (line 6479)

**当前行为**: 
```python
def get_all_conditional_op(self, node) -> List[str]:
    # 提取 condition, left, right 的所有信号
    # 但不区分每个信号属于哪个分支
    return [sel, a, b, c]  # 丢失分支信息
```

### 改进方案

**方案 A**: 在 `SignalExpressionVisitor` 添加新方法
```python
def get_signals_with_conditions(self, node, parent_cond=None) -> List[Tuple[str, str]]:
    """返回 (signal, condition) 对列表
    
    对于嵌套三元 `a ? (b ? y1 : y2) : y3`:
    - y1 -> (y1, a && b)
    - y2 -> (y2, a && !b)  
    - y3 -> (y3, !a)
    """
```

**方案 B**: 在 `graph_builder.py` 的连续赋值处理中特殊处理 ConditionalOp

### 具体改动位置
1. `src/trace/core/visitors/signal_expression_visitor.py` - 添加 `get_signals_with_conditions()`
2. `src/trace/core/graph_builder.py` - 修改连续赋值边创建 (line 560-660)

---

## 问题 2: Case on signal 选择器为空

### 根因
**位置**: `statement_collector_visitor.py` - `_get_case_selector()` (line 660)

**问题**: 嵌套 case 时，inner case 是 `CaseStatementSyntax`（语法节点），不是 `CaseStatement`（语义节点）

**当前代码**:
```python
def _get_case_selector(self, node) -> str:
    expr = getattr(node, 'expr', None)
    if expr:
        sel_str = self._expr_to_string(expr)
        if sel_str:
            return sel_str  # 返回空字符串给 IdentifierNameSyntax
    return "?"  # 回退
```

**根因**: `_expr_to_string()` 不处理 `IdentifierNameSyntax`（语法树节点）

### 改进方案

**方案 A**: 修改 `_expr_to_string` 添加 `IdentifierNameSyntax` 处理
```python
# 在 _expr_to_string 中添加
if hasattr(expr, 'kind'):
    kind_name = expr.kind.name if hasattr(expr.kind, 'name') else str(expr.kind)
    if 'IdentifierName' in kind_name:
        # 直接返回 syntax 的字符串表示
        return str(expr).strip()
```

**方案 B**: 修改 `_get_case_selector` 直接处理 syntax 节点
```python
def _get_case_selector(self, node) -> str:
    # 语义路径
    expr = getattr(node, 'expr', None)
    if expr and hasattr(expr, 'kind'):
        kind_name = expr.kind.name if hasattr(expr.kind, 'name') else ""
        # 语义 NamedValueExpression
        if 'NamedValue' in kind_name:
            return self._expr_to_string(expr)
        # 语法 IdentifierNameSyntax - 直接返回 str
        if 'IdentifierName' in kind_name:
            return str(expr).strip()
    
    # 回退到 syntax.expr
    syntax = getattr(node, 'syntax', None)
    if syntax:
        expr = getattr(syntax, 'expr', None)
        if expr:
            return str(expr).strip()
    return "?"
```

### 具体改动位置
1. `src/trace/core/visitors/statement_collector_visitor.py`
   - `_expr_to_string()` - 添加 `IdentifierNameSyntax` 处理
   - 或 `_get_case_selector()` - 添加 syntax 节点直接处理

---

## 问题 3: always_comb 内嵌套 ternary 无输出

### 根因
**待进一步分析**

可能原因：
1. `always_comb` 块内的语句收集逻辑问题
2. 三元操作符在过程块内的处理与连续赋值不同

### 改进方案
需要先确认 `always_comb begin case(x) ... ternary ... end end` 的收集流程

---

## 优先级建议

| 问题 | 优先级 | 原因 |
|------|--------|------|
| 问题 2 | **高** | Case on signal 是常见模式，影响核心功能 |
| 问题 1 | 中 | 嵌套三元较少见，当前基本功能可用 |
| 问题 3 | 低 | 需要更多调试，可能涉及架构调整 |

---

## 验证方法

```bash
# 问题 2 验证
cat > /tmp/test_case.sv << 'EOF'
module top(input valid, data, output logic y);
    always_comb begin
        case (valid)
            1'b0: y = data;
            1'b1: y = data + 1;
        endcase
    end
endmodule
EOF
python run_cli.py controlflow analyze top.y -f /tmp/test_case.sv
# 期望: when valid == 1'b0, when valid == 1'b1

# 嵌套三元验证
cat > /tmp/test_nested_ternary.sv << 'EOF'
module top(input [1:0] sel, a, b, c, d, output logic y);
    assign y = (sel == 2'b00) ? a :
               (sel == 2'b01) ? b :
               (sel == 2'b10) ? c : d;
endmodule
EOF
python run_cli.py controlflow analyze top.y -f /tmp/test_nested_ternary.sv
# 期望: 4 个分支分别对应 4 个条件
```
