# Control Coverage Generator

> 用户文档
> 创建时间: 2026-06-02
> 状态: V1 实现完成 (8 个 TDD cycle)
> 关联: [实施计划](COVERAGE_GENERATOR_PLAN.md)

---

## 1. 概述

`ControlCoverageGenerator` 是 sv_query 的一个子模块，**基于信号的条件驱动关系，递归展开到原子信号，生成控制覆盖度建议**。

### 1.1 解决的问题

验证工程师手写 coverage 时容易遗漏：
```sv
assign c = a | b;     // c 的 true_condition: a, b
assign x = c & d;     // x 的 true_condition: c, d (容易漏展开)
```

**期望**: 查询 `x` 的 coverage 应输出 `a, b, d`（递归展开 c）。

### 1.2 核心能力

- ✅ **递归展开**: 沿 driver 链展开到原子信号
- ✅ **位选感知**: `a[3:0]`, `a[7:0][3:0]` 等位选
- ✅ **宽松模式**: 表达式中所有出现的信号都包含
- ✅ **跨模块检测**: 检测并报错
- ✅ **端口边界**: 模块端口停止递归
- ✅ **Markdown 报告**: 包含证据链 + covergroup 模板

---

## 2. 快速开始

### 2.1 CLI 一行命令

```bash
python run_cli.py coverage suggest \
    -f path/to/your.sv \
    --signal top.your_signal
```

**示例**: 用项目自带的 `test_data_path.sv`:

```bash
$ python run_cli.py coverage suggest \
    -f sim/tests/regression/test_data_path.sv \
    --signal data_path.stage1_data
```

**输出**:
```markdown
# 控制覆盖度分解报告

## 概要

- **原始信号**: `data_path.stage1_data`
- **原子信号数**: 4 (OK)
- **分解深度**: 10
- **控制块数**: 3

## 原子信号清单

### 1. `rst_n`
### 2. `din_valid`
### 3. `din_ready`
### 4. `din`

## 控制块详情

### 控制块 #1
- **条件**: `!rst_n`
- **驱动表达式**: ``
- **边**: `data_path.clk` → `data_path.stage1_data`

### 控制块 #2
- **条件**: `din_valid && din_ready`
- **驱动表达式**: `din`
- **边**: `data_path.din` → `data_path.stage1_data`
...

---

> 💡 **下一步**:
> 
> 将 4 个原子信号添加到 covergroup:
> 
> ```systemverilog
> covergroup cg_data_path_stage1_data @ (posedge clk);
>     cross rst_n, din_valid, din_ready, din {
>         // bins 由工具根据关键值生成
>     }
> endgroup
> ```
```

### 2.2 Python API

```python
from trace.unified_tracer import UnifiedTracer
from trace.core.coverage_generator import ControlCoverageGenerator

# 1. 解析 SV 文件
with open("my_module.sv") as f:
    source = f.read()
tracer = UnifiedTracer(sources={"my_module.sv": source})
graph = tracer.build_graph()

# 2. 创建 generator
gen = ControlCoverageGenerator(graph=graph)

# 3. 分解信号
result = gen.decompose(["top.my_signal"])

# 4. 生成 Markdown 报告
md = gen.generate_coverage_markdown(result)
print(md)
```

---

## 3. CLI 参考

### 3.1 `coverage suggest`

```bash
python run_cli.py coverage suggest [OPTIONS]
```

| 选项 | 必填 | 说明 |
|------|------|------|
| `--file / -f` | ✅ | SystemVerilog 源文件路径 |
| `--signal / -s` |  | 单个信号 (如 `top.x`) |
| `--signals` |  | 多个信号，逗号分隔 (如 `a, b, c`) |
| `--max-signals` |  | 信号树最大数量 (默认 `5`) |
| `--max-depth` |  | driver 链最大深度 (默认 `10`) |
| `--json` |  | JSON 输出 (TODO) |

**示例**:
```bash
# 完整命令
python run_cli.py coverage suggest \
    -f top.sv \
    --signal top.x \
    --max-signals 5 \
    --max-depth 10
```

### 3.2 退出码

- `0`: 成功
- `1`: 信号树超过 `max_signals` 或跨模块错误

---

## 4. Python API 参考

### 4.1 `ControlCoverageGenerator`

