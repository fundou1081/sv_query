# #6 设计: expression tree 提取独立成 builder

> **状态**: 设计文档 (方案 C — 先设计, 后改代码)
> **创建**: 2026-08-28 23:20
> **关联**: [ARCHITECTURE_TODOLIST #6](ARCHITECTURE_TODOLIST.md)

---

## 🎯 目标

`driver_extractor` 只负责"原始 driver 边"——表达式树 (expr_trees) / 常量 (const_map) /
函数信息 (func_info) 是**独立关注点**, 抽成独立 builder。

---

## 🔬 现状盘点

### 字段定义 (extractor_models.py)

```
ExtractorResult:
  expr_trees: dict[str, dict]   # {dst_key → tree_dict} (多分支 max 合并)
  const_map:  dict[str, list]   # {dst_short → [const_str,...]}
  func_info:  dict[str, tuple]  # {func_name → (msb,lsb)|None}
```

### 唯一写入点: driver_extractor._store_expr_tree (207-274 行)

```
_store_expr_tree(lhs_name, rhs_expr, module_name, result, genvar_ctx)
  ├─ unwrap Conversion wrappers (最多 10 层)
  ├─ ExpressionTree._parse_expr(tokens) → root      (来自 .graph.viz.expression_tree)
  ├─ ExpressionTree._to_dict(root) → tree_dict
  ├─ _substitute_genvar_in_tree(tree_dict, genvar_ctx)   (Plan G2)
  ├─ 多分支 max 合并 (保留最复杂) → result.expr_trees[tree_key]
  └─ _collect_from_tree(tree_dict, dst_short, const_map, func_info)
       (递归提取 Const → const_map, Call → func_info)
```

依赖 (都是 driver_extractor 内):
- `_tree_complexity(d)` — 模块级函数 (L44)
- `_collect_from_tree(...)` — 模块级函数 (L55)
- `_substitute_genvar_in_tree(tree_dict, ctx)` — staticmethod (L276)

### 调用点 (7 处, 全是通过 Helpers 注入)

```
assign_extractor  : h.store_expr_tree  (4 处)
always_extractor  : h.store_expr_tree  (1 处)
net_decl_extractor: store_expr_tree    (2 处, 直接参数)
driver_extractor  : self._store_expr_tree (被上面注入)
```

### 消费方 (读 expr_trees/const_map/func_info)

- `graph_builder.py:742-746`: 把 result 的三个 dict merge 到 graph._expr_trees 等
- `driver_extractor.py:1359-1371`: func_info 补宽度 (从 function declaration)
- viz 层 (viz_data_builder / elk_bridge / checker / expression_tree)

---

## 📐 设计: ExpressionTreeBuilder

### 新模块: `src/trace/core/extractors/expr_tree_builder.py`

```python
@dataclass
class ExprTreeHelpers:
    """注入包 (沿用 AssignHelpers/AlwaysHelpers 模式)."""
    substitute_genvar: Callable  # genvar substitute (当前是 driver_extractor staticmethod)

class ExpressionTreeBuilder:
    """expr_trees / const_map / func_info 构建器.

    关注点: 从 rhs_expr 构建表达式树 + 提取常量/函数信息.
    与 driver_extractor 解耦: 它只调 build(), 不再关心 tree 内部结构.
    """

    def __init__(self, helpers: ExprTreeHelpers | None = None):
        self._helpers = helpers or ExprTreeHelpers(substitute_genvar=None)

    def build(self, lhs_name, rhs_expr, module_name, result, genvar_ctx=None):
        """原 _store_expr_tree 逻辑, 移入这里."""
        ...

    @staticmethod
    def _tree_complexity(d): ...          # 从 driver_extractor L44 搬

    @staticmethod
    def _collect_from_tree(tree_dict, dst_short, const_map, func_info): ...
                                            # 从 driver_extractor L55 搬
```

### driver_extractor 改动

```python
# _store_expr_tree 变为薄壳:
def _store_expr_tree(self, lhs_name, rhs_expr, module_name, result, genvar_ctx=None):
    from .extractors.expr_tree_builder import ExpressionTreeBuilder
    ExpressionTreeBuilder().build(lhs_name, rhs_expr, module_name, result, genvar_ctx)
```

### genvar substitute 处理

`_substitute_genvar_in_tree` 是 staticmethod (无 self 依赖), 可直接搬入 builder
(作为 staticmethod 或模块函数)。driver_extractor 保留薄壳转发 (若有其他调用)。

---

## ⚠️ 关键决策点

1. **ExpressionTreeBuilder 实例 vs 纯函数** — 无状态, 建议纯函数/模块级函数
   (与 _common.py 的共享纯函数风格一致), 不引入类。
2. **_store_expr_tree 薄壳 vs 改 7 处调用点** — 保留薄壳 (调用方零改动,
   与 Step 3b/4/5/6/7 的模式一致)。
3. **substitute_genvar 归属** — 搬入 builder, driver_extractor 保留 staticmethod
   转发 (防外部引用)。
4. **func_info 补宽度逻辑** (driver_extractor 1359-1371) — 在 extract() 末尾,
   依赖 adapter.get_function_width, 属于"构建后处理", 可留原处或随 builder 搬。

---

## 📋 验证计划

1. 行为等价: 全套回归 + probe (assign/flatten/always/function) byte-identical
2. expr_trees/const_map/func_info 内容与搬移前一致 (探针比较)
3. ruff: 新模块 All checks passed

---

## 📌 待确认

- [ ] 方案: 纯函数 vs 类 (推荐纯函数, 与 _common 一致)
- [ ] _store_expr_tree 保留薄壳 (推荐)
- [ ] func_info 补宽度是否随 builder 搬 (推荐留原处, 它是 extract 后处理)
