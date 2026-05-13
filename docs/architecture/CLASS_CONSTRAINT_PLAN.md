# Class & Constraint 深度拆解开发方案

**状态**: 设计中  
**创建日期**: 2026-05-11  
**最后更新**: 2026-05-11

---

## 背景

用户需要在 sv_query 中提取 class 内各种内容，尤其是 constraint 的深度追踪。需要建立完整双向约束追踪能力。

---

## 设计原则

1. **方向 A**：Class 作为独立命名空间进 SignalGraph
2. **ClassHierarchy 独立实现**：extends 链单独维护，不进图，只给下游提供 parent 查询
3. **constraint 深度拆解**：if/else 建立独立 CONSTRAINT_IF / CONSTRAINT_ELSE 节点
4. **开闭原则**：使用 Visitor 模式，每个 constraint 语法类型独立方法

---

## pyslang Class AST 完整结构

### ClassDeclaration 成员 items[] 类型

| 元素 | pyslang kind |
|------|-------------|
| rand 变量 | `ClassPropertyDeclaration` |
| constraint 块 | `ConstraintDeclaration` |
| 方法 | `ClassMethodDeclaration` |

### ConstraintBlock.items[] 类型

| 约束种类 | pyslang kind | 可继续拆？ |
|----------|-------------|-----------|
| 表达式约束 | `ExpressionConstraint` → `InsideExpression` | ✅ |
| 表达式约束 | `ExpressionConstraint` → `BinaryExpression` | ✅ |
| 表达式约束 | `ExpressionConstraint` → `ConditionalExpression` | ✅ |
| if/else 约束 | `ConditionalConstraint` | ✅ 独立节点 |
| implication 约束 | `ImplicationConstraint` | ✅ 左/右独立 |
| unique 约束 | `UniquenessConstraint` | ✅ |
| solve before | `SolveBeforeConstraint` | ✅ |
| foreach 循环 | `ForeachConstraint` | ✅ |

---

## NodeKind 扩展

```python
CLASS = auto()                  # class 定义节点
CLASS_INSTANCE = auto()          # class 实例 (packet p = new())
CLASS_PROPERTY = auto()         # rand 变量 + 普通成员变量
CONSTRAINT_BLOCK = auto()       # constraint c { ... } 命名块
CONSTRAINT_EXPR = auto()        # 单条表达式约束
CONSTRAINT_IF = auto()          # if 分支
CONSTRAINT_ELSE = auto()        # else 分支
CONSTRAINT_IMPLIES = auto()     # implication 左部 (en)
CONSTRAINT_UNIQUE = auto()      # unique { ... }
CONSTRAINT_SOLVE = auto()       # solve A before B
CONSTRAINT_FOREACH = auto()     # foreach 循环
CONSTRAINT_RANGE = auto()       # inside {0,1,2} 的集合
```

---

## EdgeKind 扩展

```python
CONSTRAINS = auto()      # CLASS_PROPERTY ← 约束管控
HAS_CONDITION = auto()   # CONSTRAINT_IF → CLASS_PROPERTY (条件变量)
HAS_CONSEQUENT = auto()  # CONSTRAINT_IF → CONSTRAINT_EXPR
HAS_ALTERNATE = auto()   # CONSTRAINT_ELSE → CONSTRAINT_EXPR
HAS_LHS = auto()         # CONSTRAINT_EXPR → operand
HAS_RHS = auto()         # CONSTRAINT_EXPR → operand
HAS_MEMBER = auto()      # CONSTRAINT_UNIQUE → CLASS_PROPERTY
HAS_LOOP_VAR = auto()    # CONSTRAINT_FOREACH → CLASS_PROPERTY
HAS_BEFORE = auto()      # CONSTRAINT_SOLVE → CLASS_PROPERTY (before)
HAS_AFTER = auto()       # CONSTRAINT_SOLVE → CLASS_PROPERTY (after)
```

---

## 完整节点层级结构

