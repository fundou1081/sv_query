# Iteration 119: connection RangeSelect 连接命名修复 — +:/-: 切片按 [hi:lo] 求值

**Metadata**:
- **Iteration #**: 119
- **Task Tree Level**: L2 (极端场景验证 backlog S2)
- **Parent Task**: [tasks/L2_conn_rangeselect_naming.md](../tasks/L2_conn_rangeselect_naming.md)
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

修 iter_118 S2 极端场景遗留: connection 侧 RangeSelect 连接命名恒 '?' —
四级嵌套 `.a(a[i*4+:4])` / `.y(y[j*2+:2])` 出占位 `u_m2.a[?]`/`y[?]`。

## 📊 当前状态 / 预期结果

- S2: 2 个占位 (G1[1] 的 u_m2.a[?]/y[?]); 修复前 semantic RangeSelect 分支
  只取 expr.selector (None) → idx '?'
- 预期: 切片连接按 [hi:lo] (msb:lsb) 命名, 0 占位

## 🔬 实际结果

### 探查 (pyslang 11)

- semantic RangeSelectExpression: **left/right 在 expr 上** (无 .selector),
  **selectionKind** 区分 +: (RangeSelectionKind.IndexedUp) / -: (IndexedDown) /
  普通 (Simple); `[base+:width]` 语义 = 位 [base+width-1 : base]
  (right 是宽度非 lsb — 实测 .y(y[j*2+:2]) j=0 → left 常量 0, right=2=width)
- S1 (同写法, top 级) 无占位是 slang 对部分 entry 常量折叠的偶然差异 —
  非两条路径

### 修复 (semantic_adapter._conn_expr_to_signal)

RangeSelect 分支独立于 ElementSelect:
- 逐界 `_eval_select_index` (已支持 Literal/Conversion/NamedValue(gidx)/
  BinaryOp ±* — iter_109 就绪, 无需扩)
- IndexedUp: hi=base+width-1, lo=base; IndexedDown: hi=base, lo=base-width+1;
  Simple: hi=max, lo=min → 命名 `sig[hi:lo]`; 求不出保持 `sig[?]` (不静默)

### 验证

- S2 复现: 占位 2→**0**; 正确切片名 `u_m2.y[1:0]`/`y[3:2]` 等 (G1[1] 非折叠
  entry) 在位
- 新 unit +3 (TestPartSelectConnNaming: 无占位 / 切片名 / leaf→切片 CONNECTION)
  test_nested_generate_instance 10→13
- 全量回归结果见 commit

### 观察 (非本次范围)

G1[1].u_m2.G2[0].u_leaf 的连接在图里归到 G2[1] 一侧 / G2[0] 缺失 — 疑似 slang
合并相同 generate entry (identical bodies) 的实例枚举边角, 与本次 '?' 修复
无关 — 已注释记录待后续探查。

## 💡 关键发现 / 决策

1. **semantic RangeSelect 的坑**: 无 .selector (ElementSelect 有), left/right
   在 expr; 且 `[base+:width]` 的 right 是**宽度** — 命名必须用 selectionKind
   换算, 不能当 msb/lsb 直接用。
2. `_eval_select_index` (iter_109) 已具备 ±*/Literal/Conversion/gidx —
   本次只是把它接到 RangeSelect 两端, 无新求值逻辑。

## 📌 状态

- ✅ 代码 + unit +3; 全量回归见 commit
