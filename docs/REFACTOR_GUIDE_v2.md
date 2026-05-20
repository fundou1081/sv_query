# sv_query 重构指南 v2.0

版本：2.1 日期：2026-05-19
基于：REFACTOR_GUIDE.md v1.4 + 实测调研

## 项目纪律（必须遵守）

> **核心原则：所有数据源必须来自 Semantic AST（Compilation + getRoot()）**
>
> 禁止使用 SyntaxTree 作为主要数据源。Semantic AST 经过 elaboration，提供符号表、类型信息等语义上下文，是唯一可信的数据来源。

### 纪律条款

| 条款 | 规则 | 理由 |
|------|------|------|
| **D-1** | 禁止使用 `pyslang.SyntaxTree.fromText()` / `fromFile()` 作为主要 AST 来源 | 仅做语法解析，无语义上下文 |
| **D-2** | 必须使用 `Compilation` + `comp.addSyntaxTree()` + `comp.getRoot()` | 触发 elaboration，获取符号表和类型信息 |
| **D-3** | TB Class+Constraint 相关仅限 `constraint_visitor.py`，禁止修改 | 唯一实现，禁区 |
| **D-4** | `graph/models.py`、`unified_tracer.py`、query 层为核心资产，保持稳定 | API 契约 |

### 纪律解释

```python
# ✅ 正确做法
comp = pyslang.Compilation()
tree = pyslang.SyntaxTree.fromText(code, fname)  # 仅用于创建 Compilation
comp.addSyntaxTree(tree)
root = comp.getRoot()  # 使用 Semantic AST

# ❌ 禁止做法
tree = pyslang.SyntaxTree.fromText(code, fname)
root = tree.root  # 直接使用 SyntaxTree root
```

## 核心变化 vs v1.4

| 变化点 | v1.4 | v2.0 |
|--------|------|------|
| RTL 数据源 | `am.getDrivers()` (Layer 3) | slang-netlist NetlistGraph |
| 图结构位精确化 | Step 6 优先级高 | 降级为 Phase 2 |
| visitors/ 目录 | "整个目录删除" | 只删 statement + assignment，constraint 保留 |
| Step 2 visit API | `root.visit(lookup_table)` | 修正为 `root.visit(callback)` |
| TB Class+Constraint | 未明确 | **禁区，不动** |
| DFA 能力 | Step 3 包含 | 等待 slang-netlist SIGSEGV bug 修复 |

---

## 背景与问题定义

sv_query 现有问题：

1. **数据源层混用**：Layer 1（SyntaxTree）+ 1500 行手写 AST 遍历，绕过了 Layer 2/3 语义 API
2. **参数化位宽不准确**：返回字符串 `"W-1"` 而非整数 `7`
3. **TB Class+Constraint 能力**：目前只有 sv_query 有实现，slang-netlist 不覆盖
4. **条件感知查询缺失**：只知道"谁驱动谁"，不知道"在什么条件下驱动"

---

## 架构原则：RTL / TB / TB-Class 三层分离

```
sources (.sv)
    ↓
Compilation (elaborated)
    │
    ├─── RTL ──────────────────────────┐
    │    slang-netlist NetlistGraph    │  ← 替代 DriverExtractor + LoadExtractor
    │    (Layer 3 数据流分析)          │
    │    ⚠️ SIGSEGV bug: DFA 选项暂不可用 │
    │    → 驱动关系 + 位范围            │
    │                                  │
    ├─── TB 时序结构 ─────────────────┤
    │    pyslang AST 遍历             │  ← 替代大部分 graph_builder.py
    │    (always/initial/模块实例)    │
    │    → 条件提取 (guard conditions) │
    │                                  │
    └─── TB Class+Constraint ─────────┘
         constraint_visitor.py (543行) │  ← 唯一的 TB Class 实现
         class_graph_builder.py        │     不修改、不删除、不替换
         → randomize/constraint 能力   │

    ↓ 三层结果合并
SignalGraph ← (graph/models.py, ~400行，保留)
    ↓
unified_tracer.py + query 层 ← (~400行，保留)
    ↓
Agent debug 查询 API
```

### 为什么这样分

