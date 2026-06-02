# Control Coverage Generator 实施计划

> 创建时间: 2026-06-02
> 状态: 规划完成，待实施
> 目标版本: V1

---

## 1. 背景与目标

### 1.1 业务背景
验证工程师用 `assign c = a | b; assign x = c & d;` 这种 RTL 时，手写 coverage 容易遗漏。
当前 sv_query 已经能提取 true condition 字符串，但**未递归展开到原子信号**。

### 1.2 目标
基于已有的 `true condition` 提取能力，**递归展开到原子信号**（含位选），
自动生成 `cross` coverage 模板 + 关键值 bins。

### 1.3 例子
```sv
// 输入
assign c = a | b;        // c = a | b
assign x = c & d;        // x = c & d

// 查询 x 的 coverage
// V1 输出应该是: {a, b, d}  (3 个原子信号)
```

---

## 2. 需求决策表

| # | 决策点 | 决策 | 备注 |
|---|--------|------|------|
| 1 | "true condition" 定义 | 宽松 + 最小布尔集合 | 宽松优先，Z3 后续 |
| 2 | 关键值 bin | g/f 边界值作为 bin | 非简单的 0/1 |
| 3 | 位选表示 | 区间表示 `a[3:0]` | 保留可读性 |
| 4 | 信号树 > 5 限制 | **报错**，让用户指定 | 严格 |
| 5 | 最小集合判断 | 表达式直接含的信号 = 最小 | 不深追 driver |
| 6 | 父级 block 搜索 | 围绕 if/case 块搜索 | 然后展开 |
| 7 | 否定处理 | 同样展开到 a, b | `!a` 包含 `a` |
| 8 | 父级 block 类型 | 父级 if/else/case | |
| 9 | 信号树限制 | ≤ 5 个 | 超过报错 |
| 10 | 阶段 | V1 宽松版，后续评估 Z3 | |
| +A | 位选精度 | 精确到位选，区间表示 | |
| +B | 比较关系 | 拆出所有出现信号 | 后续 Z3 求关键值 |

---

## 3. 系统设计

### 3.1 数据结构

```python
# coverage_models.py

@dataclass
class SourceLocation:
    """源码位置"""
    file: str = ""
    line_start: int = 0
    line_end: int = 0
    column: int = 0

@dataclass
class SourceSnippet:
    """源代码片段（懒加载）"""
    location: SourceLocation
    text: str = ""  # 通过 source_provider 按需加载

@dataclass
class EvidenceStep:
    """推导链单步 - signal/位选分开"""
    step_type: str  # 'driver_chain'|'bit_select'|'expression_parse'|'control_block'|'port_stop'|'cross_module'
    description: str
    from_signal: str
    to_signals: list[str]
    source: SourceSnippet | None = None

@dataclass
class AtomicSignal:
    """原子信号（含位选）"""
    name: str              # "a[3:0]"
    base_name: str         # "a"
    bit_range: tuple | None  # (3, 0) or None
    source: SourceLocation
    evidence: list[EvidenceStep]

@dataclass
class DecompositionResult:
    """信号分解结果"""
    original_signal: str
    atomic_signals: list[AtomicSignal]
    control_blocks: list[ControlBlock]
    depth_reached: int
    signal_count: int
    truncated: bool
    error: str | None = None
```

### 3.2 核心类 API

