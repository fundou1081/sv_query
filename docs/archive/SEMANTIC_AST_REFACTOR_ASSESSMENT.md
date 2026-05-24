# Semantic AST 重构方案 - 影响评估

版本：1.0
日期：2026-05-19
状态：草稿

---

## 一、方案概述

**目标**：用 Semantic AST（Compilation + getRoot()）替换当前的 SyntaxTree 方案，减少大量 try/except 异常处理。

**核心变化**：

```python
# 当前 (SyntaxTree)
tree = pyslang.SyntaxTree.fromText(code, fname)
root = tree.root  # SyntaxNode

# 新方案 (Semantic AST)
comp = pyslang.Compilation()
comp.addSyntaxTree(tree)
root = comp.getRoot()  # SemanticNode，带符号表
```

---

## 二、源代码更新范围

| 文件 | 行数 | 改动类型 | 优先级 |
|------|------|----------|--------|
| `unified_tracer.py` | 325 | API 参数变更: `trees: dict` → `sources: dict` | P0 |
| `core/pyslang_adapter.py` | ~2318 | **主体改动**: SyntaxTree → Semantic AST | P0 |
| `core/graph_builder.py` | 2520 | 遍历入口变更: `tree.root` → `comp.getRoot()` | P0 |
| `core/base.py` | ~2318 | ASTWalker/PyslangAdapter API 适配 | P1 |
| `core/module_instance_graph.py` | 995 | `tree.root` → `comp.getRoot()` | P1 |
| `core/graph/models.py` | 374 | **不需改动** (数据模型) | - |
| `core/bit_select_handler.py` | 362 | **不需改动** (基于 SignalGraph) | - |
| `core/class_graph_builder.py` | 785 | **不需改动** (基于 SignalGraph) | - |
| `core/query/*.py` | ~700 | **不需改动** (query 层) | - |
| `core/visitors/constraint_visitor.py` | 543 | **禁区 - 不可改动** | 🚫 |
| `core/visitors/base_visitor.py` | 161 | 视情况更新 | P2 |

### SyntaxTree 相关代码分布

```
src/trace/core/visitors/constraint_visitor.py:532:    tree = pyslang.SyntaxTree.fromText(source)
src/trace/core/pyslang_adapter.py:6:from pyslang import SyntaxTree, SyntaxKind
src/trace/core/pyslang_adapter.py:17:    def __init__(self, tree: SyntaxTree):
src/trace/core/pyslang_adapter.py:144:    return PyslangAdapter(pyslang.SyntaxTree.fromFile(f)).parse().trace_signal(sig)
src/trace/core/pyslang_adapter.py:148:    return PyslangAdapter(pyslang.SyntaxTree.fromText(c)).parse().trace_signal(sig)
src/trace/core/module_instance_graph.py:129:            root = tree.root
src/trace/core/module_instance_graph.py:150:            self._find_all_hierarchy_instantiations(tree.root, ...)
src/trace/core/graph_builder.py:790:                        for member in tree.root.members:
src/trace/core/base.py:27:            if not tree or not tree.root:
src/trace/core/base.py:1404:            find_inst(tree.root)
src/trace/core/base.py:1475:            walk(tree.root)
src/trace/unified_tracer.py:78:            trees: SyntaxTree 字典 {"filename": tree}
```

---

## 三、新方案优势对比

| 方面 | SyntaxTree（当前） | Semantic AST（方案） |
|------|-------------------|---------------------|
| 异常处理 | 大量 try/except | 语义节点属性更一致 |
| 符号解析 | 手写字符串匹配 | 自动符号表解析 |
| 路径构建 | 字符串拼接 | `getHierarchicalPath()` |
| 参数化位宽 | 字符串 `"W-1"` | 整数 `7` |
| 端口方向 | 字符串匹配 | `ArgumentDirection` 枚举 |
| 时钟域识别 | 手写遍历 | 语义 API 支持 |

---

## 四、项目纪律（必须遵守）

### 🚨 禁区 (不可修改)

```python
core/visitors/constraint_visitor.py  # 543行
理由: TB Class+Constraint 唯一实现，删除则功能丢失
```

### ✅ 核心资产 (保持稳定)

| 文件 | 说明 |
|------|------|
| `core/graph/models.py` | TraceNode/TraceEdge/EdgeKind 数据模型 |
| `unified_tracer.py` | 统一入口 API |
| `core/query/` | 查询层 ~700行 |

### ⚠️ 需迁移代码

| 文件 | 变更 |
|------|------|
| `core/pyslang_adapter.py` | SyntaxTree → Semantic AST |
| `core/graph_builder.py` | `tree.root` → `comp.getRoot()` |
| `core/base.py` | ASTWalker API 适配 |
| `core/module_instance_graph.py` | 遍历入口变更 |

---

## 五、文档更新范围

| 文档 | 改动程度 | 说明 |
|------|----------|------|
| `README.md` | ⚠️ 需更新 | 架构图、三层分离 |
| `DEVELOPMENT.md` | ⚠️ 需更新 | 开发指南、API 示例 |
| `EXAMPLES.md` | ⚠️ 需更新 | 代码示例 |
| `PROJECT_PLAN.md` | ⚠️ 需更新 | 工期估算 |
| `docs/architecture/architecture.md` | 🔴 重大更新 | 三层分离架构 |
| `docs/REFACTOR_GUIDE_v2.md` | 🔴 重大更新 | 新方案替代旧方案 |
| `docs/REFACTOR_GUIDE.md` | 🗑️ 废弃 | 可删除或保留旧版 |
| `docs/ISSUES_SUMMARY.md` | 📝 补充 | 添加新方案说明 |