| 层次 | 数据来源 | slang-netlist 能替代？ | AST 能覆盖？ |
|------|---------|----------------------|--------------|
| RTL 驱动关系 | slang-netlist NetlistGraph | **直接替代** | ❌ |
| TB 时序结构（条件） | pyslang AST | ⚠️ 不完整 | **✅ 补充** |
| TB Class+Constraint | constraint_visitor.py | ❌ 不覆盖 | ❌ 唯一实现 |

**constraint_visitor.py 是禁区**——这是 sv_query 在 TB Class+Constraint 领域唯一的实现，删掉就没了，没有任何替代方案。

---

## 改造目标

**现状**：
```
SyntaxTree → [1500 行手写遍历] → SignalGraph（信号级，无位精度，无条件）
```

**改造后**：
```
sources
    ↓
Compilation
    ├── slang-netlist ─→ NetlistGraph ──┐
    │  (DFA 暂不可用，先用基础 netlist)   │
    │                                   │
    ├── pyslang AST ──→ 条件提取 ─────┤
    │  (guard conditions)               │
    │                                   │
    └── constraint_visitor.py (不动) ──┘
    ↓ 合并
SignalGraph（位精确，条件感知）
    ↓
[~400 行桥接代码] (保留 graph/models + query 层)
```

---

## 第一步：建立正确的编译入口

**工作量：1 天 新建文件：src/trace/core/compiler.py**

```python
# src/trace/core/compiler.py
import sys
sys.path.insert(0, '/path/to/slang/build/bindings')
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

    # 触发 elaboration
    diags = comp.getSemanticDiagnostics()
    errors = [d for d in diags if d.isError()]
    if errors:
        from pyslang.diagnostics import DiagnosticEngine
        report = DiagnosticEngine.reportAll(comp.sourceManager, errors)
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

**注意**：这一步是所有后续步骤的基础。后续的 Layer 2/3 API 依赖 elaboration 结果。

---

## 第二步：用 slang-netlist 替换 RTL 驱动关系

**工作量：2 天 替换文件：graph_builder.py 的 DriverExtractor + LoadExtractor**

### 2.1 调用 slang-netlist 生成 NetlistGraph

```python
import subprocess
import json
import tempfile
import os

def build_nl_from_sources(sources: dict, out_json: str):
    """调用 slang-netlist 生成 netlist JSON"""
    with tempfile.TemporaryDirectory() as td:
        # 写入临时 .sv 文件
        for fname, code in sources.items():
            with open(os.path.join(td, fname), 'w') as f:
                f.write(code)

        # 调用 slang-netlist
        args = ['slang-netlist', '--no-resolve-assign-bits',
                '--save-netlist', out_json]
        args.extend([os.path.join(td, f) for f in sources])
        result = subprocess.run(args, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"slang-netlist failed: {result.stderr.decode()}")
```

### 2.2 NetlistGraph → TraceEdge 映射

```python
with open(netlist_json) as f:
    nl = json.load(f)

# nl 格式: {nodes: [...], edges: [...], fileTable: [...]}
node_map = {}  # id → TraceNode
for n in nl['nodes']:
    node_map[n['id']] = TraceNode(
        id=n['path'],
        name=n['name'],
        module=n['path'].split('.')[0],
        kind=_map_kind(n['kind'], n.get('direction')),
        width=n.get('bounds', [0, 0]),
    )

for e in nl['edges']:
    result.edges.append(TraceEdge(
        src=node_map[e['source']],
        dst=node_map[e['target']],
        kind=_map_edge_kind(e.get('edgeKind')),
        bit_lo=e['bounds'][0],
        bit_hi=e['bounds'][1],
    ))
```

### 2.3 已知问题：SIGSEGV bug

```
slang-netlist --resolve-assign-bits (启用 DFA) 在 picorv32 上会崩溃。
目前只能用 --no-resolve-assign-bits 生成基础 netlist。
等 slang-netlist 修复后，更新 Step 2.2 添加 DFA 路径分析。
```

---

## 第三步：用 pyslang AST 替换 TB 时序条件

**工作量：2 天 替换文件：graph_builder.py 的 always 块处理部分**

### 3.1 时钟与复位识别

```python
from pyslang.ast import (
    SymbolKind, ProceduralBlockKind, TimingControlKind,
    SensitivityListKind, ProceduralBlockSymbol
)

