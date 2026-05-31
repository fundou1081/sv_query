# Req-5/6/7/8 与 Driver/Load 功能关系评估

## 现有架构分析

### 核心组件

| 组件 | 文件 | 功能 |
|------|------|------|
| `DriverExtractor` | graph_builder.py | 从 AST 提取驱动关系 (assign/always) |
| `LoadExtractor` | graph_builder.py | 从 AST 提取负载关系 |
| `ConnectionExtractor` | graph_builder.py | 从 AST 提取实例端口连接 |
| `GraphBuilder` | graph_builder.py | 协调所有 extractor，构建完整图 |
| `SignalTracer` | query/signal.py | 追踪信号的驱动源和负载 |
| `LoadTracer` | query/load.py | 追踪信号的后继 |
| `GraphTraversal` | graph_traversal.py | 共享的图遍历基类 |

### 数据流

```
Pyslang AST
    │
    ▼
┌─────────────────┐
│   GraphBuilder   │
│   .build()      │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌─────────┐ ┌─────────┐ ┌─────────────────┐
│ Driver  │ │  Load   │ │ Connection      │
│Extractor│ │Extractor│ │ Extractor       │
└────┬────┘ └────┬────┘ └────────┬────────┘
     │           │              │
     ▼           ▼              ▼
     │           │         CONNECTION 边
     │           │         (实例端口)
     ▼           ▼
  DRIVER边     DRIVER边
(连续赋值)  (负载追踪)
     │           │
     └─────┬─────┘
           ▼
    ┌─────────────┐
    │ SignalGraph │
    │ (NetworkX) │
    └─────┬─────┘
          │
    ┌────┴────────┐
    ▼             ▼
┌────────┐  ┌────────┐
│Signal  │  │ Load  │
│Tracer  │  │Tracer │
└────────┘  └────────┘
```

---

## 现有功能覆盖分析

### DriverExtractor 能力

```python
class DriverExtractor:
    def extract(self) -> ExtractorResult:
        # 1. ContinuousAssign → DRIVER 边
        # 2. AlwaysBlock → 分析时钟/复位 → DRIVER 边
        # 3. ConditionalStatement (if-else) → 条件赋值
```

**已处理**:
- `assign` 语句 → `EdgeKind.DRIVER, assign_type="continuous"`
- `always @(posedge clk)` → `EdgeKind.DRIVER, assign_type="nonblocking"`
- `always @(posedge clk) if (en)` → 条件 DRIVER 边
- 时钟识别 → `EdgeKind.CLOCK`
- 复位识别 → `EdgeKind.RESET`

**未处理**:
- Function/Task 内部的赋值
- generate 块内的驱动关系

### LoadExtractor 能力

```python
class LoadExtractor:
    def extract(self) -> ExtractorResult:
        # 查找信号的负载
```

**已处理**:
- 端口连接关系

**未处理**:
- Function/Task 内部的使用

### ConnectionExtractor 能力

```python
class ConnectionExtractor:
    def extract(self) -> ExtractorResult:
        # 遍历 HierarchyInstantiation
        # 创建 CONNECTION 边
```

**已处理**:
- 模块实例的端口连接

**未处理**:
- generate 块内的实例

---

## 与 Req-5/6/7/8 的关系

### Req-5: generate 内的实例支持

**现状**: ConnectionExtractor 只遍历模块级成员，不进入 generate 块

**需要**:
- 让 ConnectionExtractor 进入 GenerateBlock 遍历
- 或者新增 GenerateInstanceExtractor

**影响**: ❌ 影响信号追踪的跨模块能力

---

### Req-6: 函数内部逻辑提取

**现状**: ❌ 完全未实现

**原因**: DriverExtractor 只处理模块级 always/assign，不进入 FunctionDeclaration

**需要**:
- 新增 `FunctionBodyExtractor`
- 或者扩展 DriverExtractor 支持函数体

**影响**: ❌ 无法追踪函数内部信号

---

### Req-7: always block 内部语句提取

**现状**: ✅ 大部分已实现

DriverExtractor 已处理:
- always block 识别
- 时钟/复位提取
- 条件赋值追踪

**未处理**:
- 嵌套 begin...end 块的完整语句列表
- 多个信号的并行赋值

**需要**: 增强语句提取的完整性

---

### Req-8: SignalTracer 信号追踪

**现状**: ⚠️ 框架已存在，实际功能依赖 GraphBuilder

**依赖关系**:
```
SignalTracer.trace(signal)
    │
    ├── 依赖 SignalGraph.nodes() 包含该信号
    │
    ├── 依赖 SignalGraph.edges() 包含 DRIVER 边
    │
    └── 依赖 GraphBuilder.build() 完整构建
```

**当前问题**:
1. GraphBuilder 可能遗漏某些节点（特别是 generate 内的）
2. GraphBuilder 遗漏函数内部的赋值

