# Iteration 042: #1 Step 7 — 拆 function_extractor (7 方法 / 648 行)

**Metadata**:
- **Iteration #**: 042
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #1 (拆 driver_extractor)
- **Created**: 2026-08-28 19:55 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, function/task 探针 byte-identical

---

## 🎯 本次目标

用户指令: **"继续吧"** → Step 7 拆 function_extractor（#1 剩余步骤的最后一次拆分）。

从 `driver_extractor.py` 拆出 function/task 相关 7 个方法 (648 行) →
`extractors/function_extractor.py`:

| 方法 | 行数 | 职责 |
|---|---|---|
| `_find_invocations` | 32 | 递归找 Invocation/Call |
| `_get_constructor_call` | 11 | 构造器调用名 |
| `_find_func_assignment_rhs` | 57 | 函数赋值 RHS |
| `_handle_invocation` | 26 | 入口 |
| `_parse_invocation_call` | 122 | 解析 invocation |
| `_find_task_definition` | 42 | 找 task 定义 |
| `_create_invocation_edges` | **358** | 主展开 |
| `_get_all_signals` | 9 | 信号提取 (仅 invocation 用) |

---

## 🔑 调查发现

### 3 个区域，非连续

- `_find_invocations` (L864) 孤立，自递归
- 主区域 6 方法 (L1677-文件尾) 连续

### 共享 helper 边界

| 依赖 | 归属 | 处理 |
|---|---|---|
| `_get_signal` | 全文件共享 | 注入 |
| `_subroutine_expander` | 实例 (L116 构造) | 注入 |
| `_get_all_signals` | **仅 invocation 用** | 随模块搬走 |

### 关键: 两个方法搬走后需薄壳

`_find_invocations` / `_handle_invocation` / `_get_all_signals` / `_get_constructor_call`
被 **AssignHelpers / AlwaysHelpers 注入点**引用（`handle_invocation=self._handle_invocation`
等），搬走后 driver_extractor 需保留薄壳转发。

---

## 🔬 实施中的问题 (诚实标注)

### 失误 1: `_parse_bit_range` 的 `@staticmethod` 被吞 (第 2 次!)

删 `_find_invocations` (L864-895) 时，下一个方法 `_parse_bit_range` 的
`@staticmethod` (L896 前) 被删除区间吞掉 → 31 个 integration 测试失败
(`TypeError: takes 1 positional argument but 2 were given`)。

**这是 Step 6 犯过的同一错误**。修复后做了一次**系统性对比**:
用 `git show` 导出基线 staticmethod 清单，逐一对当前文件比对，
确认没有其他丢失 (`_is_valid_signal_name` 搬去 always_extractor 是模块级，正常)。

### 失误 2: `_get_all_signals` 漏搬

`_create_invocation_edges` 里用到它，但最初没把它加入搬运集合，导致
`AttributeError: 'DriverExtractor' object has no attribute '_get_all_signals'`。
修复: 补搬 + 加薄壳。

### 失误 3: 双逗号

`_handle_invocation` 里 `task_def,, h=h` (原参数已有尾逗号)，修复为单逗号。

### 教训

1. **`@staticmethod` 吞并已犯 2 次** — 下次必须用基线对比法系统检查
2. 删除区间 + 薄壳化，涉及**注入点引用**的方法要格外小心 (assign/always 都引用)

---

## 📈 验证 (git worktree A/B, 基线 = `04eec7b`)

### 回归: 全套 0 新增失败

| 测试套 | 基线 `04eec7b` | Step 7 后 | 结论 |
|---|---|---|---|
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 (修 staticmethod 前 44) |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |
| `unit` | 4 failed (沙箱) | **4 failed** | ✅ 0 回归 |
| `test_case27_1to1_truth` | — | **4 passed** | ✅ 全绿 |

### 🔑 行为等价: function/task 探针

覆盖 function call + binary+invocation 的 fixture（4 边/5 节点）:
```
assign o1 = addf(a, b);
assign o2 = a & addf(b, a);
```
A/B diff **完全 byte-identical** — 包括 `addf(p)` / `addf(q)` 参数边。

### lint

- `function_extractor.py`: **All checks passed!**
- `driver_extractor.py`: 删 `CallSiteInfo` 未用 import + ruff --fix 排序；
  剩 1 个先期 `side_kind` F841

---

## 📊 进度

| 指标 | 值 |
|---|---|
| `driver_extractor.py` | 2292 → **1685 行** (净减 607) |
| 累计拆出 (#1 全程) | 4101 → 1685, **净减 2416 行** |
| #1 步骤 | **8/9 完成** (只剩 Step 8 删主体 + Step 9 回归) |

---

## 📌 下一步

- **Step 8: 删 driver_extractor.py 主体** (0.5 天) — 剩余的 1685 行是什么?
  需要盘点: 应该只剩薄壳 + 共享 helper + extract() 主循环
- Step 9: 全套最终回归 (0.5 天)
