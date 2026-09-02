# Iteration 107: #23 generate-if 单块内 wire 声明提取

**Metadata**:
- **Iteration #**: 107
- **Task Tree Level**: L1 (EXTRACTION_COVERAGE #23)
- **Parent Task**: A-F 修复后续 (方豆 "继续")
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

修复 #23: generate-if/else 单块 (GenerateBlock, 非 Array) 内的 `wire x = expr;`
声明不被提取 — 镜像 iter_103 缺陷 F (always 单块修复)。

## 📊 当前状态 / 预期结果

- probe_generate_if_wire.sv 实测 0 节点/0 边 (wire prod1 = a*b 完全丢失)
- spec 测试锁定旧行为 (edges == {})

## 🔬 实际结果

### 根因 (同缺陷 F)

`get_generate_net_declarations` 只处理 GenerateBlockArray (for/case 展开),
generate-if/else 单块 (GenerateBlock) 的 net 声明漏掉。

### 修复 (semantic_adapter.get_generate_net_declarations)

- 增加 GenerateBlock 分支 (镜像 get_generate_always_blocks 的缺陷 F 修复):
  跳过 isUninstantiated (未激活分支), 收集 Net child (name/initializer/
  hierarchical_path/width)
- 注意: 首版 elif 缩进错误 (try/for 循环仍在 if 外) → 语法错 —
  重写整个函数为 if/elif 结构 (与 F 修复同坑)

### 验证

- probe_generate_if_wire (USE=1): **g_use1.prod1 节点 + a→prod1, b→prod1
  DRIVER 边 (expr='a * b')**; g_use0.prod0 (未实例化) 不出现 ✓
- spec 测试更新: test_generate_if_wire_needs_hierarchical_name →
  test_generate_if_wire_extracted (断言 2 条 DRIVER)
- T10 truth +3 (激活分支节点/边 + 未激活反例)

### 文档同步

- EXTRACTION_COVERAGE: #23 从"有条件支持 (GenerateBlock 未处理)" →
  完整支持 (iter_107); 状态变更日志记录

## 💡 关键发现 / 决策

1. **同一函数族同坑**: get_generate_always_blocks 和 get_generate_net_declarations
   结构相同, F 修复的 elif 缩进坑在 #23 又踩一次 — 两个函数后续重构可考虑
   合并遍历 (GenerateBlockArray + GenerateBlock 公共逻辑)。
2. **isUninstantiated 是分支激活的统一判据**: always 和 net 声明都用它跳过
   未激活分支, 语义一致。

## 📌 状态

- ✅ #23 修复 (GenerateBlock net 声明提取) + spec 测试更新 + T10 +3
- 全量回归: 待确认 (预期零新增失败)
- 剩余: #24 generate-case 单块 net 声明 (同 GenerateBlock 路径, 应已覆盖,
  待 fixture 验证)
