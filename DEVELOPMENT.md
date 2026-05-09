# sv_query 开发规范 (纪律要求增强版)

---

## 项目状态

- 维护: 方浩
- 更新: 2026-05-04
- 继承自: sv-trace 开发纪律

---

## 状态标注

| 状态 | 说明 | 触发校验 |
|------|------|---------|
| [草案] | AI生成，未经确认 | 人工审查 |
| [审查中] | 经评审，待人工 | 人工审查 |
| [生效] | 已确认执行 | CI强制校验 |
| [废弃] | 已过时，不再使用 | 无 |

---

## 第一部分：技术路线铁律 (不可妥协)

### 铁律1: AST唯一数据源 [生效]

**必须**：所有硬件语义提取必须且仅能通过 pyslang AST 遍历实现

**严禁**：将源码转为字符串后用正则分析

**原理**：正则无法正确处理拼接赋值、宏展开、位选择、注释中的代码

**违规后果**：
- 时序路径分析跳过拼接赋值
- 位选择信号被混淆为同一信号

**校验方式** [生效]
```bash
grep -rn "re\.(findall|match|search)" src/trace/core/
# 允许: 日志格式化、CLI参数解析
# 禁止: SV源码分析
```

### 铁律2: 位精确性不可妥协 [生效]

**必须**：信号追踪必须保留完整的位级信息

**原理**：`data[7:0]` 和 `data[15:8]` 是不同的硬件信号

**违规后果**：跨时钟域分析、时序路径分析出错

**校验方式** [草案]
- graph_models.py 的 width 字段必须正确传递

### 铁律3: 不可信则不输出 [生效]

**必须**：无法解析时必须显式报错或返回 confidence: "uncertain"

**严禁**：静默跳过

**示例**：
```python
# 正确
if not parsed:
    return SignalChain(
        drivers=[],
        confidence="uncertain",
        caveats=["无法解析 always 块"]
    )

# 错误
if not parsed:
    return SignalChain(drivers=[])  # 缺少 confidence
```

---

## 第二部分：架构铁律

### 铁律4: 模型即契约 [生效]

**必须**：
- models.py 中每个数据字段必须有对应的 AST 填充代码
- 未实现字段必须删除或标注 `# TODO`

**原理**：数据模型是核心契约，僵尸字段导致下游误判

**违规后果**：下游读取空字段导致运行时错误

**校验方式** [审查中]
- 静态分析 dataclass 字段使用率
- JSON 输出时检测空字段

### 铁律5: 原子化必须保持 [生效]

**必须**：一个语法节点对应一个解析器/collector 文件

**禁止**：在一个文件中处理多种 AST 节点类型

### 铁律6: Schema即宪法 [生效]

**必须**：所有模块输出必须严格遵循 Schema 定义

**校验方式** [草案]
- JSON Schema validator

---

## 第三部分：开发流程铁律

### 铁律7: 新功能必须先有边界测试 [生效]

**必须**：
1. 先推导金标准
2. 运行被测代码
3. 与金标准逐项对比
4. 完全一致才能提交

**示例格式**：
```python
# 金标准 (Golden Standard)
# 测试设计: data_out = always_ff 时钟驱动 data_in
# 预期结果:
#   - data_out 的驱动: [data_in] (always_ff)
#   - data_in 的负载: [data_out] (always_ff)

# 实际输出必须与上述完全一致
```

### 铁律8: 文档与代码同步更新 [生效]

**必须**：代码变更必须同步更新文档

---

## 第四部分：用户导向铁律

### 铁律10: 每次API返回必须有置信度标注 [生效]

**必须**：
```python
@dataclass
class SignalChain:
    root: str
    drivers: List[TraceNode]
    confidence: str  # 必须: "high", "medium", "uncertain"
    caveats: List[str]
```

### 铁律11: 必须提供Agent调用示例 [生效]

**必须**：每个新功能必须包含示例

**示例**：
```python
# === 示例 ===
# 追踪信号完整链路
tracer = UnifiedTracer(parser)
chain = tracer.trace_signal("data", module="top")
# 输出包含驱动、负载、置信度
```

---

## 第五部分：金标准测试原则

### 铁律13: 金标准测试 [生效]

核心规则：

1. **先推导金标准**：脱离被测代码，从 RTL 人工推导
   ```python
   # RTL: assign data = din;
   # 金标准: driver(data) = [din]
   ```

2. **明确记录**：在测试代码注释中以表格形式记录
   ```python
   # | 信号   | 驱动    | 来源 |
   # |--------|---------|------| 
   # | data   | [din]  | assign |
   ```

3. **对比验证**：运行被测代码，与金标准逐项对比
   ```python
   assert set(gold[s]) == set(actual.get(s, []))
   ```

4. **完全一致才能提交**

---

## 第六部分：核心原则

| 原则 | 说明 |
|------|------|
| AST唯一 | 正则不能碰源码 |
| 位精确性 | data[7:0] ≠ data[15:8] |
| 不可信不输出 | 标 confidence |
| 文档同步 | 代码即文档 |
| 承诺可验证 | 都在代码中 |

---

## 第七部分：检查清单 (新功能提交流程)

- [ ] 铁律13: 是否先推导金标准再验证？
- [ ] 铁律1: 是否使用 pyslang AST 而非正则？
- [ ] 铁律2: 信号是否保留完整位级信息？
- [ ] 铁律3: 无法解析时返回 uncertain？
- [ ] 铁律4: 数据字段都有 AST 填充代码？
- [ ] 铁律6: Schema 变更同步更新？
- [ ] 铁律7: 新功能附带边界测试？
- [ ] 铁律8: 文档同步更新？
- [ ] 铁律10: API 返回包含 confidence？
- [ ] 铁律11: 提供调用示例？