```python
class ControlCoverageGenerator:
    """控制覆盖度生成器

    复用项目内现有组件:
    - UnifiedTracer → 构建图
    - ControlFlowGraph → 找控制块
    - SignalExpressionVisitor → 解析表达式（含位选）
    - SignalGraph.find_drivers → driver 链追踪
    - DataFlowGraph → 跨驱动追踪
    """

    def __init__(
        self,
        graph: SignalGraph,
        cfg: ControlFlowGraph | None = None,
        source_provider: Callable[[str], str] | None = None,
    ):
        ...

    # === 主入口 ===
    def decompose(
        self,
        signals: list[str],
        max_signals: int = 5,
        max_depth: int = 10,
    ) -> DecompositionResult:
        """分解信号到原子

        Args:
            signals: 用户输入的信号列表 (e.g. ["x", "a", "b"])
            max_signals: 信号树最大数量 (默认 5)
            max_depth: driver 链最大深度

        Returns:
            DecompositionResult: 包含原子信号 + 推导链
        """

    # === 内部方法 ===
    def _find_control_blocks(self, signal: str) -> list[ControlBlock]:
        """找含该信号的 if/case blocks (复用 cfg.find_control_blocks)"""

    def _extract_condition_atomic(
        self,
        cond_expr: str,
        cond_ast: ASTNode | None,
    ) -> list[AtomicSignal]:
        """提取条件中的原子信号

        优先用 cond_ast (如有)
        Fallback 用字符串解析
        """

    def _trace_drivers(
        self,
        signal: str,
        bit_range: tuple | None,
        depth: int,
        max_depth: int,
        visited: set,
    ) -> list[AtomicSignal]:
        """沿 driver 链递归

        每层:
        1. 找 drivers (复用 graph.find_drivers)
        2. 提取 driver 表达式中的原子信号
        3. 递归追踪 driver 源
        4. 遇到端口/跨模块/无 driver 停止
        """

    def _is_module_port(self, signal: str) -> bool:
        """检测模块端口 (停止条件)"""

    def _detect_cross_module(self, signal: str) -> bool:
        """检测跨模块 (报错)"""

    # === 输出 ===
    def generate_coverage_markdown(self, result: DecompositionResult) -> str:
        """生成 markdown 报告"""
```

### 3.3 CLI API

```bash
# 单个信号
python run_cli.py coverage suggest -f top.sv --signal x

# 多个信号
python run_cli.py coverage suggest -f top.sv --signals "x, a, b"

# JSON 输出
python run_cli.py coverage suggest -f top.sv --signal x --json
```

### 3.4 Markdown 输出示例

```markdown
# 分解结果: x

## 概要
- 原始信号: x
- 分解深度: 2
- 原子信号数: 3 (限制 ≤ 5)
- 涉及控制块: 1 个

## 控制块上下文
### [if] top.sv:8-10
- 条件: rst_n && en
- 数据信号: x

## 原子信号详情

### a[3:0]
- 来源: top.sv:5
- 位选: 3:0

**推导链**:
1. x 在 if (rst_n && en) 块内驱动 (top.sv:8-10)
2. 找到 x 的 driver: c & d (top.sv:8)
3. c & d 解析为 {c, d}
4. c 的 driver 表达式: a | b (top.sv:5)
5. a | b 解析为 {a, b}
6. a[3:0] 来自 a 的位选 3:0 (top.sv:3)

源码证据:
\`\`\`sv
3:  logic [3:0] a, b;
4:  logic [3:0] c;
5:  assign c = a | b;
8:  if (rst_n && en) begin
9:    x <= c & d;
10: end
\`\`\`
```

---

## 4. 实施步骤

### Step 1: 数据结构 (`coverage_models.py`)

**文件**: `src/trace/core/coverage_models.py`

包含:
- `SourceLocation`
- `SourceSnippet`
- `EvidenceStep`
- `AtomicSignal`
- `DecompositionResult`

**预估**: 100-150 行

### Step 2: 核心类 (`coverage_generator.py`)

**文件**: `src/trace/core/coverage_generator.py`

包含:
- `ControlCoverageGenerator` 类
- 内部 helper 方法
- `generate_coverage_markdown` 方法

**预估**: 400-600 行

### Step 3: 增强 `graph_builder.py`

**改动**: 添加 `condition_ast` 字段到 `TraceEdge`

```python
# data_models.py
@dataclass
class TraceEdge:
    ...
    condition_ast: Any | None = None  # 条件表达式 AST (懒填充)
    condition_source: SourceLocation | None = None  # 条件所在源码位置
```

**改动点**:
- `graph_builder.py`: 在收集 condition 时同时记录 AST
- 新增方法 `_build_condition_ast(cond_exprs)` - 返回 AST