```python
class ControlCoverageGenerator:
    def __init__(
        self,
        graph: SignalGraph,
        cfg: ControlFlowGraph | None = None,
        source_provider: Callable[[str], str] | None = None,
    ):
        """
        Args:
            graph: SignalGraph (来自 UnifiedTracer.build_graph())
            cfg: ControlFlowGraph (可选, 用于未来 find_control_blocks)
            source_provider: 源码懒加载函数 file -> str
        """
```

### 4.2 `decompose()`

```python
def decompose(
    self,
    signals: list[str],
    max_signals: int = 5,
    max_depth: int = 10,
) -> DecompositionResult:
    """分解信号到原子

    Args:
        signals: 要分解的信号列表 (V1 只处理第一个)
        max_signals: 信号树最大数量 (默认 5, 超过报错)
        max_depth: driver 链最大深度 (默认 10)

    Returns:
        DecompositionResult 含:
        - atomic_signals: list[AtomicSignal]
        - control_blocks: 涉及的 if/case 边
        - depth_reached: 实际深度
        - signal_count: 原子信号数
        - truncated: 是否超 max_signals
        - error: 错误信息 (如有)
    """
```

### 4.3 `generate_coverage_markdown()`

```python
def generate_coverage_markdown(self, result: DecompositionResult) -> str:
    """生成 Markdown 格式的分解报告

    Returns:
        Markdown 文本 (可直接 print 或写入文件)
    """
```

### 4.4 数据类

#### `AtomicSignal`

```python
@dataclass
class AtomicSignal:
    name: str              # 完整名 "a" 或 "a[3:0]"
    base_name: str         # 不含位选 "a"
    bit_range: tuple[int, int] | None  # (high, low) 或 None
    source: SourceLocation  # 出现位置
    evidence: list[EvidenceStep]  # 推导链步骤
```

#### `DecompositionResult`

```python
@dataclass
class DecompositionResult:
    original_signal: str
    atomic_signals: list[AtomicSignal]
    control_blocks: list[TraceEdge]  # 临时: 含 condition 的边
    depth_reached: int
    signal_count: int
    truncated: bool
    error: str | None
```

#### `EvidenceStep`

```python
@dataclass
class EvidenceStep:
    step_type: str  # 'driver_chain' | 'recursive' | ...
    description: str  # "top.c -> top.x: c & d"
    from_signal: str
    to_signals: list[str]
    source: SourceSnippet | None
```

---

## 5. 设计原理

### 5.1 数据流

```
用户输入 signals
       ↓
collect_condition_edges(signal)  ─→  找带 condition 的 incoming edges
       ↓
parse_expression_to_atomics(expr)  ─→  从表达式提取原子
       ↓
trace_drivers(atomic)  ─→  沿 driver 链递归 (端口/深度限制)
       ↓
collect & dedupe  ─→  所有原子信号
       ↓
generate_coverage_markdown()  ─→  输出报告
```

### 5.2 表达式解析

V1 使用**字符串解析** + **AST 解析**双路径:

| 路径 | 何时用 | 精度 |
|------|--------|------|
| 字符串 | V1 默认 (graph_builder 暂存条件字符串) | 中 (正则分词) |
| AST | 未来 (graph_builder 存 AST 后) | 高 (复用 SignalExpressionVisitor) |

**支持表达式**:
- 二元: `a & b`, `a | b`, `a + b`, `a - b`, `a < b`
- 一元: `!a`, `~a`
- 字面量: `1`, `8'hFF`, `32'd100`, `4'b1011` (自动过滤)
- 位选: `a[3:0]`, `a[5]`, `data[7:0][3:0]`
- 括号: `(a & b) | c`
- 三元: `en ? d : 0`

### 5.3 driver 链追踪

**终止条件**:
- 已访问 (避免循环)
- 节点不存在
- 模块端口 (`is_port=True` 或 `kind in (PORT_IN, OUT, INOUT)`)
- 超过 `max_depth`

**信号 ID 解析**:
- 表达式返回 `a, b` (无模块前缀)
- driver 链需要 `top.a, top.b` (有前缀)
- `_resolve_signal_id(name, context)` 用 context 推导前缀

### 5.4 跨模块检测

```
'a'           -> False (单点以下)
'top.x'       -> False (1个点, 单模块)
'top.sub.x'   -> True  (2个点, 跨模块)
'top.a.b.c'   -> True  (2个点以上)
```

---

## 6. 限制

### 6.1 当前不支持

