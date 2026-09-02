# Iteration 108: #24 验证 + generate 遍历去重重构

**Metadata**:
- **Iteration #**: 108
- **Task Tree Level**: L1 (EXTRACTION_COVERAGE #24 + 代码质量)
- **Parent Task**: #23 修复后续 (方豆 "继续")
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

1. #24 验证: generate-case 单块内 wire 声明 (GenerateBlock 分支应已覆盖)
2. get_generate_net_declarations / get_generate_always_blocks 去重重构 (iter_107 记录)

## 📊 当前状态 / 预期结果

- #24 理论上被 iter_107 的 GenerateBlock 分支覆盖, 无 fixture 验证
- 两函数同构 (~60 行遍历重复), iter_107 记录建议合并

## 🔬 实际结果

### 1. #24 验证 (probe_generate_case_wire.sv 新建)

- SEL=2 → **g_use2.prod2 节点 + a→prod2, b→prod2 DRIVER 边** (expr='a - b');
  g_use1/g_def (未实例化) 不出现 ✓
- ternary 引用解析: prod2→BRANCH_TRUE, a→BRANCH_FALSE (y = SEL==2 ? prod2 : a)
- spec 测试 +1 (test_generate_case_wire_extracted, 断言 3 DRIVER =
  prod2×2 + a→y 假分支); T10 truth +3
- **#24 与 #23 同修**: case item 也是 GenerateBlockSymbol, GenerateBlock
  分支天然覆盖

### 2. 去重重构 (semantic_adapter)

- 新增 `_iter_generate_children(module, kind_marker)` 共享遍历:
  GenerateBlockArray entries + GenerateBlock 单块, 跳过 isUninstantiated,
  产出 (child, genvar_ctx, array_index, loop_var, container)
- get_generate_net_declarations: 收敛遍历, 保留 Net 专属提取
  (name/init/hp 用 child 的 — G3 原行为)
- get_generate_always_blocks: 收敛遍历, 保留 ProceduralBlock 专属提取
  (hp 用 container 的 — #8 原行为)
- **hp 来源差异保留** (net: child.hp; always: container.hp) — 1:1 不变量

### 验证

- generate 相关 (T10/T9/case27/spec): 34 passed
- 全量回归: 待确认 (预期零新增失败, ~44 行去重)

## 💡 关键发现 / 决策

1. **#24 = #23 的免费午餐**: GenerateBlock 分支同时覆盖 if/else 和 case item,
   补 fixture 验证即可收尾, 无需单独修复。
2. **重构 1:1 的关键**: 遍历收敛但**提取逻辑留在各自函数** (hp 来源不同:
   net 用 child.hp, always 用 container.hp) — 收敛"怎么走", 不收敛"拿什么"。
3. **测试保护重构**: 两函数被 generate truth + spec + 2839 全量覆盖,
   1:1 偏离会被立即捕获。

## 📌 状态

- ✅ #24 验证通过 (probe + spec + truth), #23/#24 同根同修
- ✅ 去重重构 (_iter_generate_children, ~44 行去重), 生成测试全绿
- 全量回归待确认后 commit