**预估**: 80-100 行

### Step 4: CLI 入口 (`cli/commands/coverage.py`)

**文件**: `src/cli/commands/coverage.py`

包含:
- `coverage_app = typer.Typer(...)`
- `suggest` 子命令
- 参考 `cdc.py` 模式

**预估**: 100-150 行

### Step 5: 测试 (`test_coverage_generator.py`)

**文件**: `sim/tests/unit/test_coverage_generator.py`

测试用例:
1. `test_decompose_simple` - 简单 `x = a & b` 分解
2. `test_decompose_with_bit_select` - `x[3:0] = a[3:0] | b[3:0]`
3. `test_decompose_driver_chain` - `x = c & d, c = a | b` 多层
4. `test_decompose_with_condition` - if 块内的分解
5. `test_decompose_max_signals` - 超过 5 个报错
6. `test_decompose_cross_module` - 跨模块报错
7. `test_decompose_module_port` - 端口停止
8. `test_markdown_output` - markdown 格式验证

**预估**: 300-400 行

### Step 6: 文档 (`COVERAGE_GENERATOR.md`)

**文件**: `docs/COVERAGE_GENERATOR.md`

内容:
- 功能概述
- 使用示例
- 设计原理
- 限制和未来工作

**预估**: 200-300 行

---

## 5. 文件改动汇总

| 文件 | 类型 | 行数估计 |
|------|------|----------|
| `src/trace/core/coverage_models.py` | 新建 | 100-150 |
| `src/trace/core/coverage_generator.py` | 新建 | 400-600 |
| `src/trace/core/data_models.py` | 修改 | +20 |
| `src/trace/core/graph_builder.py` | 修改 | +80 |
| `src/cli/commands/coverage.py` | 新建 | 100-150 |
| `src/cli/main.py` | 修改 | +5 |
| `sim/tests/unit/test_coverage_generator.py` | 新建 | 300-400 |
| `docs/COVERAGE_GENERATOR.md` | 新建 | 200-300 |
| **总计** | | **~1200-1700 行** |

---

## 6. 复用检查清单

### 6.1 完全复用
- [x] `SignalGraph.find_drivers(signal_id)` - 找 driver
- [x] `SignalGraph.find_loads(signal_id)` - 找 load
- [x] `ControlFlowGraph.find_control_blocks(ctrl, data)` - 找控制块
- [x] `SignalExpressionVisitor.extract(node)` - 解析表达式含位选
- [x] `SignalResult` - 表达式结果
- [x] `DataFlowGraph.get_segments(from, to)` - 跨驱动追踪
- [x] `TraceEdge.condition` / `effective_condition` - 条件信息
- [x] `TraceEdge.expression` - driver 表达式
- [x] `TraceNode.is_port` - 端口标记
- [x] `UnifiedTracer.build_graph()` - 入口

### 6.2 需要扩展
- [ ] `TraceEdge.condition_ast` - 新增字段（可选）
- [ ] `TraceEdge.condition_source` - 新增字段（可选）

### 6.3 需要新建
- [ ] `SourceLocation` / `SourceSnippet` / `EvidenceStep` / `AtomicSignal` / `DecompositionResult`
- [ ] `ControlCoverageGenerator` 类

---

## 7. 关键技术点

### 7.1 表达式解析（位选支持）

`SignalExpressionVisitor` 已支持位选:

```python
# 已实现的 extract_xxx 方法:
- extract_element_select(self, node)  # a[5]
- extract_range_select(self, node)    # a[7:0]
- extract_member_access(self, node)   # obj.field
```

**复用方法**:
```python
visitor = SignalExpressionVisitor(adapter)
result = visitor.extract(condition_ast)
# result.all_signals 含位选形式: ["a[3:0]", "b[3:0]"]
```

### 7.2 driver 链追踪

