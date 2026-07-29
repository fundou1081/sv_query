# 纪律违反记录

> 审查日期: 2026-05-28
> 最终更新: 2026-07-29 (V6.8)
> 铁律定义: [CODE_DISCIPLINE.md](CODE_DISCIPLINE.md)

---

## 铁律0 违反: StatementCollectorVisitor 用 Syntax AST 提取 case item 条件 (FIXED V6.8)

**时间**: 2026-07-29 发现并修复

**违反描述**: `StatementCollectorVisitor.visit_case_statement()` 使用 Syntax `StandardCaseItemSyntax.expressions`（而非 Semantic `ItemGroup.expressions`）提取 case 条件表达式。导致 condition 字符串被注释污染。

**影响范围**: 所有包含 case 语句的 RTL 设计中，condition 标签包含源码注释文本

**修复**: 改用 Semantic `ItemGroup`（通过 `ProceduralBlockSymbol.body.visit()` 遍历），用 `ConversionExpression.operand.value` 拿干净数值

**教训**: [CODE_DISCIPLINE.md#铁律0](CODE_DISCIPLINE.md) 已记录为项目铁律

---

## 铁律1: SyntaxTree → Semantic AST 修复状态

| 文件 | 方式 | 说明 |
|------|------|------|
| `covergroup_extractor.py` | ✅ Semantic AST | 使用 CovergroupType/CoverpointSymbol/CoverageBin |
| `call_graph_builder.py` | ✅ Semantic AST | 使用 Subroutine 节点 |
| `uvm_testbench_extractor.py` | ⚠️ SyntaxTree | UVM 宏展开依赖 uvm_pkg，Semantic AST 无法解析 |
| `constraint_visitor.py` | ✅ 合规 | 仅做语法解析，不需要语义信息 |
| `compiler.py` | ✅ 新增 UVM include 路径 | 自动检测 UVM 源码，支持 import uvm_pkg 编译 |

### 技术说明

- pyslang SVCompiler 可以编译 `import uvm_pkg::*` + UVM 宏的代码（需加入 uvm_pkg.sv 源码）
- pyslang 存在 Unicode 内存损坏 bug：混合编译 UVM + 用户代码时，部分类的 `name` 属性返回乱码
- 通过 `_fix_unicode_class_names()` 用 `sourceRange.offset` 从源码提取类名来规避
- UVM 提取器只需语法结构，使用 SyntaxTree 是合理的工程选择

---

## 铁律10: 数据模型 confidence/errors

| 模型 | 状态 |
|------|------|
| `CovergroupInfo` | ⚠️ 待补充 errors 字段 |
| `CallGraph` | ✅ 有 errors 字段 |
| `UVMTestbench` | ⚠️ 待补充 errors 字段 |

---

## 铁律3.1: except 注释

| 文件 | 状态 |
|------|------|
| 各提取器 `except TypeError` | ⚠️ 待补充注释 (pyslang Token 不可迭代) |

---

## 状态

- [x] P0: covergroup/call_graph SyntaxTree → Semantic AST
- [x] P0: compiler 支持 UVM include 路径
- [x] P0: Unicode bug 修复 (_fix_unicode_class_names)
- [ ] P0: 数据模型加 errors (CovergroupInfo, UVMTestbench)
- [ ] P2: except 加注释

---

## 死代码清理

| 文件 | 操作 | 说明 |
|------|------|------|
| `pyslang_adapter.py` (144-148行) | ✅ 已删除 | `trace_signal_from_file/code` 无调用方，违反铁律1 |
| `docs/archive/pyslang_adapter_legacy.py` | ✅ 已归档 | 保留原始代码供参考 |
