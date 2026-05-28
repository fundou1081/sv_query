# 纪律违反记录

> 审查日期: 2026-05-28
> 审查范围: 今日新增代码 (Covergroup/CallGraph/UVM TB)

---

## 🔴 P0: 铁律1 违反 — 使用 SyntaxTree 而非 Semantic AST

| 文件 | 行号 | 说明 |
|------|------|------|
| `src/trace/core/covergroup_extractor.py` | 47 | `pyslang.SyntaxTree.fromText(source)` |
| `src/trace/core/call_graph_builder.py` | 50 | `pyslang.SyntaxTree.fromText(source)` |
| `src/trace/core/visitors/constraint_visitor.py` | 551 | `pyslang.SyntaxTree.fromText(source)` |

**修复方案**: 改用 `SVCompiler` 获取 Semantic AST，或明确标注为何必须使用 SyntaxTree（如 covergroup/call graph 不需要语义信息，只需语法结构）。

**注意**: covergroup 和 call graph 提取的是语法结构（类定义、函数调用），不依赖语义信息（符号表、类型）。需要评估是否真的需要 Semantic AST，还是可以作为例外处理。

---

## 🔴 P0: 铁律10 违反 — 新数据模型缺少 confidence/errors

| 模型 | 文件 | 说明 |
|------|------|------|
| `CovergroupInfo` | `src/trace/core/graph/covergroup_models.py` | 无 confidence 字段 |
| `CallGraph` | `src/trace/core/graph/call_graph_models.py` | 无 confidence 字段 |
| `UVMTestbench` | `src/trace/core/graph/uvm_models.py` | 无 confidence 字段 |

**修复方案**: 给每个数据模型添加 `errors: List[str]` 字段，记录解析过程中的错误。

---

## 🟡 P2: 铁律3.1 — except 缺少注释

| 文件 | 行号 | 类型 | 说明 |
|------|------|------|------|
| `covergroup_extractor.py` | 75 | `except TypeError` | pyslang Token 不可迭代 |
| `covergroup_extractor.py` | 117 | `except Exception` | 递归遍历容错 |
| `call_graph_builder.py` | 130, 230, 282 | `except TypeError` | pyslang Token 不可迭代 |
| `uvm_testbench_extractor.py` | 112, 148, 172, 223, 360, 471 | `except TypeError` | pyslang Token 不可迭代 |

**修复方案**: 给每个 `except TypeError` 加注释说明原因: `# pyslang Token 对象不可迭代，跳过`

---

## 🟡 P2: 铁律7 — 负面测试不足

| 功能 | 现有测试 | 缺少的负面测试 |
|------|---------|--------------|
| CovergroupExtractor | 7 个 | 空输入、编译错误源码 |
| CallGraphBuilder | 11 个 | 无效入口、空函数体 |
| UVMTestbenchExtractor | 20 个 | 空文件、非 UVM 代码 |

---

## 状态

- [ ] P0: SyntaxTree → Semantic AST 评估
- [ ] P0: 数据模型加 confidence/errors
- [ ] P2: except 加注释
- [ ] P2: 补充负面测试
