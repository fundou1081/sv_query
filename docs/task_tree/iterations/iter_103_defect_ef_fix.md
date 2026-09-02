# Iteration 103: 缺陷 E + F 修复 — 动态 part-select 宽度 + generate-if 内 always

**Metadata**:
- **Iteration #**: 103
- **Task Tree Level**: L1 (缺陷 A-F 修复)
- **Parent Task**: 缺陷修复 (iter_088~100 发现)
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "继续")
- **Outcome**: ✅ 成功 (E/F 修复, A-F 全部完成)

## 🎯 本次目标

修复缺陷 E (indexed part-select 动态索引 → bus[?:?] 宽度假数据) 和
F (generate-if/else 内 always 块不提取)。

## 📊 当前状态 / 预期结果

- E: `bus[{sel,3'b000} +: 8]` → bus[?:?] 节点 width=(1,0) (假数据, 暗示 1 位)
- F: generate_if_alu (TWO_CYCLE_ALU=0 else 分支) 只有 2 条 BIT_SELECT 边,
  always @* 的赋值无 DRIVER 边

## 🔬 实际结果

### 缺陷 E: driver_extractor._ensure_signal_node (根因)

- `bus[?:?]` 占位节点由 ensure_signal_node 硬编码 width=(1,0) 创建 —
  "?" 是 _extract_base_chain/get_signal 对无法静态解析位选的一致占位标记,
  (1,0) 是假数据 (动态 base 的 part-select 宽度未知)
- 修复: 名字/节点 id 含 "?" → width=None (未知), 其余保持 (1,0)
- 先试了 graph_builder 位选 pass 的 elif 补丁 — 实测该 part-select 无
  BitSelectHit (占位节点不走那条路径), 属死代码, 按纪律回退
- 验证: bus[?:?] width (1,0) → None; 静态位选 bus[7:0] 仍 (7,0)

### 缺陷 F: semantic_adapter.get_generate_always_blocks (根因)

- always_extractor 收集顶层 (get_always_blocks) + generate-for 内
  (get_generate_always_blocks), 但 **generate-if/else 单块 (GenerateBlock,
  非 Array) 内的 always 全部丢失**
- pyslang 用 isUninstantiated 标记未激活分支 (TWO_CYCLE_ALU=0 →
  IfTrue 未实例化)
- 修复: get_generate_always_blocks 增加 GenerateBlock 分支 (跳过
  isUninstantiated, 收集 ProceduralBlock)
- 验证: generate_if_alu else 分支 (always @*) 现在有 8 条 DRIVER 边
  (reg_op1/reg_op2[4:0]/instr_sra/instr_srai → alu_shl/alu_shr),
  且无 CLOCK 边 (else 分支是组合逻辑, if 分支未实例化) — 正确

### 顺带更新 (golden/测试锁定旧 bug)

- test_known_limitations::test_generate_if_alu_shr_has_no_drivers →
  **has_drivers** (F 修复后 limitation 解除, 测试自己写着 "If >0, update")
- subfunction_open_source golden ×4 (prim_arbiter dataflow/risk/stats/timing)
  — D 修复改变 driver expression, 按 golden=ground truth 原则重生成

## 💡 关键发现 / 决策

1. **"?" 占位 = 未知宽度的一致标记**: _extract_base_chain/get_signal 用
   `[?:?]`/`[?]` 表示无法静态解析 — ensure_signal_node 据此置 None 而非 (1,0),
   与 graph_builder 位选路径默认一致。
2. **测试锁 bug 时有明确信号**: known_limitations 测试注释 "If >0, the
   limitation is now fixed; update this test" — 修复后按提示更新即可。
3. **跑回归时不要改代码**: bash-36 因运行中改文件出现 91 个假失败 —
   全量验证必须在稳定树上跑。

## 📌 状态

- ✅ 缺陷 E 修复 (占位节点宽度 None) + T4 断言
- ✅ 缺陷 F 修复 (GenerateBlock always 收集) + T10 4 测试 + known_limitations 更新
- ✅ **A-F 全部完成** (iter_101~103)
- 全量验证: 待最终回归 (仅 picorv32 ELK 暂缓项)
