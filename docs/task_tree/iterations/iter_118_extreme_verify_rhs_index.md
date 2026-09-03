# Iteration 118: 极端场景验证 — generate RHS 位选 genvar-ctx 求值缺口修复

**Metadata**:
- **Iteration #**: 118
- **Task Tree Level**: L2 (方豆 "构造极端场景确认 signal graph 正确性")
- **Parent Task**: 验证任务 → 缺口修复
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (修复 1 缺口; 1 新 backlog)

## 🎯 本次目标

方豆要求用极端场景验证 signal graph 是否真的提取正确。构造 9 类极端场景,
每场景断言 无加倍段 / 无占位 / 驱动源集合相等 / fanin 可达性。

## 🔬 实际结果

### 场景 (9 类, 全部构造+断言)

S1 三层嵌套 gen / S2 四级嵌套 gen / S3 gen loop+if 混合 / S4 同名 STAGES 两级 /
S5 门级 (buf 多输出+链) / S6 多驱动 net / S7 组合自环+时序反馈 / S8 15 级深
fanin (generate assign 链) / S9 0 次迭代+false if。

### 发现 1 (已修): generate-for 内 assign 的 RHS 位选丢 genvar 索引

- **S8 复现**: `assign x[i] = x[i-1]` (15 级链) — RHS 全被解析成**整总线 'top.x'**
  → x[14] 的 fanin 回溯死端 (修复前 reachable=False)
- **根因** (semantic_adapter._extract_signals_from_expr ElementSelect/RangeSelect):
  selector 非 IntegerLiteral/Parameter 时 (generate entry 内 slang 不 fold,
  保持 NamedValue 'i' / BinaryOp 'i-1') → 直接 fallback 返回 base → 丢索引。
  LHS 走 get_signal (另一路径, 有 ctx) 正常 — 同一条 assign 左右不一致。
- **牵连**: case27 fixture (iter_035 起) 的 `assign acc[i+1] = acc[i] + prod`
  同病 — acc[i] RHS 落总线 acc, **从未被图级断言捕获** (语义 lookupName 测试
  不查 driver 边)。
- **修复**: 局部 `_fold_sel` (Literal/NamedValue-in-ctx/BinaryOp +-*/ /
  Conversion) 应用于 ElementSelect 非 Literal/Parameter 分支 + RangeSelect
  left/right 求值。踩坑 ×2: op 枚举名是 'Subtract' 非 '-'; IntegerLiteral
  .constant 是 ConstantValue (`.integer` 是对象) → `int(str(...))` 解。

### 发现 2 (记录 backlog, 未修): connection 侧 RangeSelect 连接命名恒 '?'

- S2 (四级嵌套, m2 端口 `.a(a[i*4+:4])`) 出 2 个占位 `...u_m2.a[?]`
- 根因方向: `_conn_expr_to_signal` 的 RangeSelect 分支取 `expr.selector`
  (semantic RangeSelect 无 .selector, left/right 在 expr 上) → idx='?' 恒;
  `_eval_select_index` 也不支持 Multiply (i*4)。已记录 backlog。

### 其余场景断言

S1/S3/S4/S5/S6/S7/S8/S9 全部 PASS (扣除 connection 端口 DRIVER 自环设计标记
与 reset 字面量等既有约定后断言成立); S8 修复后 x[i]←x[i-1] per-index,
fanin 14 跳可达 a。

### 验证

- 新 unit +3 (TestGenerateAssignRhsIndex: per-entry RHS 索引 / fanin 可达 /
  无总线 fallback 源), test_nested_generate_instance 7→10
- case27 回归确认 acc[1]←acc[0] per-index (行为改善, 无既有断言依赖总线)
- 回归处置: 旧断言锁定了 bus 级 RHS (bug 形态) 需随修复更新 —
  test_generate_for_chain_truth.test_edge_stage_chain 改 per-entry 断言
  (buf1[i+1]→buf2[i], buf2[i]→buf3[i]); prim_arbiter 3 个 golden
  (stats/risk/dataflow) 重生成 (DRIVER 90→118 = 新增 per-index 边, 合法改善)
- 全量回归结果见 commit

## 💡 关键发现 / 决策

1. **同一 assign 的 LHS/RHS 走两套解析, 一致性无保证** — LHS (get_signal) 有
   genvar ctx, RHS (signal visitor) 的 select 分支缺 ctx fold — 这是架构级
   分裂点 (visitor 分散在 semantic_adapter 大函数), 后续可考虑统一。
2. **generate RHS 位选从未被图级测试断言** — 极端场景 (深链) 是这类"潜伏缺口"
   的有效探针; S8 形态值得转 truth。
3. 断言必须排除既有设计标记: connection 端口 DRIVER 自环 (2026-07-08 约定) /
   reset 字面量 / assign 自反馈 (~comb→comb 合法)。

## 📌 状态

- ✅ S8/case27 RHS 索引缺口修复 (代码+unit +3); S2 connection RangeSelect 命名
  记录 backlog; 全量回归见 commit
