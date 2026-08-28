# Iteration 050: #6 expression tree 提取独立成 builder

**Metadata**:
- **Iteration #**: 050
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #6
- **Created**: 2026-08-28 23:40 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, expr_trees/const_map/func_info byte-identical

---

## 🎯 本次目标

用户指令: **"先 c"** → 按方案 C (先设计文档) 推进 #6:
expression tree 提取独立成 builder。

设计文档: [DESIGN_expr_tree_builder.md](DESIGN_expr_tree_builder.md)

---

## 🔬 盘点

唯一写入点: `driver_extractor._store_expr_tree` (L206-274), 依赖:
- `_tree_complexity` (L44, 模块级)
- `_collect_from_tree` (L55, 模块级)
- `_substitute_genvar_in_tree` (L276, staticmethod)

7 处调用点全是通过 Helpers 注入 (`store_expr_tree=self._store_expr_tree`):
- assign_extractor (4) / always_extractor (1) / net_decl_extractor (2)

---

## 🛠️ 实施

### 新建 `extractors/expr_tree_builder.py`

纯函数风格 (与 _common 一致):
- `build_expr_tree(lhs_name, rhs_expr, module_name, result, genvar_ctx)` — 主入口
- `tree_complexity(d)` / `collect_from_tree(...)` — 纯模块级函数
- `substitute_genvar_in_tree(tree_dict, ctx)` — **1:1 复刻原实现**
  (SignalRef/BitSelect + 'base[idx]' → 'base[N]', 非简化 regex)

### driver_extractor 改动

- `_store_expr_tree` → 薄壳 (转发到 build_expr_tree, 调用方零改动)
- 删 `_tree_complexity` / `_collect_from_tree` / `_substitute_genvar_in_tree`
- 1431 → 1302 行 (净减 129)

---

## 🔴 实施失误 (诚实标注)

**两次删除错位**:

1. 第一次: 逐段 del 时第二个 del 用原索引操作已缩短的列表 → 索引错位,
   **误删 `_expr_is_compile_time`** → `AttributeError` → 7 测试失败
2. 第二次: `del out[start2:end2]` 逻辑对但 `out` 已被前一个 del 改过 →
   anchor 找不到

**修复**: 一次性构造新列表 (不逐段删):
```python
new_lines = lines[:seg_start] + lines[i_class:i_store] + [SHELL] + lines[i_set:]
```

**教训**: 多段删除同一列表, 必须一次性构造或从大到小删且重算索引。
删除后**立即验证关键方法存在** (脚本断言), 不依赖测试才发现。

---

## 📈 验证

| 项 | 结果 |
|---|---|
| `integration` | 13 failed (基线) = **0 回归** |
| `cli` | 20 failed (先期) = **0 回归** |
| `unit` | 4 failed (沙箱) = **0 回归** |
| `test_case27_1to1_truth` | **4 passed** ✅ |
| **expr_trees/const_map/func_info** | **byte-identical** (probe_tree A/B) |
| ruff | expr_tree_builder All checks passed |

### 🔑 核心验证

探针覆盖 ternary + function call + const:
```
assign o = sel ? (a + 8'd1) : addf(a, b);
```
产出:
- expr_trees: {'top.o': ...}
- const_map: {"o": ["8'd1"]}
- func_info: {"addf": [7, 0]}

与基线 **byte-identical** — #6 的行为完全一致。

---

## 📌 后续

- #7: 迁 pyslang 11.0 native API (最后一项)
- 可选: func_info 补宽度逻辑 (driver_extractor 1359-1371) 是否随 builder 搬
  (当前留在 extract 后处理, 依赖 adapter, 边界清晰)
