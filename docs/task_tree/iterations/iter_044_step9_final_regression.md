# Iteration 044: #1 Step 9 — 全套最终回归, #1 收官

**Metadata**:
- **Iteration #**: 044
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #1 (拆 driver_extractor) — **收官**
- **Created**: 2026-08-28 20:45 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — #1 全部 9 步完成, 0 回归

---

## 🎯 本次目标

用户指令: **"继续"** → Step 9 全套最终回归, **收官 #1**。

验证整个拆分链条 (Step 1+2 → 8) 无累积回归。

---

## 📈 全套回归结果

| 测试套 | 基线 (Step 7 末) | Step 8+9 后 | 结论 |
|---|---|---|---|
| `test_case27_1to1_truth` | 4 passed | **4 passed** | ✅ 全绿 |
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 |
| `unit` | 4 failed (沙箱) | **4 failed** | ✅ 0 回归 |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |

### 🔑 行为等价: 6 探针全部 byte-identical

| 探针 | 覆盖 | 结果 |
|---|---|---|
| `probe_assign` | assign 4 分支 (concat/ternary/call/binary+invocation) | ✅ |
| `probe_flatten` | if/else + case + for loop + timing | ✅ |
| `probe_always` | always_ff+async reset / comb case / ternary | ✅ |
| `probe_func` | function/task 调用展开 | ✅ |
| `probe3` | net_decl (wire X = expr) | ✅ |
| `probe_gen` | generate-for 展开 wire decl | ✅ |

**6 条代码路径, 横跨所有拆出的模块, 输出与拆分前完全一致。**

---

## 📊 #1 最终成绩

| 指标 | 值 |
|---|---|
| 起始 | driver_extractor.py **4101 行** |
| 结束 | driver_extractor.py **1431 行** |
| 净拆出 | **2670 行** (65%) 到 7 个独立模块 |
| commit 数 | 9 个 (含 #2 相关) |

### 最终结构

```
src/trace/core/driver_extractor.py    (1431 行 — 薄壳 + 共享 helper + extract 主循环)
src/trace/core/extractors/
├── _common.py               (共享纯函数: fold_constant / get_signal / iter_bit_selects)
├── alias_extractor.py       (Step 1+2: alias 边)
├── wire_init_extractor.py   (Step 3: 变量/网表声明节点)
├── net_decl_extractor.py    (Step 3b: wire X = expr 边)
├── assign_extractor.py      (Step 4: assign 4-way dispatch + AssignHelpers)
├── statement_flattener.py   (Step 5: semantic AST 展平)
├── always_extractor.py      (Step 6: always 块 + AlwaysHelpers)
└── function_extractor.py    (Step 7: function/task + FunctionHelpers)
```

### 每步验证方式

每步都做了:
1. **全套测试回归** (integration/cli/unit/truth) — 0 新增失败
2. **行为探针 A/B** (worktree 基线 vs 当前) — byte-identical
3. **ruff lint** — 新模块 All checks passed

---

## 💡 关键发现汇总 (9 个迭代的经验沉淀)

1. **共享 helper 不该跟着业务逻辑搬** — 判断标准是调用点分布
   (Step 3b/4/6 多次验证)
2. **注入参数多了要打包** — 2-6 个用 Callable, 13 个用 dataclass (Step 4)
3. **搬代码和重构代码分开 commit** — 出回归时能归因 (Step 4b)
4. **行号区间删除要保护** — @staticmethod 被吞 2 次, extract() 被删 1 次
   (Step 6/7/8), 教训: 加"区间内不得含目标方法"断言 + 基线对比法
5. **行为等价要探针验证** — 测试全绿 ≠ 行为一致, byte-identical 探针更严格
6. **死代码判断要全仓搜** — driver_extractor 内 0 调用 ≠ 死代码 (注入引用)

---

## ✅ #1 完成

**ARCHITECTURE_TODOLIST #1: 拆 driver_extractor (4101 行 → 10 个文件) — DONE**

项目总进度更新: **#1 ✅ done + #2 ✅ done + #3 ✅ done = 3/7 项完成**,
剩余 #4~#7 + #8 待决策。