- ❌ **跨模块信号** (rtl 通常不会这么设计)
- ❌ **JSON 输出** (CLI 只支持 Markdown)
- ❌ **多信号组合 decompose** (V1 只处理第一个)
- ❌ **关键值 bin 自动生成** (后续 Z3 集成)
- ❌ **`ControlFlowGraph` 集成** (现有 `ControlBlock.control_vars` 字段未填充)
- ❌ **AST 自动提取** (需要 graph_builder 改造)

### 6.2 已知 bug (已修复)

- ✅ `SignalExpressionVisitor.extract()` dispatch 错误 (bound method 调用)
- ✅ `SignalResult.merge()` 方法缺失
- ✅ `extract_identifier_name` 不设 `all_signals`

### 6.3 边界情况

- 空表达式: 返回空列表
- 纯字面量: 全部过滤
- 循环引用: `visited` 集合保护
- 端口: 立即停止递归

---

## 7. 未来工作

### 7.1 短期 (下一版本)

- **AST 自动集成**: graph_builder 改造存储 condition_ast
- **控制块真实集成**: 修复 `ControlBlock.control_vars` 填充
- **多信号 decompose**: 支持 `signals=["a", "b", "c"]`
- **JSON 输出**: CLI `--json` 实现

### 7.2 长期 (后续)

- **Z3 集成**: 求关键值 / 最小覆盖集合
- **更复杂的表达式**: 宏、typedef、struct 字段
- **HTML 报告**: 更好的可视化
- **批量分析**: 整个模块的 coverage 一键生成

---

## 8. 测试

### 8.1 运行测试

```bash
# 单个测试文件
python -m pytest sim/tests/unit/test_coverage_generator.py -v

# 全部测试
python -m pytest sim/tests/ -q

# 特定 cycle
python -m pytest sim/tests/unit/test_coverage_generator.py::TestMarkdownOutput -v
```

### 8.2 测试覆盖 (按 cycle)

| Cycle | 测试 | 数量 |
|-------|------|------|
| 1 | 数据结构 (SourceLocation, AtomicSignal 等) | 18 |
| 2 | 表达式解析器 (含位选) | 16 |
| 3 | Driver 链追踪 + 端口 | 9 |
| 4 | decompose 主入口 | 10 |
| 5 | Markdown 输出 | 6 |
| 7 | CLI 入口 | 2 |
| 8 | AST 解析集成 | 2 |
| 9 | 跨模块检测 | 5 |
| **合计** | | **68** |

### 8.3 实际跑 SV

```bash
# 真实示例 (用项目自带的 test_data_path.sv)
python run_cli.py coverage suggest \
    -f sim/tests/regression/test_data_path.sv \
    --signal data_path.stage1_data
```

---

## 9. 故障排查

### Q1: 输出 "0 atomic signals"

**原因**: 目标信号没有带 condition 的 incoming edges

**解决**:
- 检查信号名拼写
- 确认在 always 块内使用 `if (en) data <= src;` 而不是 `assign data = en ? src : 0;`

### Q2: 报错 "信号 X 跨模块"

**原因**: 信号名含 2+ 个点 (如 `top.sub.x`)

**解决**: V1 不支持跨模块. 用顶层模块信号, 或修改 `decompose()` 内部

### Q3: 报错 "Decomposition exceeds max_signals (5)"

**原因**: 分解的原子信号数 > 5

**解决**:
- 用 `--max-signals 10` 放宽
- 或手动指定更窄的起点

### Q4: 报错 "unknown module 'x_sub'"

**原因**: 单独分析子模块时缺少依赖文件

**解决**:
- 用完整顶层文件
- 或在 `--include` 提供头文件

### Q5: 端口被错误识别为普通信号

**检查**: `is_port=True` 和 `kind=PORT_IN/OUT/INOUT` 任一

**解决**: 子模块实例的端口在 graph_builder 中可能没正确标记

---

## 10. 相关文档

- [实施计划](COVERAGE_GENERATOR_PLAN.md) - V1 设计细节
- [DOC_IMPL_GAP.md](DOC_IMPL_GAP.md) - 文档与实现差异
- [主 README](../README.md) - sv_query 总览
- [USER_GUIDE.md](USER_GUIDE.md) - sv_query 用户指南

---

**最后更新**: 2026-06-02
**作者**: QClaw Agent
**状态**: V1 完成 (8 cycle TDD)