---

## 六、测试文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `sim/test_golden_cases.py` | ⚠️ 可能需更新 | 如果 API 签名变化 |
| `sim/test_gold_comprehensive.py` | ⚠️ 可能需更新 | 如果返回值结构变化 |
| 669 gold standard 测试 | ✅ 应该稳定 | 行为测试，不测 API |

---

## 七、实施计划

| 阶段 | 任务 | 工作量 | 完成标志 |
|------|------|--------|----------|
| **Phase 0** | 建立 `compiler.py` 编译入口 | 0.5 天 | Compilation API 验证 |
| **Phase 1** | `unified_tracer.py` API 适配 | 0.5 天 | `sources` 参数替代 `trees` |
| **Phase 2** | `PyslangAdapter` → Semantic AST | 2 天 | AST 遍历正常 |
| **Phase 3** | `GraphBuilder` 遍历入口重构 | 2 天 | Graph 构建正确 |
| **Phase 4** | `module_instance_graph.py` 适配 | 0.5 天 | 模块实例识别正确 |
| **Phase 5** | 文档更新 | 0.5 天 | 文档与代码一致 |
| **Phase 6** | 回归测试 (669 tests) | 1 天 | 所有测试通过 |
| **总计** | | **7 天** | |

### 依赖关系

```
Phase 0 (compiler.py)
    ↓
Phase 1 (unified_tracer API)
    ↓
Phase 2 (PyslangAdapter) ←→ Phase 3 (GraphBuilder)  可并行
    ↓
Phase 4 (module_instance_graph)
    ↓
Phase 5 (文档) + Phase 6 (测试)
```

---

## 八、关键风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| pyslang Semantic AST API 不稳定 | 高 | 先用 `sv_query_experiments/` 验证 API |
| constraint_visitor.py 不兼容 | 中 | 确认它自己创建 SyntaxTree，与新方案独立 |
| 大量 try/except 移除暴露隐藏问题 | 中 | 保留必要的安全检查，逐步移除 |
| 669 测试失败 | 低 | Gold standard 可更新，行为优先 |

### 验证计划

1. **Phase 0 完成后**：验证 `comp.getRoot()` 返回的节点结构
2. **Phase 2 完成后**：运行 `sim/test_golden.py` 快速冒烟
3. **Phase 6**：完整回归测试

---

## 九、与 slang-netlist 方案的关系

**正交关系**：

| 层次 | 数据来源 | 新方案作用 |
|------|----------|------------|
| RTL 驱动关系 | slang-netlist (可选) | 替代 `DriverExtractor` |
| **TB 时序结构** | **Semantic AST (本次方案)** | **替代 SyntaxTree 遍历** |
| TB Class+Constraint | constraint_visitor.py | 不变 |

**不是替换，而是互补**：
- Semantic AST 优化内部 AST 遍历
- slang-netlist 可作为可选的 RTL 分析后端

---

## 十、迁移后收益

| 指标 | 迁移前 | 迁移后 |
|------|--------|--------|
| 异常处理代码量 | ~500 行 | ~200 行 |
| 参数化位宽 | 字符串 `"W-1"` | 整数 `7` |
| 端口方向识别 | 字符串匹配 | 枚举比较 |
| 符号解析能力 | 弱 | 强 (符号表) |
| 代码可维护性 | 中 | 高 |

---

## 附录 A: 相关文件路径

```
sv_query/
├── src/trace/
│   ├── unified_tracer.py          # API 入口 (P0)
│   └── core/
│       ├── pyslang_adapter.py     # AST 适配器 (P0)
│       ├── graph_builder.py       # 图构建器 (P0)
│       ├── base.py                 # 基类 (P1)
│       ├── module_instance_graph.py # 模块实例 (P1)
│       ├── graph/models.py         # 数据模型 ✅
│       ├── bit_select_handler.py   # 位选处理 ✅
│       ├── class_graph_builder.py  # 类图构建 ✅
│       ├── query/                   # 查询层 ✅
│       └── visitors/
│           ├── constraint_visitor.py  # 🚫 禁区
│           └── base_visitor.py         # (P2)
├── docs/
│   ├── REFACTOR_GUIDE_v2.md       # 🔴 需重大更新
│   ├── architecture/
│   │   └── architecture.md         # 🔴 需重大更新
│   └── ...
├── sim/
│   ├── test_golden.py             # 冒烟测试
│   ├── test_golden_cases.py        # 回归测试
│   └── test_gold_comprehensive.py  # 综合测试
└── 669 gold standard 测试
```

---

## 附录 B: 新增文件

```python
# src/trace/core/compiler.py (新增)
"""编译入口 - 建立 Semantic AST"""

import sys
sys.path.insert(0, '/path/to/slang/build/bindings')
import pyslang

def compile_sources(sources: dict) -> tuple:
    """
    sources: {filename: sv_code_string}
    返回: (Compilation, root)
    """
    comp = pyslang.Compilation()
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
    
    root = comp.getRoot()
    return comp, root
```