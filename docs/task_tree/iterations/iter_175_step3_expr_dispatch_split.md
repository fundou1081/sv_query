# Iteration 175: Step 3 — 拆 474 行 `_extract_signals_from_expr`

**Metadata**:
- **Iteration #**: 175
- **Task Tree Level**: L1
- **Parent Task**: L1_adapter_split
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (474 → 70 行分派器 + 16 处理器; 顺带修 1 latent bug)

## 🎯 本次目标

方案 Step 3: 拆 `_extract_signals_from_expr` (474 行, 13 处外部调用) —
行为不变, 由 API 冻结测试 + 表达式/驱动/truth 套件保护。

## 🔬 实际结果

**结构 (实测)**: 函数 = 20 个并列 `if` 分支 (kind 子串分派) + 方法级 `return signals`;
其中 **2 个条件是重复的** (`Conversion` ×2, `ConditionalOp/ConditionalExpression` ×2)。
核对可达性: 前一处两分支均以**分支级 `return signals` 收尾** → 后一处**不可达 (死代码)**。

**顺带发现 latent bug**: `_fold_sel` (iter_118 genvar 索引折叠) 定义在**死分支体内**,
却被活分支 (ElementSelect/RangeSelect 的非常量 selector 路径) 调用 — Python 帧
局部作用域下该路径必然 `UnboundLocalError`。Step 3 提到模块级
(`_fold_select_index(sel, ctx)`) 后变得可达/可测 → **行为修复** (原路径崩溃 → 正常折叠),
已在迭代记录 + 测试中明示 (新增 6 个直接单测)。

**重构做法 (脚本化 + 逐步验证)**:
- 16 个 kind 分支体原样搬到模块级纯函数 `_expr_<kind>(adapter, expr, ctx)` (body dedent 8,
  `self.` → `adapter.`); 分派器保留原 if-chain 顺序与出口语义 (分支级 return → `return handler(...)`;
  fall-through → `signals.extend(handler(...))`) — **控制流逐一保持**
- 删除 2 个不可达分支; `_fold_select_index` 提升 (3 处调用点补 ctx 参数)
- 方法保留 `return signals` 兜底 (未覆盖 kind → 空列表; 拆分首版曾漏掉, 被 replication
  套件 17 失败 + 13 error 立刻抓出 → 补回)

**结果**: `_extract_signals_from_expr` **474 → 70 行**; 文件 3049 → 3036 行;
16 个处理器 + 1 个 helper 位于文件末尾 (含 Step 4-9 mixin 搬迁的天然分组)。

**验证 (Step 3 gate)**:
| gate | 结果 |
|---|---|
| unit + regression + truth | **2,243 passed** (含新增 15 个 helper 单测) |
| cli + integration | **739 passed / 0 failed** |
| API 面冻结 | ✅ 65 方法/签名/property 完全一致 |
| 中途回归 | 首版漏末尾 `return signals` → 17 failed + 13 errors, **已修复并复跑全绿** |

## 💡 关键发现 / 决策

- **"行为不变" 必须有机械证据**: API 冻结测试 + 计数基线让"17 failed"在 1 分钟内被定位到
  单行 (末 return) — 若没有安全网, 这种 474 行脚本化搬迁很难收敛。
- **死代码里常藏着活 bug**: 两个不可达分支之外, 死分支内的嵌套 def 被活路径调用 =
  latent UnboundLocalError。拆分把不可见依赖暴露成显式模块级函数。
- **脚本化重构的坑**: ① 缩进 dedent 要按**原始层级**算 (12→4 而非 12→8);
  ② 末尾分支切片会吞掉方法级兜底语句; ③ 断言别用子串判定改名结果
  (`_fold_select_index` 含 `_fold_sel` 子串 → 假阳性)。三条都在本迭代踩到并修正。
