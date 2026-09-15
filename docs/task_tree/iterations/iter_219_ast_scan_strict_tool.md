# Iteration 219: 写 AST 扫描工具 `scan_strict.py` — `strict` 移除的精确清单

**Metadata**:
- **Iteration #**: 219
- **Task Tree Level**: L1 (纪律强制 · 工具)
- **Parent Task**: 方豆 "可以，去做吧" (iter_218 的换方法决定)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 工具落地 + 精确清单 (**未改任何被测代码**)

## 🎯 本次目标

`strict` 的移除用"正则批量删"已回退 **4 次** (iter_216/217/218)。根因是**形态没穷举**。
本轮按纪律换方法: 先写 **AST 驱动**的只读扫描工具, 输出精确清单 + 与 grep 对账。

## 🔬 实际结果

### 新增 `tools/scan_strict.py` (只读)

AST 分类统计 (`src` / `tools` / `sim/tests` / `run_cli.py`):
- **形参** (位置-only / 位置或关键字 / 关键字-only)
- **关键字实参** `strict=...`
- **位置实参** ⚠️ (按被调函数名 → `strict` 形参下标推算; **正则看不见**)
- **裸引用** `strict` / **属性** `self._strict`
最后与 `grep -c strict` 对账 (grep 含注释/docstring, 应为超集)。

### 清单 (当前批次 2 状态)

| 类别 | 数量 |
|---|---|
| 形参 | **22** |
| 关键字实参 | **160** |
| **位置实参 ⚠️** | **1** (`src/cli/commands/handshake.py:311` → `_scan_internal(...)` 第 5 个位置参数) |
| 裸引用 | **12** |
| `self._strict` | **7** |
| **合计** | **202 处 / 61 文件** |
| grep 对账 (行级) | 471 (含注释/字符串/docstring → 合理超集) |

Top 文件: `visualize.py`(21) / `trace.py`(15) / `handshake.py`(10) / `controlflow.py`(9) /
`randomize.py`(9) / `tools/coverage_gen_demo.py`(9) / `sv_extractor.py`(8) / `sva.py`(8) ...

## 💡 关键发现 / 关键技术 / 决策

1. **只有 1 处位置实参, 但它足以解释 iter_218**: `handshake.py:311` 用位置传 `strict`,
   删形参后位置**整体错位** (第 5 个参数变成别的值) → 该命令的链路静默出错 →
   上下游断言大面积失败。**正则方法的致命盲点就在这里** (关键字实参能匹配, 位置不能)。
2. **AST 计数 vs grep 行数的差值 (202 vs 471) 是"噪声地图"**: 差值主要是注释/docstring/
   帮助文本里的 `--no-strict` 字样 (不构成行为), 说明**不能按 grep 数字判断进度**。
3. **工具化比"更小心的正则"更划算**: 一次 30 分钟的投入, 换来后续 202 处改造的
   **可核对清单** (每改一类都能用同一工具复测: 数字必须下降, 且位置实参必须先清零)。

## 📢 下一步 (逐文件执行配方, 工具已就绪)

1. **先清位置实参**: 修 `handshake.py:311` (改成关键字/删参数) → 跑 handshake 相关测试;
2. **按文件逐个删形参 + 实参**, 顺序建议: `_common.py` → `_viz_common.py` →
   `_evidence_helpers.py` → 各 `commands/*.py` → `tools/*.py`;
   每文件改完: `python3 tools/scan_strict.py --summary` 复测数字 + 跑该文件相关用例;
3. **核心层 `src/trace`** (`self._strict` 7 处 + 语义分支) 单独立项:
   删 `self._strict` 意味着删除"返回 partial AST"的降级分支 → 行为变更, 需与批次 5 的
   fixture 修复一起验证;
4. 每批**全量门禁**通过 (或"失败集不变差") 才提交 —— 这条已写进教训。

## 📎 关联

- 工具: `tools/scan_strict.py`
- 前序失败: `iter_217` / `iter_218` (正则方法的 4 次回退)
