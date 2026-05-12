# sv_query 开发规范 (纪律要求增强版)

---

## 项目状态

- 维护: The sv_query team
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

## 2026-05-09 模块实例化追踪记录

### 问题分析
_connect_instance_ports_to_module 的问题：
1. 代码硬编码检查 `parts[1] == 'inst'`（期望实例名叫 'inst'）
2. 实际实例名叫 `u1`，所以匹配失败
3. ConnectionExtractor 已经创建了实例端口节点 `top.u1.d`, `top.u1.q`
4. 但没有建立连接边

### 已有 API
- `get_module_instances()` - 获取所有实例化
- `get_instance_connection(inst)` - 返回 `[(port, external), ...]`

### 修复方案
在 `_connect_instance_ports_to_module` 中：
1. 遍历所有实例节点（`top.u1.*` 格式）
2. 提取实例名（`u1`）和端口名（`d`, `q`）
3. 调用 `get_instance_connection` 获取映射
4. 创建 CONNECTION 边


## 测试标准补充说明

### 铁律17: 强断言原则 [生效]

**原则**：测试断言必须验证具体行为，不能只检查"不崩溃"

**禁止**：
```python
# ❌ 弱断言 - 0 个结果也通过
self.assertTrue(len(result) >= 0)
self.assertIsNotNone(result)  # 只检查非空，不检查内容

# ❌ 模糊断言 - 不知道期望什么
self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
```

**必须**：
```python
# ✅ 强断言 - 精确验证
self.assertEqual(len(result.drivers), 2)
self.assertIn('top.clk', [d.id for d in result.drivers])
self.assertEqual(result.confidence, 'high')

# ✅ 边界断言 - 验证极端情况
self.assertEqual(len(result.registers), 1, "单寄存器设计应有 1 个寄存器")
```

---

### 铁律18: 负面测试原则 [生效]

**原则**：每个功能必须有对应的负面测试，验证不支持的语法或错误输入有合理行为

**必须测试**：
1. 空 module / 空 always_ff
2. 不支持的语法（如 `fork...join_none` 在不支持时）
3. 错误输入（语法正确但语义错误）
4. 边界条件（0 个元素、巨型位宽、深层嵌套）

**示例**：
```python
def test_empty_module_no_crash(self):
    """空 module 不应崩溃"""
    source = 'module top(); endmodule'
    graph = self._build_graph(source)
    self.assertEqual(len(graph.nodes()), 0)

def test_unsupported_syntax_handled_gracefully(self):
    """不支持的语法应被跳过而非崩溃"""
    source = '''
module top(input clk);
    initial clk = 0;  # initial 不支持但不应崩溃
endmodule'''
    # 应该：不崩溃，但 initial 块被跳过
    graph = self._build_graph(source)
    self.assertEqual(len(graph.predecessors('top.clk')), 0)
```

---

### 铁律19: 金标准测试的 RTL 来源 [生效]

**原则**：金标准测试的 RTL 必须来自真实场景或芯片设计常见模式

**优先级**：
1. **真实开源项目片段**（ibex, cv32e40p 等）
2. **芯片设计常见模式**（如多路复用、跨时钟域握手）
3. **标准总线协议**（APB, AXI, AHB 子集）

**禁止**：
```python
# ❌ 人为构造的简单 RTL，不反映真实场景
source = '''
module top(input clk, output q);
    assign q = clk;
endmodule'''
```

**必须**：
```python
# ✅ 真实场景模式
source = '''
module apb_mux #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32
) (
    input  logic                psel,
    input  logic [ADDR_WIDTH-1:0] paddr,
    input  logic                penable,
    input  logic [DATA_WIDTH-1:0] pwdata,
    output logic [DATA_WIDTH-1:0] prdata,
    // 多路复用逻辑...
);'''
```

---

### 铁律20: 全面性原则 [生效]

**原则**：测试必须覆盖功能的所有使用路径

**必须覆盖**：
| 场景 | 测试内容 |
|------|----------|
| 基本路径 | 功能的核心使用场景 |
| 边界条件 | 参数为 0、1、最大值时的行为 |
| 组合路径 | 多个功能组合使用 |
| 跨层级 | 从顶层到叶节点的完整路径 |
| 多实例 | 同一模块被实例化多次 |

**检查清单**：
- [ ] 基本功能测试
- [ ] 空输入测试
- [ ] 单元素测试
- [ ] 多元素测试
- [ ] 错误输入测试
- [ ] 边界值测试
- [ ] 跨模块路径测试
- [ ] 多实例独立追踪测试


---

## 2026-05-10 SV 语法验证规则追加

### 铁律21: SV 语法必须通过双重工具验证 [生效]

**要求**：所有测试用例中的 RTL 源码必须同时通过 **Verilator** 和 **Verible** 验证

**理由**：
- Verilator 是工业级模拟器/linter，权威性高
- Verible 是 Google 维护的 SV 工具，对语法规范更严格
- 两者互补可发现更多语法问题
- pyslang 可能接受但标准工具不接受的语法需要修正

**验证方式** [生效]：
```bash
# 单文件验证（两者都需通过）
verilator --lint-only -sv your_file.sv
verible-verilog-lint your_file.sv

# 或使用自动化脚本（项目根目录）
./scripts/verify_sv_syntax.py sim/tests/integration/test_*.py
```

