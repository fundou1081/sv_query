# L1: 彻底移除 strict (恒定严格)

**Metadata**:
- **Task Tree Level**: L1
- **Created**: 2026-09-08 (登记) / 2026-09-09 补建文件 (iter_224 收尾)
- **Author**: 方豆 / AI 助手
- **Status**: ✅ CLOSED (iter_215 ~ iter_224)
- **触发指令**: 方豆 "去除默认值, **彻底移除 strict**。" → "推进批次2, 全部移除"
  → "逐文件修改, 全改" → "继续做, 直到全部完成。"

---

## 🎯 任务背景

`strict` 是 sv_query 早期为应对不完整 RTL / elaboration 报错而引入的
graceful degradation 开关: `strict=False` 时 SVCompiler 不 raise, 而是返回
partial AST, 上层拿到"残缺图"继续跑。

**它为什么必须消失**:

1. **AGENTS.md 核心纪律 1 明令禁止 `--no-strict`** —— 它掩盖真实的代码质量
   问题 (空 graph / 节点缺失 / expr tree 拿不到), 让 debug 不可能。
2. **"假绿"机制**: 大量测试过去靠 `--no-strict` / API 级 `strict=False` 通过,
   撤掉 flag 后暴露出 fixture 与 src 的真实错误 (iter_210 首日就暴露 16 个)。
3. **不传 flag 就是降级更危险**: `design` / `arch` / `backpressure` / `coverage`
   四个命令的 CLI 默认值就是 `strict=False` (iter_214 扫描发现), 用户根本
   不知道自己一直在降级。
4. **`strict=False` 的生产调用点仍在主动降级**: `design.py` 有 **7 处**
   `args.append("--no-strict")` (iter_214 追加发现)。

**决策**: 不是"改默认值", 而是**彻底移除**这个概念 —— 删 CLI 选项、删 API 形参、
删 `self._strict` 语义分支, 工具恒定严格 (elaboration error 一律 raise)。

---

## 📋 执行批次 (6 批, 全部完成)

| 批次 | 范围 | 迭代 | 结果 |
|---|---|---|---|
| 1 | `design.py` 7 处 `args.append("--no-strict")` + 形参 | iter_215 | ✅ |
| 2 | 全部 34 个 `--strict/--no-strict` CLI 选项 + `STRICT_OPTION` 常量 | iter_216 | ✅ |
| 3 | API 形参 (CLI helper / 核心类) | iter_217/218 回退 ×2 → iter_220 | ❌×3 → ✅ |
| 4 | 生产 `strict=False` 调用点 | iter_215/221 | ✅ |
| 5 | 测试 API 级降级 29 处 + 暴露的 fixture | iter_210~213, iter_223 | ✅ |
| 6 | 核心层 `self._strict` 语义分支 (`compiler.py` 降级分支 + 3 个类) | iter_224 | ✅ |

**最终状态 (iter_224 + iter_225 验收)**: `tools/scan_strict.py` = **0 处 / 0 文件**,
全仓 (src + tools + sim/tests) 的 `--strict` / `--no-strict` **用法 = 0**,
`SVCompiler` / `UnifiedTracer` / `SVSignalExtractor` 不再有 `strict` 形参或字段;
**全量门禁 3300 passed / 16 failed** —— 16 红全是方豆指示暂缓的
`test_visualize_teach_nested_mux.py` (fixture 有真实 elaboration 错误), 目标态达成。

| 收尾批次 | 范围 | 迭代 | 结果 |
|---|---|---|---|
| 6a | 核心层 `self._strict` + 降级分支 + 全部残留实参 | iter_224 | ✅ 27 处 → 0 |
| 6b | 严格模式暴露的 12 个失败 (语料缺依赖 / fix 命令契约 / 用例锁降级语义) | iter_225 | ✅ 28 → 16 failed |

**移除降级开关的必然代价 (两次实测)**: `strict=False` 时代留下的测试语料普遍**不完整**
(iter_223 darkriscv 缺 `spi_master`, iter_225 NaplesPU 缺 `memory_bank_1r1w`),
撤掉降级后必须逐个补全 —— 这也是移除 strict 最大的价值: 把"假绿"变成"真红"。

---

## 🔑 关键教训 (5 次回退换来的)

1. **横切关注点不能用"一次改一层"**: `strict` 贯穿 CLI → helper → tracer →
   compiler, 任何"只改一层"的做法都会留下未覆盖路径 → 运行时才炸。
   最终采用**逐文件: 改 → `scan_strict` 复测 → 冒烟 → 相关用例 → 全量门禁 → 提交**。
2. **冒烟通过 ≠ 安全**: iter_218 冒烟 5/5 rc=0 但全量 116 failed。
   改签名必须跑全量门禁。
3. **正则改签名必漏**: 位置实参 (正则看不见, 删形参后整体错位)、行内形态
   (`strict=True, other=...`)、字典键形态 (`{"strict": True}`) 都是盲点。
   → 改用 AST 工具 (`tools/scan_strict.py` / `tools/remove_strict_in_file.py`)。
4. **门禁是唯一裁判**: 只有"全量失败数不恶化"才允许提交。

---

## 📎 相关迭代

iter_210 ~ iter_224 (见 `iterations/` 与 `overview.md` 汇总表 #113 ~ #126)。
核心收尾: [iter_224](../iterations/iter_224_strict_core_layer_removed.md)。
