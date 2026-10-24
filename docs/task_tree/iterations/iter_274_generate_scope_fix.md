# Iteration 274: generate 局部信号作用域限定（方案 A）

**Metadata**:
- **Iteration #**: 274
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-24 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按 A 做"）
- **Outcome**: ✅ 成功（generate 内局部信号按块路径限定；全量 2308 passed）

## 🎯 目标

按 iter_273 的方案 A：把 generate 块内**局部声明**的信号命名从模块作用域
（`top.local_wire`）改成块作用域（`top.G[0].local_wire`），消除跨轮塌缩与假边。

## 🔧 改动（四处，形成闭环）

| # | 文件 | 改动 |
|---|---|---|
| 1 | `semantic/exprs_drivers.py::get_assignments` | 进入 `GenerateBlockArray` / `GenerateBlock` 时把 **块路径**（`G[0]` / `GEN_IF`）与 **块内声明名集合**并入 ctx（保留原有 genvar 下标替换） |
| 2 | `extractors/_common.py::get_signal` | 名字命中 `__scope_locals__` 时返回 `G[0].local_wire`；模块级信号（`din[i]`）不受影响 |
| 3 | `semantic/exprs_drivers.py` | 新增 `get_generate_locals_index()` → `{块路径: 块内声明名}`（elaboration 不变，缓存一次） |
| 4 | `connection_extractor.py` | 实例端口连到块内局部信号时，父侧 id 用**完整块路径**（原逻辑会剥掉 generate 段，导致塌缩） |

> 第 4 处是关键：DriverExtractor 侧修好后，连接侧仍把 `local_wire` 连成
> `top.local_wire → G[i].u_leaf.a`，所以两边必须用同一套作用域判定。

## 📊 修复前后（最小 fixture）

```
修复前: din[0..3] → top.local_wire → G[0..3].u_leaf.a     ← 4 轮合并成 1 个节点
修复后: din[0] → top.G[0].local_wire → G[0].u_leaf.a
        din[1] → top.G[1].local_wire → G[1].u_leaf.a      ← 各自独立
        ...
```

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `drivers G[1].u_leaf.a` | `{top.local_wire}`（背后 din[0..3]） | `{top.G[1].local_wire}` |
| `loads local_wire` | 4 个实例端口 | 各自的 1 个 |
| 节点 id | `top.local_wire` | `top.G[1].local_wire` |

## 🧪 测试

| 文件 | 变化 |
|---|---|
| `test_generate_local_scope.py` | xfail → **正常通过**（断言块路径与无跨轮边） |
| `test_genvar_for.py` | 断言改为 `top.a → top.g[i].w`，并加"不得塌缩成 top.w"守卫 |
| `test_semantic_adapter_api_surface.py` | 冻结表新增 `get_generate_locals_index`（API 面变更按纪律登记） |

## 📊 量化

| 指标 | 值 |
|---|---|
| 全量门禁 | 2306 → **2308 passed / 0 failed**（2 个 xfail 转正） |
| 跨轮假边 | 4 条 → **0** |
| 节点命名 | 4 个 `local_wire` 塌缩成 1 → **4 个独立块路径** |

## 💡 说明

- 方案 A 保留了 **`din[i] → G[i].local_wire → u_leaf.a`** 的完整连通性（方案 B 会丢这条链）。
- genvar 下标替换逻辑未动（`acc[i]` → `acc[2]`），只是**额外**给局部裸名加了块前缀，两者正交。
- 嵌套 generate 的路径会累加（父块路径 + 子块路径）。

## 🔗 相关

- 前序: [iter_273 generate 缺陷登记](iter_273_generate_scope_finding.md)
- 限制登记: [KNOWN_LIMITATIONS §3.5](../../KNOWN_LIMITATIONS.md)（已标"已修"）