**校验脚本**：`scripts/verify_sv_syntax.py`
- 自动提取测试文件中的 RTL 并双重验证
- 输出通过/失败统计

**已知限制**：
- 参数化模块 `#()` 在某些临时文件场景可能仅 CLI 直接验证通过
- 遇到此类情况时以 CLI 验证结果为准

---

## 2026-05-10 测试纪律追加

### 铁律22: 测试断言必须验证具体行为 [生效]

**禁止**：
```python
# ❌ 弱断言 - 只检查不崩溃
self.assertIsNotNone(graph)
self.assertTrue(len(result) >= 0)

# ❌ 模糊断言 - 不知道期望什么
self.assertIn(result.confidence, ['high', 'medium', 'uncertain'])
```

**必须**：
```python
# ✅ 强断言 - 精确验证
self.assertIn(('top.clk', 'top.q'), clock_edges,
    "应有CLOCK边: clk -> q")
self.assertEqual(len(result.drivers), 2,
    "应有2个驱动源")

# ✅ 边界断言 - 验证极端情况
self.assertEqual(d_node.width, (7, 0),
    f"[7:0] 应该是 (7, 0)，实际是 {d_node.width}")
```

---

## 2026-05-10 工具安装记录

### Verilator
- 版本：5.048 (2026-04-26)
- 安装：`brew install verilator`
- 用途：SV 语法验证 (`verilator --lint-only -sv`)

### Verible
- 版本：v0.0-4053-g89d4d98a
- 安装：GitHub release 下载 (macOS)
- 路径：`~/my_daily_proj/verible-v0.0-4053-g89d4d98a-macOS/`
- 用途：SV 语法验证（与 Verilator 双重验证）

## 2026-05-12 Class OOP 功能扩展

### 铁律23: Class 组合关系 (Composition) [生效]

**功能**：检测 ClassPropertyDeclaration 的类型是否为类引用 (NamedType)，创建 IS_INSTANCE_OF 边

```python
# NamedType 检测
type_node = getattr(decl, 'type', None)
if getattr(type_node, 'kind') == SyntaxKind.NamedType:
    type_name = str(type_node.name).strip()  # 类名
    graph.add_trace_edge(TraceEdge(
        src=property_node_id,
        dst=type_name,
        kind=EdgeKind.IS_INSTANCE_OF,
    ))
```

**示例**：
```systemverilog
class inner { rand int x; }
class outer { inner my_inner; }  // my_inner 是 inner 的实例
```

**创建边**：
```
outer.my_inner --IS_INSTANCE_OF--> inner
```

### 铁律24: Constraint SUPER_CALL 边 [生效]

**功能**：检测 constraint block 中的 `super.<constraint_name>` 调用，创建 SUPER_CALL 边

```python
# super.c1 检测
item_str = str(item).strip()
if item_str.startswith('super.'):
    super_call_name = item_str.split('.')[1].rstrip(';').strip()
    parent = self.hierarchy.get_parent(cls_name)
    parent_constr_id = f"{parent}.{super_call_name}"
    graph.add_trace_edge(TraceEdge(
        src=f"{block_id}::expr_{idx}",
        dst=parent_constr_id,
        kind=EdgeKind.SUPER_CALL,
    ))
```

**示例**：
```systemverilog
class packet;
    constraint c1 { addr > 0; }
endclass

class extended extends packet;
    constraint c1 { super.c1; addr > 100; }  // 增量扩展
endclass
```

**创建边**：
```
extended.c1::expr_0 --SUPER_CALL--> packet.c1
extended.c1::expr_1 --HAS_LHS--> extended.addr
```

### 铁律25: Constraint 多语句 Block 展开 [生效]

**功能**：if/else/implication 中的多语句 `{ }` 块展平为多个 CONSTRAINT_EXPR 节点

**示例**：
```systemverilog
constraint c1 { if (en) { a == 1; b == 2; } }
constraint c2 { a == 5 -> { b == 10; d == 20; } }
```

**创建边**：
```
if_0 --HAS_CONSEQUENT--> cons_0
if_0 --HAS_CONSEQUENT--> cons_1
impl_0 --HAS_CONSEQUENT--> result_0
impl_0 --HAS_CONSEQUENT--> result_1
```

---

## 2026-05-12 新增 EdgeKind

| 边类型 | 值 | 用途 |
|--------|-----|------|
| CONTAINS_MEMBER | 16 | CLASS → CLASS_PROPERTY (组合成员) |
| IS_INSTANCE_OF | 17 | CLASS_PROPERTY → 被引用的类 |
| SUPER_CALL | 18 | CONSTRAINT_EXPR → 父类约束 (增量扩展) |

---

## 2026-05-12 新增测试文件

| 文件 | 测试数 | 场景 |
|------|--------|------|
| test_composition_chain.py | 19 | 组合关系 (IS_INSTANCE_OF) |
| test_constraint_override.py | 7 | Constraint SUPER_CALL / 覆盖 |
| test_complex_inheritance.py | 10 | 复杂继承场景综合测试 |
| test_constraint_complete.py | 75 | Constraint 完整功能测试 |

---

## 工具获取
```bash
# Verilator
brew install verilator

# Verible (需手动下载)
curl -L "https://github.com/chipsalliance/verible/releases/download/v0.0-4053-g89d4d98a/verible-v0.0-4053-g89d4d98a-macOS.tar.gz" -o verible.tar.gz
tar -xzf verible.tar.gz -C ~/
```

