# Iteration 117: 索引段加倍假节点修复 — get_path gen_block 二次拼接去重

**Metadata**:
- **Iteration #**: 117
- **Task Tree Level**: L2 (openrtl 摸底 → 缺口修复)
- **Parent Task**: [tasks/L2_index_segment_doubling_fix.md](../tasks/L2_index_segment_doubling_fix.md)
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

修复 iter_116 target 重扫发现的**索引段加倍假节点** (多项目真实复现):
- aes Top_PipelinedCipher: 84 个 — `U_SUB.ROM[4].ROM[4]`
- dblclockfft fftmain/ifftmain: 63 个/模块 — `p3.STAGES.FOR.GENSTAGES[0].GENSTAGES[0].genmpy`

## 📊 当前状态 / 预期结果

- 触发: 实例在 generate-for entry 内且该 gen 位于**嵌套实例之下**时路径加倍
- genfor (顶层 gen) / CLA (实例下单层 gen) 正常 — 曾疑 legacy 族覆盖所致

## 🔬 实际结果

### 诊断 (最小复现 + 归因)

- 最小复现 (实例 u_bfly → p3 → STAGES→FOR→GENSTAGES for-gen → genmpy):
  connection extractor **16 个加倍节点**, driver/load/clock 0 — 归因 connection
- **根因**: `get_path` 的 gen_block 分支。实例 genmpy 的 hp 父路径 =
  `top.u_bfly.p3.STAGES.FOR.GENSTAGES[0]` (**已含索引段**);
  `_get_generate_block_name` 的 hp 正则又取一次 `GENSTAGES[0]` →
  `f"{parent_mod}.{gen_block}.{inst}"` 拼成 `...GENSTAGES[0].GENSTAGES[0].genmpy` 双段
- **为何 genfor/CLA 未炸**: 其 legacy `get_generate_instances` 族 (parent=顶层
  短名, 无索引) 与 indexed 族同 key, 后写覆盖成单索引路径 — 掩盖了 bug;
  无 legacy 族时 (generate 在嵌套实例的模块内, get_generate_instances 收不到)
  即暴露。这与 iter_113 的 legacy 族判断互相印证。

### 修复 (connection_extractor.get_path)

父路径已以 `[N]` 结尾 (即父路径本身已是 gen entry) → `gen_block = None`
(索引已在 parent 中, 不再二次拼接)。三处 gen_block 返回点统一受益。

### 验证

- FFT 最小复现: doubled 16→0; 正确单索引路径
  `top.u_bfly.p3.STAGES.FOR.GENSTAGES[i].genmpy.*` 16 节点在位
- 真实: aes 84→**0** (节点 3986→3841, 假节点净删), dblclockfft fftmain/
  ifftmain 63→**0** (5888→5843)
- 既有 74 passed 零回归 (cordic/genfor/CLA/gate/connection/generate/d1)
- 新 unit +3 (TestIndexSegmentDoubling: 嵌套 gen 无加倍 / 单索引路径在位 /
  顶层 gen 形态仍单索引 — target 显式化), test_nested_generate_instance 4→7
- 全量回归结果见 commit

## 💡 关键发现 / 决策

1. **索引段是"不可重复段"**: 任何路径里同层索引段 (gen entry / 数组元素)
   出现两次必假 — 可用作通用回归探针 (unit 里 _doubled_segment)。
2. **legacy 族掩盖类 bug 的教训再现** (iter_113 已见一次): "行为正常"可能是
   双族 key 覆盖的巧合; 真实验证必须在无 legacy 场景 (嵌套实例内 gen) 下做。
3. `_get_generate_block_name` 的 hp 正则对"父路径已带索引"的实例天然重复 —
   根治点是路径组装层 (parent 含索引则不拼 gen_block), 而非正则本身。

## 📌 状态

- ✅ 代码 + 测试 (unit +3) + 本文档; 全量回归见 commit
