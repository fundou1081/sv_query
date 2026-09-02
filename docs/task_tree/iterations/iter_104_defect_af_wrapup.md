# Iteration 104: 缺陷 A-F 修复收尾汇总

**Metadata**:
- **Iteration #**: 104
- **Task Tree Level**: L1 (缺陷 A-F 修复)
- **Parent Task**: 缺陷修复 (iter_088~100 发现)
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "继续")
- **Outcome**: ✅ 成功 — A-F 全部修复, 零回归

## 🎯 本次目标

收尾: 汇总 A-F 修复成果, 同步所有追踪文档。

## 📊 当前状态 / 预期结果

- iter_101~103 完成 A-F 六项修复
- 预期: 文档同步 + 全量验证记录

## 🔬 实际结果

### 修复清单 (6 项, 3 个 iter)

| 缺陷 | 根因 | 修复 | iter |
|---|---|---|---|
| A assign expression 整份文件 | get_source_text 取整个 buffer 而非 sourceRange 片段 | 按 sr.start/end.offset **字节**切片 (pyslang offset 是 UTF-8 字节) | 101 |
| B net-decl 位宽忽略 | ensure_signal_node 硬编码 (1,0); extract_data_width 拿不到 NetSymbol 位宽 | declaredType.type.getBitVectorRange() + _ensure_net_node | 101 |
| C LHS 拼接笛卡尔积 | 注释说对齐映射, 实现是嵌套循环 | zip 位置对齐 | 102 |
| D localparam ternary 无常量边 | 分支名被 compile-time 过滤, 值未物化 | _resolve_const_value (lookupName→sym.value), arm key + leaf 两处一致 | 102 |
| E 动态 part-select 宽度假数据 | bus[?:?] 占位节点硬编码 (1,0) | '?' 占位 → width=None (未知) | 103 |
| F generate-if 内 always 不提取 | get_generate_always_blocks 只处理 GenerateBlockArray | +GenerateBlock 分支 (跳过 isUninstantiated) | 103 |

### 回归测试 (truth 层 +1 file 33, +13 测试)

- T1 +3 (assign expression ×2 + net 位宽 ×2... 实际 T1 9→12)
- T5 +3 (LHS 位置映射)
- T7 +1 (真分支常量边)
- T10 +4 (generate-if always) — 新 fixture 36 (lhs_concat)
- test_known_limitations: has_no_drivers → has_drivers (锁定旧 bug 的测试更新)
- subfunction_open_source golden ×4 重生成 (D 修复改变 driver expression)

### 全量验证

- unit+cli+integration+truth (排除 usage): **2835 passed + 1 failed (picorv32
  ELK 暂缓) + 7 skipped**
- ventus usage 层 14 failed pre-existing (外部项目依赖, 与本工作无关)
- 教训: 回归运行中不要改代码 (bash-36 混入 91 假失败)

## 💡 关键发现 / 决策

1. **truth 层 = 缺陷探测器 → 修复闭环**: iter_088~100 用 golden 发现 A-F,
   iter_101~103 修复并补断言 — golden 从"锁定 bug"变为"锁定修复"。
2. **pyslang 偏移单位 (字节) 是 A 的隐藏坑**: 纯 ASCII 测试测不出, 含
   非 ASCII 注释的 fixture 才暴露。
3. **'?' 占位 = 未知宽度的诚实 sentinel**: E 修复与 graph_builder 默认一致。
4. **golden 锁定 bug 的更新原则**: 工具行为合法改变 (修复) → golden 重生成
   (BITSELECT 决策同款: golden 是 ground truth, 不是 source of truth)。

## 📌 状态

- ✅ 缺陷 A-F 全部修复 (iter_101~103), 零回归
- 遗留: picorv32 ELK (方豆拍板暂缓) / ventus usage (pre-existing) /
  EXTRACTION_COVERAGE 需同步 A-F 修复 (#11 LHS concat, #41, generate-if 等)
- 文档: overview / CURRENT_TODO / TEST_MAP 同步
