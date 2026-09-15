# Iteration 223: 修 mutating-test fixture — POC 语料补全 (5 个新失败清零)

**Metadata**:
- **Iteration #**: 223
- **Task Tree Level**: L1 (纪律强制 · 目标轮次 1)
- **Parent Task**: goal-e8196ce3 (逐文件彻底移除 strict)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 5 个新失败清零 (37 → **32**), 与基线持平

## 🎯 本次目标

iter_222 的批量改写把全量从 32 → 37 failed。本轮**精确定位并修掉这 5 个新失败**。

## 🔬 实际结果

### 定位 (worktree 对照法, 精确求差)

```bash
git worktree add /tmp/wt_baseline f78e7d2        # 上一 commit (handshake 状态 = 32 failed)
# 在基线 worktree 与新代码分别跑同一批文件, 求 FAILED 差集
comm -13 /tmp/base_fails.txt /tmp/now_fails.txt
```

结果: 5 个新失败**全部**在 `sim/tests/poc/test_portconn_native_poc.py`
(该文件在基线 12 failed / 现在 17)。

### 真因: 测试的**语料文件清单不完整** (过去靠 API 级 `strict=False` 容忍)

- 该测试加载 darkriscv 的 10 个 `rtl/*.v`, 但 `darkspi.v` 实例化的 `spi_master`
  **定义在同语料的 `rtl/lib/spi/spi_master.v`** (实测该文件存在);
- 过去 `SVCompiler(..., strict=False)` 把 `unknown module 'spi_master'` 降级吞掉;
  移除 `strict` 后暴露 → 报 `Elaboration errors: darkspi.v:140 unknown module 'spi_master'`。

### 修复 (真修 fixture, 不是降级)

`_load_darkriscv()` 的文件清单补上 `lib/spi/spi_master.v` + 注释说明原因。

| 检查 | 结果 |
|---|---|
| `test_portconn_native_poc.py` | **5 passed** (修复前 5 failed) |
| **全量 canonical** | **32 failed / 3283 passed** ← 与基线持平 (37 → 32) |

## 💡 关键发现 / 关键技术 / 决策

1. **worktree 对照法**是精确归因的利器: `git worktree add <commit>` 可以**不动工作树**
   地跑基线, 用 `FAILED` 差集一步定位"哪些是新引入的失败" (比猜测快得多)。
2. **"移除 strict 后暴露的失败" 大多是 fixture 不完整**: 本次是语料清单少了文件
   (同语料里其实有定义)。这验证了 `strict` 的移除价值 —— 它把"清单不全"变成了
   可见的错误, 而不是静默降级。
3. **fixture 修复优于任何降级**: 补一个文件路径 vs 恢复 `strict=False`, 前者让测试
   真正验证完整编译。

## 📢 下一步

1. **核心层 `self._strict`** (剩余 27 处 / 7 文件): `compiler.py` / `unified_tracer.py` /
   `sv_extractor.py` / `native_adapter.py` 等 —— 删 `self._strict` = 删"返回 partial AST"
   降级分支 (语义变更), 需逐文件 + 全量验证;
2. 之后清理"移除 strict 暴露的 fixture 真错"剩余项 (fix_report / fix_imports /
   pyslang_type_extraction / f2 等, 属 32 基线的一部分);
3. 最后清可视化 16 个 (按方豆指示暂缓)。

## 📎 关联

- 前序: `iter_222_perfile_mass_rewrite.md` (202 → 27 处); goal: `goal-e8196ce3`