def extract_clock_domains(root):
    """提取所有 always_ff 的时钟域"""
    procs = []
    root.visit(lambda n: procs.append(n) if isinstance(n, ProceduralBlockSymbol) else None)

    domains = []
    for proc in procs:
        if proc.procedureKind != ProceduralBlockKind.AlwaysFF:
            continue
        if not hasattr(proc, 'body') or proc.body.kind != StatementKind.Timed:
            continue

        tc = proc.body.as_TimedStatement.timing
        if tc.kind == TimingControlKind.SignalEvent:
            clock = _extract_clock_signal(tc.as_SignalEventControl)
            domains.append({'block': proc.name, 'clock': clock})
        elif tc.kind == TimingControlKind.EventList:
            for ev in tc.as_EventListControl.events:
                if ev.kind == TimingControlKind.SignalEvent:
                    clock = _extract_clock_signal(ev.as_SignalEventControl)
                    domains.append({'block': proc.name, 'clock': clock})
    return domains
```

### 3.2 Guard 条件提取（简化版）

```python
def extract_guard_conditions(stmt):
    """从 ConditionalStatement 提取 guard 条件"""
    if stmt.kind != StatementKind.Conditional:
        return None
    predicate = stmt.predicate
    return str(predicate) if predicate else None
```

**注意**：这里只做**时钟/复位识别 + 简单 guard 条件字符串**。完整 condition extractor（支持 if/case/三元的嵌套条件树）放在 Step 9。

---

## 第四步：用语义 API 替换字符串解析

**工作量：2 天 替换文件：graph_builder.py, base.py**

### 4.1 端口方向

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

### 4.2 参数化位宽

```python
# 替换前
port_width = self.fd_adapter.extract_port_width(port_decl, scope=module)

# 替换后
width = p.type.bitWidth  # 整数，elaboration 后自动求值
```

### 4.3 路径构建

```python
# 替换前：手写路径拼接
path = f"{module_name}.{signal_name}"

# 替换后
path = var.getHierarchicalPath()  # 完整路径，跨文件唯一
```

---

## 第五步：清理死代码

**工作量：1 天 删除文件/代码**

**删除**：
- `src/trace/core/visitors/statement_visitor.py` (152行) — 死代码
- `src/trace/core/visitors/assignment_visitor.py` (29行) — 死代码
- `graph_builder.py` 里的 `_collect_stmts_with_context` 之后的手写遍历逻辑（已由 Step 2/3 替换）

**保留**：
- `src/trace/core/visitors/constraint_visitor.py` (543行) — **禁区**
- `src/trace/core/visitors/__init__.py` (0行) — 保留

**不修改**：
- `graph/models.py` (TraceNode/TraceEdge/EdgeKind/NodeKind) — 核心资产
- `unified_tracer.py` — 核心资产
- query 层 (`signal.py`, `module.py`, `load.py`, `clock_domain.py`) — 核心资产

---

## 第六步：图结构位精确化（Phase 2）

**工作量：待定 降级为 Phase 2**

原因：MultiDiGraph 改动影响 669 个 gold standard 测试，Step 3 的 slang-netlist 已经能给出位范围，边字段已足够。

**当前阶段只确认**：
- slang-netlist 的 NetlistGraph 已经输出 `bounds: [bit_lo, bit_hi]`
- TraceEdge 添加 `bit_lo`/`bit_hi` 字段即可使用

```python
@dataclass
class TraceEdge:
    # ... 现有字段 ...
    bit_lo: Optional[int] = None
    bit_hi: Optional[int] = None