```python
def _trace_drivers(self, signal, bit_range, depth, max_depth, visited):
    if signal in visited or depth >= max_depth:
        return []
    if self._is_module_port(signal):
        return []  # 端口停止
    if self._detect_cross_module(signal):
        raise CrossModuleError(signal)
    
    visited.add(signal)
    drivers = self._graph.find_drivers(signal)
    if not drivers:
        return []  # 无 driver 停止
    
    atomics = []
    for d in drivers:
        edge = self._graph.get_edge(d.id, signal)
        expr = edge.expression
        # 解析表达式获取原子
        parsed = self._parse_expression_atomic(expr)
        atomics.extend(parsed)
        # 递归 driver
        for atomic in parsed:
            atomics.extend(
                self._trace_drivers(atomic.base_name, atomic.bit_range,
                                    depth + 1, max_depth, visited.copy())
            )
    return atomics
```

### 7.3 控制块查找

复用 `ControlFlowGraph.find_control_blocks`:

```python
# 用户的 x 在 if (en) 块内
# 1. 找含 x 的所有 if/case 块
# 2. 提取 condition 字符串
# 3. 解析 condition → 原子信号

blocks = self._cfg.find_control_blocks(
    control_vars=condition_vars,  # 从 condition 提取
    data_vars=[original_signal]
)
```

### 7.4 位选传播

```python
# x[3:0] = c[3:0] & d[3:0]
# x[3:0] 的 driver: c[3:0]
# 需要保持位选 3:0 追踪 c

def _propagate_bit_select(self, parent_signal, parent_bits, child_signal):
    """x[3:0] → 找 x 的 driver 表达式 → 检查位选是否匹配
    返回 (new_signal, new_bits)
    """
```

---

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 位选 driver 不匹配 | 中 | 中 | 报错，让用户手动 |
| 表达式太复杂解析失败 | 中 | 低 | 降级到字符串解析 |
| AST 位置不准 | 高 | 中 | 标记可选，N/A 也可工作 |
| 跨模块引用未检测 | 低 | 中 | 用 `ModuleInstanceGraph` 兜底 |
| 大型项目性能 | 低 | 低 | 限制深度，默认 10 |

---

## 9. 验收标准

### 9.1 功能验收
- [ ] 单信号分解正确（含 if 块）
- [ ] 多信号分解正确
- [ ] driver 链跨 2-3 层正确
- [ ] 位选 `a[3:0]` 正确传递
- [ ] 比较 `g < f` 正确拆为 `{g, f}`
- [ ] > 5 信号报错
- [ ] 跨模块报错
- [ ] 模块端口停止
- [ ] Markdown 输出可读

### 9.2 性能验收
- [ ] 100 节点文件 < 1s
- [ ] 1000 节点文件 < 10s

### 9.3 质量验收
- [ ] 测试覆盖率 > 80%
- [ ] 1247 现有测试仍通过
- [ ] ruff 错误 < 10

---

## 10. 未来工作（不在 V1 范围）

1. **Z3 集成** - 求关键值 / 最小覆盖集合
2. **覆盖率合并** - 多个信号合成一个 cross
3. **统计反馈** - 哪些 coverage 实际可行
4. **批量生成** - 整个模块的 coverage
5. **HTML 报告** - 更好的可视化

---

## 11. 计划时间线

| 步骤 | 内容 | 估计行数 |
|------|------|----------|
| 1 | 数据结构 `coverage_models.py` | 100-150 |
| 2 | 核心类 `coverage_generator.py` | 400-600 |
| 3 | 增强 `graph_builder.py` + `data_models.py` | 100 |
| 4 | CLI 入口 | 100-150 |
| 5 | 单元测试 | 300-400 |
| 6 | 文档 | 200-300 |
| **合计** | | **1200-1700 行** |

---

## 12. 实施检查点

实施过程中需要验证:
- [ ] 表达式解析对位选的支持覆盖
- [ ] driver 链不会无限递归
- [ ] 跨模块检测有效
- [ ] 端口检测有效
- [ ] Markdown 格式可读
- [ ] CLI 易用
- [ ] 测试覆盖主要场景
- [ ] 文档完整

---

**创建**: 2026-06-02
**状态**: 规划完成，待实施
