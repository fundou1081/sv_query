# Iteration 227: 尾随逗号清理 — 用 AST 等价闸重做, 46 处归零

**Metadata**:
- **Iteration #**: 227
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_zero_red_and_policy_followups.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 成功 (46 处 → 0 处, 19 文件, 0 拒绝)

## 🎯 本次目标

iter_226 把"46 处尾随逗号"记为**尝试失败 + 决策保持原样** (脚本误删 1-tuple 逗号,
`outputs=("root",)` → `("root")` 语义从 tuple 变 str, 已回退)。
但方豆的指令 ("去做吧") 包含这一项, 而失败的原因**不是"做不到"**, 是**缺一道机械闸**:

- 缺陷 1: `end_col_offset - 2` 取错了括号位置 (应 `- 1` 取 Call 自己的 `)`)
- 缺陷 2: `col_offset` 是 **UTF-8 字节偏移**, 中文注释文件里直接当字符下标会崩/错位
- 缺陷 3 (**根因**): 没有任何东西阻止"删掉 1-tuple 的逗号" —— 描述性警告 (iter_224
  文档里我自己写过) 挡不住脚本

→ 本轮补上**机械保障**后重做。

## 🔬 做法: AST 等价闸 (关键创新点)

核心思路: **删尾随逗号不应改变 AST**。

- Call 实参列表的尾随逗号: 删掉后 `ast.dump()` **完全一致** (逗号不产生节点)
- 1-tuple 的逗号: 删掉后 `Tuple` 节点消失 (变成 `Constant`/`Name`) → `ast.dump()` **变化**

因此: 每个文件改完后, 用 `ast.dump(tree_before) != ast.dump(tree_after)` 判断 ——
**不等就拒绝写入该文件** (不是警告, 是硬拒绝)。这正好补上 iter_226 缺的那道闸,
而且它同时覆盖了"我还没想到的其它语义陷阱"。

精确定位 (只改"属于 Call 自己的实参列表"的逗号):

```python
close = b2c(line, c.end_col_offset) - 1     # Call 自己 ')' 的字符下标 (字节→字符)
if line[close] != ')':  continue            # 跨行/非典型 → 不猜, 跳过
k = close - 1
while line[k] == ' ': k -= 1                # 跳过空格
if line[k] == ',':  删除 [k, close)         # 连逗号带空格一起删 → f(a, b)
```

## 📊 实际结果

| 指标 | 值 |
|---|---|
| 清理文件 | **19** (`src/cli/commands/*` 16 + `src/cli/main.py` + `tools/verify_native_parity.py`) |
| 尾部逗号 | **46 → 0** (唯一残留匹配是 `__slots__ = ("_original",)` —— 合法 1-tuple, 正确未动) |
| AST 闸拒绝 | **0 文件** (说明 19 个文件的改动都是纯风格) |
| 语法复核 | 全仓 `src/` + `tools/` `ast.parse` 无错 |
| 1-tuple 保全 | `outputs=("root",)` 在 `unified_tracer.py` 中完好 (实测 `grep -c` = 1) |
| 抽样 diff | `CovergroupExtractor(sources=sources, )` → `CovergroupExtractor(sources=sources)` |
| CLI 套件 | **409 passed** |
| 全量 canonical | **3317 passed / 0 failed** (与 iter_226 持平, 0 恶化) |

## 💡 关键发现 / 决策

1. **"描述性警告"挡不住脚本, 机械闸才行**: iter_224 文档写了"盲正则会把 `(x, )`
   改坏", iter_226 的脚本照样改坏 —— **同一个教训在 iter_190 出现过一次**
   (`except: pass` 计数声明为 0 后又长回来, 于是加了 `tools/check_except_pass.py`)。
   本轮的对策同样是"加闸"而不是"下次小心"。
2. **AST 等价闸是通用手法**: 任何"意在不改变语义的机械改写"都可以用它兜底 ——
   `ast.dump` 相同 = 语义结构未变。比逐条 review 便宜, 比"小心一点"可靠。
   → **建议 (主动告知)**: 将来再把这类改写固化成工具时, 把 `ast.dump` 等价检查
   做成默认开关 (现在是就地脚本, 未落成 `tools/` 下的常驻工具)。
3. **失败记录的价值**: 正因为 iter_226 如实写了失败与回退 (含 1-tuple diff 原文),
   本轮才能直接定位"缺的是哪道闸"并一次做对。若上轮写成"清理完成"或干脆不提,
   这次就会重新踩一遍。
4. **唯一残留是合法的**: `__slots__ = ("_original",)` 是 1-tuple, 语义上**必须**
   保留逗号 —— 脚本正确地没碰它 (它不在 Call 实参位置)。

## 📎 产物

- 19 个文件: 删尾随逗号 (纯风格, AST 不变), 见 `git diff --stat`
- 文档: 本文件 + `tasks/L1_zero_red_and_policy_followups.md` (第 2 项状态更新) +
  `CURRENT_TODO.md` + `overview.md` + `docs/INDEX.md`
