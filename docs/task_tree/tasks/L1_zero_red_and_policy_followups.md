# L1: 全量归零 + 策略/收尾项 (阈值 / 冻结 skip / 尾随逗号)

**Metadata**:
- **Task Tree Level**: L1
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Status**: ✅ CLOSED (iter_226)
- **触发指令**: 方豆 **"去做吧"** (对上轮列出的 5 个待决项)

---

## 🎯 任务范围

上一轮 (iter_225) 达成"只剩 16 个暂缓的可视化红"后, 列出 5 个待办, 方豆指示全部执行:

| # | 项 | 结果 |
|---|---|---|
| 1 | 修掉最后 16 个可视化红 (`test_visualize_teach_nested_mux.py`) | ✅ **16 passed** (fixture `output` → `output reg`) |
| 2 | 46 处尾随逗号按 AST 清理 | ❌ iter_226 尝试失败已回退 → ✅ **iter_227 补 AST 等价闸后重做成功**: 46 → 0 处 / 19 文件 / 0 拒绝 |
| 3 | `check_regression.py` 阈值收紧 50%/0.7 → 30%/1.0 | ✅ 已收紧 (含"L1/L4 仅警告"的如实说明) |
| 4 | 评估 13 个冻结可视化断言 skip 是否转正 | ✅ 分诊: **1 个转正** (arch d=1, artifact 此前从未生成), 12 个按方豆决策 ③ 继续暂缓 (理由已改准确) |
| 5 | `collect_elaboration_diagnostics` 防御分支能否构造测试 | ✅ **可构造** (iter_225 的"不可达"判断被证伪), 已补回归测试 |

**最终状态**: 全量 canonical **3316 passed / 0 failed**。

---

## 📌 遗留 / 待方豆拍板

1. **L1/L4 是否改成硬失败**: 本工具的 L1/L4 越界历来**只警告不改退出码**, 所以阈值
   50→30 只让警告更早出现; 真正改变 CI 判定的是 flakiness 0.7→1.0 (硬失败)。
   若要把 L1/L4 也变硬失败 (= 真正的收紧), 需单独批准。
2. **12 个可视化 skip 转正**: 需要"按 SVG 语义重写断言" (方豆决策 ③ 现阶段不处理)。
3. ~~**尾随逗号**: 46 处 / 19 文件待清~~ → ✅ **iter_227 已清零** (方法: 只删
   "属于 Call 自己实参列表"的逗号 + `ast.dump` 等价硬拒绝, 见 iter_227)。

---

## 📎 相关迭代

[iter_226](../iterations/iter_226_zero_red_and_policy_followups.md) (本轮) /
[iter_225](../iterations/iter_225_strict_unmasked_failures_cleared.md) /
[iter_224](../iterations/iter_224_strict_core_layer_removed.md)