---

## 第八部分：四层架构

```
┌─────────────────────────────────────────────────────────────┐
│ Query Layer: unified_tracer.py                            │
├─────────────────────────────────────────────────────────────┤
│ Graph Layer: graph_models.py (networkx)                    │
├─────────────────────────────────────────────────────────────┤
│ Builder Layer: graph_builder.py                            │
├─────────────────────────────────────────────────────────────┤
│ Extractor Layer: base.py + pyslang_adapter.py             │
└─────────────────────────────────────────────────────────────┘
```

### 文件规则

| 功能 | 文件 |
|------|------|
| 统一入口 | unified_tracer.py |
| 图模型 | graph_models.py |
| 构建器 | graph_builder.py |
| AST遍历 | base.py |
| pyslang适配 | pyslang_adapter.py |
| 信号查询 | query_signal.py |
| 模块查询 | query_module.py |
| 时钟域查询 | query_clock_domain.py |

### 禁止模式

- ❌ 禁止在 Query 层直接操作 Graph
- ❌ 禁止在 Tracer 中修改 Graph
- ❌ 禁止硬编码 Parser
- ❌ 禁止创建新 Graph 类
- ❌ 禁止修改 networkx 内部

---

## 第九部分：Git 规则

### 提交信息格式

```
<type>: <描述>

Types:
- feat: 新功能
- fix: Bug修复
- refactor: 重构
- docs: 文档
- test: 测试
```

---

## 第十部分：CI 校验

### 自动校验脚本

位置: `.github/workflows/check_discipline.py`

检测项：
1. 正则使用 (用于��码分析)
2. 目录深度 (>3)
3. 禁止导入 (igraph, graphviz)
4. 缺少 confidence 字段

---

*更新时间: 2026-05-04*
*下次审查: 2026-07-01*
*继承自: sv-trace 开发纪律*

---

## 2026-05-05 架构修正

### 铁律14: Syntax中间层 [生效]

**必须**：GraphBuilder 必须通过 PyslangAdapter (base.py) 获取信息

**禁止**：直接访问 parser.modules / parser.assignments 等属性

**原理**：实现解耦，PyslangAdapter 将 pyslang AST 适配为统一接口

**示例**：
```python
# 正确
adapter = PyslangAdapter(parser)
modules = adapter.get_modules()
for module in modules:
    assignments = adapter.get_assignments(module)

# 错误
for module in parser.modules:  # 禁止直接访问
    for assign in module.assignments:
```

### 架构对齐

```
Builder Layer: GraphBuilder
    ↓ 调用
Syntax Layer: PyslangAdapter (base.py)
    ↓ 遍历
Extractor Layer: pyslang AST
```

---

## 2026-05-07 Visitor 模式重构 [生效]

### 铁律15: Visitor 模式必须使用 [生效]

**必须**：AST 遍历和语法节点处理必须使用 Visitor 模式

**禁止**：
- 在单个方法中使用 if-elif 链处理所有语法类型
- 直接在 graph_builder.py 中添加语法类型判断

**原因**：
- SystemVerilog 语法类型 200+，if-elif 不可维护
- Visitor 模式符合开闭原则，新增语法不破坏现有代码
- 每个语法类型独立方法，可单独测试

**正确做法**：
```python
# 每个语法类型 → 独立的 visitor 方法
class StatementVisitor:
    def visit_while_loop(self, node):
        ...
    
    def visit_for_loop(self, node):
        ...

# 禁止：
# if kind and 'While' in str(kind):
#     ...
# elif kind and 'For' in str(kind):
#     ...
```

### Visitor 架构

```
sv_visitor/
├── __init__.py
├── base_visitor.py          # 抽象基类 + 通用遍历
├── statement_visitor.py    # 语句处理 (while/for/case/if)
├── assignment_visitor.py   # 赋值处理 (assign/<=)
├── declaration_visitor.py # 声明处理 (module/interface/class)
└── block_visitor.py         # 块处理 (begin-end/always)
```

### 新语法支持流程

1. 在对应 Visitor 中添加 `visit_<syntax_type>` 方法
2. 编写金标准测试
3. 在 base_visitor.py 中注册到 dispatch 表

---

## 架构演进

```
Phase 1 (当前):  if-elif 链 → 独立文件重构
Phase 2:        Visitor 基类建立
Phase 3:        每个语法族独立 Visitor
Phase 4:        完整 Visitor 架构
```

## 2026-05-09 设计纪律追加

### 铁律16: 改动前先评估理想实现 [生效]

**要求**：在改动代码前，必须先评估已有的实现方式

**步骤**：
1. 理解现有代码的结构和约束
2. 找出"好消息"（已存在的字段/方法/模式）
3. 评估改动对架构的影响范围
4. 如果理想实现太复杂，主动与用户确认后再执行

**禁止**：
- ❌ 不评估就直接用"简单方案"破坏架构
- ❌ 发现问题后不分析根本原因就修补
- ❌ 忽略已存在的字段/模式重复实现

**示例**：
```
# 错误做法
"直接改 kind 算了" → 破坏 query_module.py 的端口发现

# 正确做法
分析：端口有 PORT_OUT + is_port 标记的需求
评估：parent, bit_range 已存在，is_port 字段可以复用
确认：用户同意后再实现
```

---