```

**Phase 2 再考虑**：
- DiGraph → MultiDiGraph 的接口变更
- 位感知查询 API (`find_drivers(bit_lo=4, bit_hi=7)`)
- 位覆盖分析 (`get_bit_coverage()`)

---

## 第七步：ConditionExtractor

**工作量：1 周 新建文件：src/trace/core/condition_extractor.py**

**前置条件**：
- Step 1 完成（elaboration 可用）
- Step 2 完成（slang-netlist 生成 NetlistGraph）

**目标**：为 NetlistGraph 的边补充条件信息。

### 7.1 使用场景

```python
# Agent 问："sel=1 时 top.out 的驱动源是什么？"
tracer.find_drivers_under("top.out", conditions={"sel": 1})
# → 返回满足 sel=1 条件的驱动边
```

### 7.2 实现策略

```python
# Step 1: 遍历所有 ProceduralBlock
# Step 2: 对每个 if/case/三元，递归累积 cond_stack
# Step 3: 对每个赋值语句，记录 (lhs_path, cond_stack, stmt_loc)
# Step 4: 通过 lhs_path join 到 NetlistGraph 的边上
```

**不处理**：
- Class constraint 块（constraint_visitor.py 的职责）
- generate/if-generate（slang-netlist 已覆盖）

---

## 执行计划

| 周 | 任务 | 完成标志 |
|----|------|----------|
| Week 1 | 第一步 + 第二步（slang-netlist 基础集成） | 编译入口可用，RTL 驱动关系走 slang-netlist |
| Week 2 | 第三步（TB 时序结构 AST） + 第四步（语义 API） | always_ff 时钟识别，参数化位宽正确 |
| Week 3 | 第五步（清理死代码） + 回归测试 | 669 测试通过 |
| Week 4 | 第七步（ConditionExtractor 基础版） | guard 条件可查询 |
| Phase 2 | 第六步（MultiDiGraph + 位感知查询） | 位精确测试通过 |

**依赖关系**：
- Step 1 → 所有后续步骤（编译入口）
- Step 2 → Step 7（slang-netlist 为边提供 bit_lo/hi）
- Step 5（清理）→ 可以在 Week 1 并行做

---

## 测试失败处理策略

1. **RTL 驱动数变化**：slang-netlist 的 DFA 比手写遍历更精确，验证新结果是否正确，更新 gold standard
2. **参数化位宽变化**：新 API 返回整数（原字符串），更新测试断言
3. **EdgeKind 不匹配**：Step 5 后统一用 slang-netlist 的 edgeKind 枚举
4. **SIGSEGV**：Step 2 阶段只用 `--no-resolve-assign-bits`，DFA 相关测试标记 skip
5. **Constraint 测试失败**：不修改 constraint_visitor.py，相关测试不涉及
6. **条件未匹配**：Step 7 的 ConditionExtractor 回填检查

---

## 代码量估算

| 区域 | 现状 | 改造后 | 变化 |
|------|------|--------|------|
| graph_builder.py (手写 AST 遍历) | ~1500 行 | ~400 行 | -1100 行 |
| visitors/ (死代码) | 181 行 | 543 行 | +362 行 |
| constraint_visitor.py | 543 行 | 543 行 | 不动 |
| graph/models.py + query + unified_tracer | ~800 行 | ~800 行 | 不动 |
| **总计** | **~2520 行** | **~1786 行** | **-734 行** |

---

## 性能基准（实测）

| 设计 | 行数 | slang-netlist 时间 | 输出大小 |
|------|------|------------------|---------|
| picorv32.v | 3049 | 0.03s | 1.5 MB |
| serv RTL | 6484 | 0.02s | 893 KB |
| NVDLA SDP_CORE_x.v | 62275 | 0.66s | 33 MB |

结论：**elaboration 本身是秒级，缓存策略优先级低**。架构重点是分层数据源整合，不是性能优化。

---

## 改造后的收益

| 指标 | 改造前 | 改造后 |
|------|--------|--------|
| 核心逻辑代码量 | ~1500 行 | ~400 行 |
| 参数化位宽 | 字符串 `"W-1"` | 整数 `7` |
| RTL 驱动精度 | 部分赋值漏掉 | slang-netlist DFA（全量） |
| TB Class+Constraint | 唯一实现 | 不变（**禁区**） |
| TB 时序条件 | 手动遍历 | 语义 API 稳定 |
| pyslang 版本兼容 | 字符串匹配 | 枚举比较 |
| TB always/initial | 手写遍历 | AST + slang-netlist 分工 |
| 死代码 | 181 行 | 全量删除 |
| graph/query 层 | 保留 | 保留（核心资产） |
| condition 查询 | 不支持 | `find_drivers_under()` |