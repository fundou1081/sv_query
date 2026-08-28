# Iteration 045: #8 修 generate-for 动态位选 (BIT_SELECT + DRIVER 边)

**Metadata**:
- **Iteration #**: 045
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #8 (新发现: generate-for 动态位选)
- **Created**: 2026-08-28 21:30 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, 新测试有效, 6 探针 byte-identical

---

## 🎯 本次目标

用户指令: **"先做 #8"** → 修 generate-for 动态位选。

G2 计划 (06:33) 实测的 bug:
> generate-for 内动态位选 (`acc[i]`) 不产生 BIT_SELECT 边, 节点 ID 是
> 'top.gen_accum[0].acc[0]' 形式, regex 反推看不到。

---

## 🔬 调查: bug 的实际构成

### 发现 1: BIT_SELECT 边已被 #2 顺带修复

用 G2 的 Fixture 5 复现, **当前 HEAD 已有 5 条 BIT_SELECT 边** (vs G2 时代 0 条)。
原因: #2 引入的 `_PyslangSelectWalker` 用 `visit()` 遍历 AST, 能看到
generate 展开后的 ElementSelect 节点, 而旧 regex 反推看不到。

**验证**: `49b475c` (#2 之前) 是 0 条, 当前是 5 条。

### 发现 2: DRIVER 边仍缺失 (真正的剩余 bug)

`acc[i] <= data_in` 没有 `data_in -> acc[i]` 的 DRIVER 边 — 因为:

**根因链**:
1. `get_always_blocks(module)` 只遍历 `module.body` 顶层,
   generate-for 内的 always 块**不被枚举** (返回 0)
2. `always_extractor._create_always_edges` 主循环只遍历 `get_always_blocks`
   → generate 内所有 procedural 赋值丢失
3. 即使遍历到, `_parse_assign` 靠 `adapter._genvar_context` (id-keyed dict)
   做 genvar substitute, 但 `find_assignments` 遍历不到 Timed 内的赋值
   (缺 Timed/Block/List/ExpressionStatement 分支), dict 永不填充
   → `acc[i]` 无法 substitute 成 `acc[0]`

---

## 🛠️ 修复 (3 处)

### 1. `semantic_adapter.py`: find_assignments 补遍历分支

原 if-elif 链缺 4 个分支, 导致 Timed 内的赋值遍历不到:
- **Timed** (`@(posedge clk) ...`) → 递归 `.stmt`
- **Block** (`begin ... end`) → 递归 `.body`
- **List** (多语句) → 递归 `.list`
- **ExpressionStatement** → 递归 `.expr`
- `_iter_children` 加 `stmt`/`list` 属性 (Timed 用 `.stmt` 不是 `.statement`)

### 2. `semantic_adapter.py`: get_assignments 保持契约

`find_assignments` 修复后开始返回 procedural assignment,
但 `_create_assign_edges` 只处理 continuous → **procedural 只存 `_genvar_context`,
不 append 到返回列表** (保持 get_assignments 只返回 continuous 的契约)。

### 3. `always_extractor.py`: generate always 遍历 + genvar 注入

- `_create_always_edges` 主循环合并 `get_always_blocks` + `get_generate_always_blocks`
- `_collect_stmts_with_context` 加 `genvar_ctx` 参数, 注入每条 item 的 `ctx["_genvar"]`
- 主循环把 `ctx["_genvar"]` 塞进 `adapter._genvar_context[id(stmt)]`
  (id 不可靠, 用当前 stmt 的真实 id 重新登记), 保证 `_parse_assign` substitute

---

## 📈 验证

### 修复效果 (probe_8g, G2 Fixture 5)

```
修复前: 只有 BIT_SELECT 边 (5条), 无 DRIVER/CLOCK 边, 残留 acc[i] 节点
修复后:
  BIT_SELECT: acc[0..4] → acc            (5条)
  DRIVER:     data_in → acc[0..3]        (4条, acc[i] 已 substitute)
  DRIVER:     acc → acc[1..4]            (4条, acc[i+1] <= acc[i] 的驱动)
  CLOCK:      clk → acc[0..4]            (5条)
  无 acc[i]/acc[i+1] 残留节点
```

### 回归: 全套 0 新增失败

| 测试套 | 基线 `ab75e66` | 修复后 | 结论 |
|---|---|---|---|
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |
| `unit` | 4 failed (沙箱) | **4 failed** | ✅ 0 回归 |
| `test_case27_1to1_truth` | — | **4 passed** | ✅ 全绿 |

### 🔑 行为等价: 6 探针全部 byte-identical

assign/flatten/always/function/net_decl/generate-for 全部与基线一致 —
**修复没有破坏任何既有路径** (generate-for 场景是纯新增能力)。

### 新测试 + 有效性验证

`test_generate.py::test_generate_for_dynamic_bitselect`:
- 断言 BIT_SELECT ≥4 条、data_in → acc[0..3]、无 acc[i] 残留
- **验证有效性**: revert 修复后测试失败 (`data_in 应驱动 acc[0..3], got []`),
  证明测试能抓住这个 bug

### ruff

3 个改动文件全部 All checks passed (顺手修了 semantic_adapter 先期 I001)。

---

## 💡 关键发现 / 教训

1. **#8 的 BIT_SELECT 部分被 #2 顺带修复** — 调查先复现再定位,
   避免修一个已经不存在的问题。G2 时代是 0 条, 现在 5 条。
2. **"0 边"有两个不同根因** — BIT_SELECT (walker 看不到) 和 DRIVER
   (always 块不枚举 + genvar 不 substitute), 前者 #2 已修, 后者本次修。
3. **id-keyed dict 方案脆弱** — `_genvar_context` 依赖两次遍历返回同一
   Python 对象, 实测有时不匹配。本次改为在消费侧 (always_extractor)
   用 stmt 真实 id 重新登记, 保证命中。
4. **测试有效性验证** — revert 修复跑测试, 确认测试真能抓住 bug,
   避免"测试通过但没测到"的假阳性。

---

## 📌 #8 完成

ARCHITECTURE_TODOLIST #8 (generate-for 动态位选) — **DONE**。
项目总进度: #1 ✅ + #2 ✅ + #3 ✅ + #8 ✅; 剩余 #4~#7。