```
CLASS: packet
  │
  ├── CLASS_PROPERTY: addr        ← rand 变量（叶子）
  ├── CLASS_PROPERTY: en          ← 普通成员变量
  ├── CLASS_PROPERTY: data
  │
  ├── CONSTRAINT_BLOCK: c_valid
  │     ├── CONSTRAINT_IF: if_branch
  │     │     ├── condition: en
  │     │     └── consequent: addr == 1
  │     │           ├── op: "=="
  │     │           ├── lhs: addr
  │     │           └── rhs: 1
  │     └── CONSTRAINT_ELSE: else_branch
  │           └── alternate: addr == 2
  │                 ├── op: "=="
  │                 ├── lhs: addr
  │                 └── rhs: 2
  │
  ├── CONSTRAINT_BLOCK: c_addr
  │     └── CONSTRAINT_EXPR: addr inside {0,1,2}
  │           ├── op: "inside"
  │           ├── lhs: addr
  │           └── range: {0, 1, 2}
  │
  └── CONSTRAINT_BLOCK: c_multi
        ├── CONSTRAINT_EXPR: addr inside {...}
        ├── CONSTRAINT_EXPR: data == en ? 8'hFF : 8'h00
        │     ├── op: "?:"
        │     ├── cond: en
        │     ├── then: 8'hFF
        │     └── else: 8'h00
        ├── CONSTRAINT_UNIQUE: unique {addr, data}
        │     └── members: [addr, data]
        └── CONSTRAINT_SOLVE: solve addr before data
              ├── before: [addr]
              └── after: [data]
```

---

## ClassHierarchy（extends 链，独立实现）

```python
class ClassHierarchy:
    """只维护 class extends 关系，不进图"""
    
    def add_class(self, name, extends: Optional[str] = None): ...
    def get_parent(self, class_name) -> Optional[str]: ...
    def get_ancestors(self, class_name) -> List[str]: ...  # 递归向上
    def get_subclasses(self, class_name) -> List[str]: ... # 向下
    def is_ancestor_of(self, ancestor, descendant) -> bool: ...
```

**不进 SignalGraph**，纯数据层。下游任务自己判断是否需要向上追约束。

实现位置：`src/trace/core/class_hierarchy.py`（新文件）

---

## 实例映射表

```python
# UnifiedTracer 或独立 ClassTracer 维护
_instance_to_class: Dict[str, str]  # "top.p" → "packet"

# trace("top.p.addr") 时:
# 1. 查 _instance_to_class["top.p"] = "packet"
# 2. 找 CLASS_PROPERTY "packet.addr"
# 3. 从该节点 ←CONSTRAINS 追溯所有约束
```

在 `packet p = new()` 实例化时填入映射。

---

## 追踪能力

| 查询 | 路径 |
|------|------|
| `addr` 被哪些约束管控 | CLASS_PROPERTY.addr ←CONSTRAINS← (所有相关 CONSTRAINT_*) |
| `c_valid` 管控哪些变量 | CONSTRAINT_BLOCK.c_valid →CONSTRAINS→ addr, en |
| `en` 触发什么后果 | CLASS_PROPERTY.en →HAS_CONDITION→ IF →HAS_CONSEQUENT→ ... |
| `unique {addr,data}` 的成员 | CONSTRAINT_UNIQUE →HAS_MEMBER→ [addr, data] |
| `solve A before B` | CONSTRAINT_SOLVE →HAS_BEFORE→ A, →HAS_AFTER→ B |
| 子类约束是否包含父类约束 | ClassHierarchy.get_ancestors() |

---

## Visitor 架构（constraint_visitor.py）

```
class ConstraintVisitor:
    """每个 constraint 语法类型独立 visitor 方法"""
    
    def visit_expression_constraint(self, node, ctx):
        """ExpressionConstraint → CONSTRAINT_EXPR"""
    
    def visit_conditional_constraint(self, node, ctx):
        """ConditionalConstraint → CONSTRAINT_IF + CONSTRAINT_ELSE"""
        # 关键：if 和 else 分支各自独立节点
    
    def visit_implication_constraint(self, node, ctx):
        """ImplicationConstraint → CONSTRAINT_IMPLIES + CONSTRAINT_EXPR"""
    
    def visit_uniqueness_constraint(self, node, ctx):
        """UniquenessConstraint → CONSTRAINT_UNIQUE"""
    
    def visit_solve_before_constraint(self, node, ctx):
        """SolveBeforeConstraint → CONSTRAINT_SOLVE"""
    
    def visit_foreach_constraint(self, node, ctx):
        """ForeachConstraint → CONSTRAINT_FOREACH"""
```

文件位置：`src/trace/core/visitors/constraint_visitor.py`

---

## 实现阶段

### Phase 1: ClassHierarchy + pyslang constraint 全扫描
- 实现 `ClassHierarchy`（extends 链维护）
- 扫描 pyslang，确认所有 constraint 类型覆盖
- 编写金标准测试覆盖所有语法类型

