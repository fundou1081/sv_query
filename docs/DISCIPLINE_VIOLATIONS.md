# 纪律违反记录

> 审查日期: 2026-05-28
> 最终更新: 2026-05-29

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