**需要**:
1. 确保 GraphBuilder 完整构建 (Req-5, 7)
2. 补充函数体处理 (Req-6)

---

## 修正后的统一方案

### 方案思路调整

**原方案**: 新增 StatementExtractor 统一处理

**新方案**: 增强现有 Extractor，让 DriverExtractor/ConnectionExtractor 更完整

### 修改点

| Req | 修改组件 | 修改内容 | 实际状态 |
|-----|---------|----------|----------|
| Req-5 | ConnectionExtractor | 进入 GenerateBlock 遍历实例 | ✅ 已实现 |
| Req-6 | SubroutineExpander | 提取函数内部赋值关系 | ✅ 已实现 |
| Req-7 | DriverExtractor | 增强 always block 内部语句提取 | ✅ 已实现 |
| Req-8 | GraphBuilder | 协调新增的 Extractor | ✅ 已实现 |

### 实际实现 (2026-05-31)

- `get_generate_instances()` (graph_builder.py:2084, 2108) - generate 实例支持
- `SubroutineExpander` (graph_builder.py:2474) - 函数/任务内联展开
- `_get_generate_block_name()` (line 2017-2018) - generate block 命名
- DriverExtractor 已处理 always block 内部语句

### 数据流修正

```
                    ┌─────────────────┐
                    │   GraphBuilder   │
                    │   .build()      │
                    └────────┬────────┘
                             │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Driver    │  │  Connection  │  │  Subroutine  │
│  Extractor  │  │  Extractor   │  │  Expander    │
│  (已增强)    │  │  (已增强)     │  │  (已实现)    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       ▼                 ▼                 ▼
   DRIVER边          CONNECTION边        DRIVER边
 (always/assign)   (实例连接)      (function内部)
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
                ┌─────────────┐
                │ SignalGraph │
                └─────┬───────┘
                      │
                      ▼
               ┌─────────────┐
               │SignalTracer │
               │ (Req-8完成) │
               └─────────────┘
```

---

## 技术评估更新

### Phase 1: 增强 ConnectionExtractor (Req-5)

**目标**: 支持 generate 块内的实例

**修改**:
```python
class ConnectionExtractor:
    def extract(self) -> ExtractorResult:
        # 进入 GenerateBlock 遍历
        for member in module.members:
            if member.kind == SyntaxKind.GenerateBlock:
                self._extract_from_block(member)
```

**工时**: 0.5 天

### Phase 2: 增强 DriverExtractor (Req-7)

**目标**: 完整提取 always block 内部语句

**修改**:
```python
class DriverExtractor:
    def _collect_stmts_with_context(self, n, ctx=None, d=0, _s=None):
        # 增强：递归提取 begin...end 块内的所有语句
```

**工时**: 1-2 天

### Phase 3: 新增 FunctionExtractor (Req-6)

**目标**: 提取函数内部赋值

**新增**:
```python
class FunctionExtractor:
    """提取函数/任务内部的驱动关系"""
    
    def extract(self) -> ExtractorResult:
        # 遍历 FunctionDeclaration.body
        # 生成 DRIVER 边（函数内部赋值）
```

**工时**: 1-2 天

### Phase 4: 集成与调试 (Req-8)

**目标**: 确保 SignalTracer 能追溯所有路径

**修改**:
```python
class GraphBuilder:
    def build(self) -> SignalGraph:
        # 添加 FunctionExtractor
        func_ext = FunctionExtractor(self.adapter)
        func_result = func_ext.extract()
        # 合并到 graph
```

**工时**: 1-2 天

---

## 总工时估算 (修正后)

| Phase | 内容 | 工时 |
|-------|------|------|
| Phase 1 | ConnectionExtractor 增强 (Req-5) | 0.5天 |
| Phase 2 | DriverExtractor 增强 (Req-7) | 1-2天 |
| Phase 3 | FunctionExtractor 新增 (Req-6) | 1-2天 |
| Phase 4 | 集成与调试 (Req-8) | 1-2天 |

**总计**: 3.5 - 6.5 天

---

## 关键洞察

1. **SignalTracer 已经存在**，问题在于 GraphBuilder 构建的图不完整
2. **DriverExtractor 已经处理 always block**，但 generate 块和函数体是空白
3. **ConnectionExtractor 已经处理实例连接**，但只在模块级

### 优先级建议

| Req | 修改量 | 收益 | 建议优先级 |
|-----|-------|------|-----------|
| Req-5 | 小 | 跨模块追踪完整 | P2 |
| Req-7 | 中 | always 追踪完整 | P1 |
| Req-6 | 中 | 函数追踪能力 | P2 |
| Req-8 | - | 依赖上述三项 | 收尾 |

**建议**: 先完成 Req-7 (always block)，因为它覆盖最常见的时序逻辑场景