### Phase 2: 节点 + 边（新建 class_graph_builder.py）
- `NodeKind` / `EdgeKind` 扩展
- `ClassGraphBuilder` + `ConstraintVisitor`
- 三级节点结构 + 所有边类型
- 核心测试（金标准）

### Phase 3: DriverExtractor 支持 p.addr 语法
- instance 映射表
- `p.addr` 路径解析进 DriverExtractor

### Phase 4: unique / solve_before / foreach 支持
- CONSTRAINT_UNIQUE / CONSTRAINT_SOLVE / CONSTRAINT_FOREACH visitor
- 完整金标准测试

---

## 现有代码影响评估

| 文件 | 影响 |
|------|------|
| `graph_models.py` | 扩展 NodeKind / EdgeKind |
| `graph_builder.py` | 无影响（ClassGraphBuilder 独立） |
| `base.py` | 扩展 `get_classes()` / 新增 `get_class_members()` |
| `unified_tracer.py` | 新增 ClassTracer 注册 |
| `visitors/` | 新建 `constraint_visitor.py` |

**最小化影响**：现有 module 级别追踪逻辑完全不动。

---

## 铁律要求

- [铁律13] 金标准测试：每新增 constraint 类型，必须先推导金标准再验证
- [铁律15] Visitor 模式：每个 constraint 类型独立 visitor 方法，不使用 if-elif 链
- [铁律16] 改动前先评估理想实现：不动现有 module 追踪逻辑

---

*本方案为开发备忘，实施前需评审确认*

---

## RTL 来源

### 1. OpenTitan 项目

**路径**: `~/my_dv_proj/opentitan/`

用于真实 UVM 序列类场景，特别是 constraint 和 class extends 模式。

| 路径 | 用途 |
|------|------|
| `hw/top_earlgrey/ip_autogen/rstmgr/dv/env/seq_lib/rstmgr_base_vseq.sv` | 大量 `rand` + `inside` 约束的真实序列类 |
| `hw/ip/keymgr/dv/tests/keymgr_base_test.sv` | `class extends` 继承模式示例 |
| `hw/ip/keymgr/dv/env/seq_lib/keymgr_*.sv` | 各种 sequence class 示例 |

**constraint 特点**：
- `rand int xxx; constraint xxx_c { xxx inside {[N:M]}; }`
- 多个 constraint 块共存
- `extends cip_base_test` 继承模式

---

### 2. sv-tests SV 标准库

**路径**: `~/my_dv_proj/sv-tests/tests/chapter-18/`

SystemVerilog 标准语法测试，覆盖所有 constraint 类型。

| 文件 | constraint 类型 |
|------|----------------|
| `18.5.6--implication_0.sv` | `->` implication |
| `18.5.6--implication_1.sv` | implication 变体 |
| `18.5.7--if-else-constraints_0.sv` | 简单 if/else |
| `18.5.7--if-else-constraints_3.sv` | **嵌套 if/else**（核心测试场景）|
| `18.5.7--if-else-constraints_4.sv` | if/else 变体 |
| `18.5.4--distribution_0.sv` | `dist {N:=W, M:=W}` 分布约束 |
| `18.5.4--distribution_1.sv` | dist 变体 |
| `18.5.5--uniqueness-constraints_0.sv` | `unique {a, b, c}` |
| `18.5.5--uniqueness-constraints_1.sv` | uniqueness 变体 |
| `18.5.10--variable-ordering_0.sv` | `solve A before B` |
| `18.5.10--variable-ordering_1.sv` | solve before 变体 |
| `18.5.14--soft-constraints_0.sv` | `soft constraint` |
| `18.5.14.1--soft-constraint-priorities_*.sv` | soft 优先级 |
| `18.5.2--constraint-inheritance_0.sv` | `class A extends B` 继承 |
| `18.5.2--constraint-inheritance_1.sv` | 继承变体 |

**文件命名规律**: `NN.N--constraint-type_N.sv`

---

### 3. 本项目已有测试

**路径**: `sim/tests/regression/test_constraint*.py`

| 文件 | 已覆盖内容 |
|------|-----------|
| `test_constraint.py` | rand 变量、constraint 块定义、class 实例化 |
| `test_constraint_derivative.py` | inside、implication、if/else、dist、solve_before、unique、foreach |

**注意**: 已有测试只验证"不崩溃"，需要按铁律17 加强为强断言。

