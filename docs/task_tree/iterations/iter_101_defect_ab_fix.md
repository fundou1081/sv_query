# Iteration 101: 缺陷 A + B 修复 — expression 提取 + net-decl 位宽

**Metadata**:
- **Iteration #**: 101
- **Task Tree Level**: L1 (Truth 层扩充顺带发现的缺陷 A-F)
- **Parent Task**: 缺陷修复 (iter_088~100 发现)
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "继续")
- **Outcome**: ✅ 成功 (A/B 修复, 回归测试补齐)

## 🎯 本次目标

修复 truth 层扩充发现的缺陷 A (assign 边 expression 提取损坏) 和
B (net-decl wire 显式位宽被忽略)。

## 📊 当前状态 / 预期结果

- A: `assign sum = a + b` 的 edge.expression = 整份源文件+空字节 (下游
  handshake/dataflow/viz 消费受影响)
- B: `wire [15:0] sum = a + b` → width=(1,0) (声明位宽被忽略)

## 🔬 实际结果

### 缺陷 A: semantic_adapter.get_source_text (根因)

- 原实现 `sm.getSourceText(buf)` 返回**整个 buffer 的完整源码** (含 \x00),
  不是节点 sourceRange 的片段 — 文档注释自己都写着"获取完整源码"
- 修复: 按 `sr.start.offset / sr.end.offset` 切片
- **第二个坑**: pyslang offset 是 **UTF-8 字节偏移**, 非字符偏移 —
  源含非 ASCII (如注释里的 — em-dash) 时字符切片错位 (1_op fixture 实测
  'a + b' 切成 'ign p') → 必须按字节切片再 decode
- 顺带清理: assign_extractor/always_extractor 里重复的
  `get_source_text(...) or str(...) or get_source_text(...) or str(...)` 调用

### 缺陷 B: net_decl 位宽 (根因)

- `_ensure_signal_node` 硬编码 `width=(1, 0)` — 所有内部信号节点都是 1 位
- `extract_data_width` 两条路径都拿不到 NetSymbol 位宽:
  - declaredType 无 `.width` 属性 (旧语义路径失效)
  - NetSymbol 的 `.syntax` 是 DeclaratorSyntax (无 `.type`), 语法路径失效
- 修复 (3 处):
  1. `extract_data_width`: 新增 `declaredType.type.getBitVectorRange()`
     → '[15:0]' 字符串解析 (实测 pyslang 11)
  2. `get_generate_net_declarations`: dict 加 "width" 键
  3. `net_decl_extractor`: 新增 `_ensure_net_node` helper 用声明位宽建节点
     (替代 ensure_signal_node 硬编码), 顶层 + generate 两循环都用

### 验证

- 5_combined: sum/prod width (1,0) → **(15,0)** ✓
- case27 generate wire `wire [W-1:0] prod`: gen_accum[N].prod → **(7,0)** ✓
- 1_op (非 ASCII 注释): expression 'a + b' / 'a * b' ✓
- T1 truth: 9 → 12 passed (补 assign expression ×2 + net 位宽 ×2 断言)
- width 相关 unit (test_width_extraction / test_width_tuple_defense) 全绿

### ⚠️ 残留意 (非本次范围)
- 模块级**无初始化器**的 net 声明 (如 case27 顶层 `wire prod;`) 仍 (1,0) —
  需走 create_var_nodes 或网表声明宽度路径, 记录待定

## 💡 关键发现 / 决策

1. **getSourceText(buf) ≠ 节点文本**: pyslang 的 SourceManager 按 buffer 粒度
   取全文, 节点文本必须按 sourceRange offset 切片 — 文档注释误导了实现。
2. **pyslang offset 是字节**: 非 ASCII 源 (注释/字符串) 会让字符切片错位,
   必须 bytes 切片再 decode — 这类 bug 只在含多字节字符的 fixture 出现,
   纯 ASCII 测试测不出来 (5_combined 正常, 1_op 暴露)。
3. **硬编码默认值掩盖真实数据**: width=(1,0) 硬编码让"宽度提取失败"与
   "1 位信号"不可区分 (AGENTS.md 纪律 2.5 同款问题)。

## 📌 状态

- ✅ 缺陷 A 修复 (get_source_text 字节切片) + 回归断言
- ✅ 缺陷 B 修复 (extract_data_width + net_decl_extractor) + 回归断言
- ⚠️ ventus usage 层 14 failed 为 pre-existing (external 项目, 与本次无关)
- 下一步: 缺陷 C (LHS 拼接位置映射) / D / E / F
