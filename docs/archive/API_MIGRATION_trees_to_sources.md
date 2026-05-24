# API 迁移记录：trees={} → sources={}

## 迁移日期
2026-05-20

## 背景
sv_query 从旧 API（使用 SyntaxTree）迁移到新 API（使用源文本 + Semantic AST）。

## 旧 API（已废弃）
```python
import pyslang
from trace.unified_tracer import UnifiedTracer

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test': tree})
```

## 新 API（当前）
```python
from trace.unified_tracer import UnifiedTracer

tracer = UnifiedTracer(sources={'test.sv': source})
```

## 替换规则

| 旧写法 | 新写法 |
|--------|--------|
| `UnifiedTracer(trees={'name': tree})` | `UnifiedTracer(sources={'name.sv': source})` |
| `tree = pyslang.SyntaxTree.fromText(source)` | (删除，source 直接使用) |
| `tree.toString()` | `source` (直接使用源码字符串) |
| `PyslangAdapter` (base.py) | `SemanticAdapter` (core/semantic_adapter.py) |

## 已迁移文件
- sim/tests/integration/ (所有测试文件)
- sim/tests/regression/ (所有测试文件)
- sim/tests/unit/test_comment_handling.py
- sim/tests/unit/test_parameter_extraction.py
- sim/tests/unit/test_pyslang_adapter.py
- sim/tests/unit/test_instance_name_extraction.py
- sim/tests/unit/test_expression_evaluation.py
- sim/tests/unit/test_procedural_blocks.py
- sim/tests/unit/test_connection_tracing.py
- sim/tests/unit/test_non_ansi_port.py
- sim/tests/unit/test_param_expression_resolution.py
- sim/tests/unit/test_ast_expression_evaluator.py

## 关键差异

### 1. UnifiedTracer 初始化
```python
# 旧：使用 SyntaxTree
tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'test': tree})

# 新：使用源文本
tracer = UnifiedTracer(sources={'test.sv': source})
```

### 2. Adapter 选择
```python
# 旧：PyslangAdapter (base.py) - 基于 SyntaxTree
adapter = PyslangAdapter(parser)

# 新：SemanticAdapter (core/semantic_adapter.py) - 基于 Semantic AST
from trace.core.semantic_adapter import SemanticAdapter
adapter = SemanticAdapter(comp.getRoot())
```

### 3. 核心变化
- **旧 API**: 直接使用 pyslang 的 SyntaxTree，需要手动管理编译
- **新 API**: UnifiedTracer 内部自动编译源文本为 Semantic AST

## 测试状态（迁移后）
- 单元测试：部分通过（109 passed，部分因基础设施调整失败）
- 回归测试：进行中（392 passed, 445 failed）

## 注意事项
1. `pyslang.SyntaxTree` 没有 `toString()` 方法 - 源文本直接使用
2. 测试中的 `FakeParser` 类需要重写以适配新 API
3. 部分测试使用 `PyslangAdapter` 需要迁移到 `SemanticAdapter`