# Iteration 218: 批次 3a 冒烟通过但全量恶化 (34 → 116), 已回退 + 换方法

**Metadata**:
- **Iteration #**: 218
- **Task Tree Level**: L1 (纪律强制 · 执行)
- **Parent Task**: 方豆 "按这个继续做" (iter_217 的配方: 只做 3a → 冒烟 → 子集 → 提交)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ❌ 3a 未通过全量验证 → 回退 (本次重构第 4 次自伤, 如实记录)

## 🎯 本次目标

按 iter_217 配方执行 3a: 删除 CLI 侧 `strict` 形参与死传参, **只动 `src/cli/**`**
(不碰 `src/trace/**`), 冒烟通过后跑子集并提交。

## 🔬 实际结果

| 阶段 | 结果 |
|---|---|
| 第一次 (范围过大, 连 `src/trace` 的 `UnifiedTracer.__init__` 形参也删) | **NameError: name 'strict' is not defined** → 冒烟 stats/trace/visualize/coverage 全 rc=1 → 立即回退 |
| 第二次 (**限定 `src/cli/**`**, `strict=True` 对账 **111 → 0**) | **冒烟 5/5 全 rc=0** (stats/trace/design/visualize pipeline/coverage generate) |
| 全量 canonical | **116 failed / 3200 passed** ← 比批次 2 的 34 failed **恶化 82 个** |
| 回退 | 从 `/tmp/src_b3a` 恢复; 复核 stats/coverage rc=0, `test_design.py`+`test_filelist_parity.py` **15 passed**, 工作树干净 |

**结论**: 3a 在**冒烟层**通过, 但**全量层显著恶化** → 说明我的"删传参"手法仍不完整/不安全
(最可能: 存在**位置传参** `_build_tracer(file, filelist, strict, ...)` 之类, 删掉形参后
位置错位 → 静默行为错 → 大量断言失败; 也可能是某些调用点仍以未覆盖形态传 `strict`)。

## 💡 关键发现 / 关键技术 / 决策 (第 4 次同类教训)

1. **冒烟通过 ≠ 安全**: 5 个命令 rc=0 只覆盖了"最常见的调用形态", 而 116 个失败来自
   其它调用形态 (位置传参/别名/包装函数)。**全量门禁才是判据** —— 这点必须成为纪律:
   凡改签名, 必须跑全量再提交。
2. **机械改签名的风险被严重低估**: 这是本次 `strict` 移除的第 4 次回退
   (iter_216 常量/import, iter_217 行内形态, iter_218 范围+位置传参)。共同根因:
   **我在用正则做本应逐点审查的调用点改造**。
3. **换方法 (下次必须)**: 不再"正则批量删", 改为:
   - 用 **AST** 精确定位每一个 `strict` 形参与每一处 `strict=` 实参 (并用 `ast.walk` 统计数量, 与 `grep -c` 对账);
   - **逐文件**改 + 改完立刻 `pytest` 该文件相关用例;
   - 只在**全量绿**的批次上提交;
   - 位置传参必须单独检查 (AST 能区分 keyword vs positional)。
4. **核心层仍是硬骨头**: `src/trace` 的 `strict` 是语义分支 (raise vs partial AST),
   即便 AST 方法也要单独设计 (删降级分支 = 行为变更, 会暴露 fixture 真错)。

## 📢 下一步 (方法已换)

1. 写一个 **AST 驱动的重写脚本**: 枚举 `strict` 形参 (含位置) 与 `strict=` 实参,
   输出**清单 + 数量**, 与实际 `grep -c` 对账 (不猜形态);
2. 按清单逐文件改, 每改一个文件跑其相关测试;
3. 3a 落地后再进核心层 (批次 3b);
4. 保持每批全量门禁, 只在绿 (或"失败集不变差") 时提交。

## 📎 关联

- 配方来源: `iter_217_remove_strict_batch3_attempt_reverted.md`
- 备份: `/tmp/src_b3a` (本次回退来源); 当前全量基线仍是批次 2 的 34 failed / 3282 passed
