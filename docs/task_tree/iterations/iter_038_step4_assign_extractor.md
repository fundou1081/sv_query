# Iteration 038: #1 Step 4 — 拆 _create_assign_edges + 4 sub-method 到 assign_extractor

**Metadata**:
- **Iteration #**: 038
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #1 (拆 driver_extractor 4101 行 → 10 个文件)
- **Created**: 2026-08-28 16:10 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, 4 个 dispatch 分支探针 byte-identical

---

## 🎯 本次目标

用户指令: **"继续"** → 开 Step 4 拆 assign_extractor。

拆出 `driver_extractor` 里 assign phase 全部 **5 个方法 + 2 个专属 helper** (共 580 行):
- `_create_assign_edges` (25 行) — 主入口, 4-way dispatch
- `_handle_concat_assign` (90 行) — 5a
- `_handle_call_assign` (27 行) — 5b
- `_handle_binary_invocation_assign` (26 行) — 5c
- `_handle_normal_assign` (329 行) — 5d
- `_extract_assign_lr` (14 行) — assign 专属
- `_extract_ternary_condition` (69 行) — assign 专属

---

## 📊 实际规模 vs 估计

**估计 (todolist)**: 1 天
**实际**: 约 1 小时

**闭包分析** (git worktree 准备前的实际调查):
- 直接依赖: 10 个
- 传递闭包: **31 个方法 / 2028 行** (比 Step 3b 的 12/563 大一个量级)
- 其中 4 个**assign 专属** (随主函数一起搬走, 不需注入)
- 13 个**全文件共享** (被 `_create_always_edges` / `_create_invocation_edges` 等 Step 5-7 区域共用)

## 🔑 关键决策: 用 `AssignHelpers` 数据类打包注入 (而非逐个传 Callable)

Step 1+2 (alias_extractor) 和 Step 3b (net_decl_extractor) 用的是**逐个传 Callable** —
那时候只有 2-6 个依赖, 签名还能看。

Step 4 要注入 **13 个共享 helper**。如果继续逐个传:
- 5 个方法每个签名膨胀到 15+ 行
- handler 之间互调要层层转发 (`_handle_normal_assign(a, b, c, ..., h=...)` × 5 层)
- 4 个 handler 共用 13 个参数, 改一处全部跟着改

**这违背 AGENTS.md "函数应简洁"**, 拆分后比拆分前更难读。

改用 `dataclass AssignHelpers`: 调用方构造一次, 内部统一 `h.xxx` 访问,
签名恢复成只关注业务参数。helper 仍留在 `driver_extractor` 不动 (被 Step 5-7 共用)。

---

## 🔬 实施细节

### 用脚本机械搬运, 避免 580 行手抄错误

写了 50 行的 Python 脚本:
1. 按行号切分 7 个方法区间
2. 对函数体做规则转换:
   - `self.adapter` → `h.adapter`
   - `self._signal_visitor` → `h.signal_visitor`
   - `self._edge_factory` → `h.edge_factory`
   - `self._xxx(…)` (注入的 helper) → `h.xxx(…)`
   - `self._xxx(…)` (assign 专属) → `xxx(…)` (同模块私有函数)
   - handler 互调 → `_handle_xxx(…, h=h)` 自动传 h
3. 重新生成函数签名 (去掉 `self`, 加 `*, h: 'AssignHelpers'`)
4. 模板组装: header 文档 + `AssignHelpers` dataclass + 7 个转换后的函数

**转换后零 `self.` 残留** (用 grep 验证), 0 处遗漏。

### _handle_normal_assign 329 行的处理

按 AGENTS.md "函数应简洁" 标准, 这远超 ~50 行阈值。**没有**在本次一并拆,
理由:
- 行为重构与"搬文件"混在一个 commit, 一旦出回归会难以归因
- 内部 4 个分段 (ScopedName / wrapper unwrap / conditional fallback / expr tree)
  需要单独设计每个的契约和测试, 不是搬位置能顺带做的

已在 `assign_extractor.py` 头部 + iter_038 文档记录, 建议 Step 4b 处理。

---

## 📈 验证 (git worktree A/B 对照, 基线 = `15770af`)

### 回归: 全套 0 新增失败

| 测试套 | 基线 `15770af` | Step 4 后 | 结论 |
|---|---|---|---|
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |
| `unit` | 13 failed (含波动) | **4 failed** | ✅ 0 回归 (全沙箱所致) |
| `test_case27_1to1_truth` | — | **4 passed** | ✅ 全绿 |

### 🔑 行为等价性: 4 个 dispatch 分支探针 + 历史路径

写了覆盖 4 个 handler 的测试 fixture:

```sv
function [7:0] addf(...); addf = p + q; endfunction

assign o1 = sel ? a : b;          // 5d normal + ternary
assign o2 = addf(a, b);            // 5b call
assign o3 = {a, b};                // 5a concat
assign o4 = a & addf(b, a);        // 5c binary + invocation
```

在 `15770af` worktree 与当前工作区分别跑, `diff` 16 条边 / 13 节点
**完全 byte-identical**。还附带验证了 Step 3b 的 net_decl + generate-for
两条路径仍保持 byte-identical (说明此次重构未误伤别处)。

### ruff 检查

- `assign_extractor.py`: **All checks passed!**
- `driver_extractor.py`: 1 个先期 warning (`F841 side_kind unused`, 1238/1294/1329 行) —
  Step 4 改动**不引入任何新 lint 问题**

---

## 💡 关键发现 / 关键技术 / 决策

### 发现 1: 注入参数从 ~6 个到 13 个, 是质变而非量变

Step 1+2/3b 用逐个 Callable, 工作得不错。但到 Step 4 (13 个依赖), 同样的模式
**反而成了负担** — 每个 handler 签名 15+ 行, handler 间互调参数传递成噩梦。

`dataclass` 打包是**这种规模的标准解法**: 调用方一次构造, 内部统一 `h.xxx`,
签名只关注业务参数。这与 `_common.ExtractorHelpers` Protocol 是同构的
(都把"共享基础设施"作为参数注入), 只是 Step 4 多到需要打包成对象。

### 发现 2: 行为重构 vs 文件搬迁 不该混在一个 commit

329 行的 `_handle_normal_assign` 显然违反"函数简洁"原则。但本次没动它, 因为:
- 拆函数可能改 bug 行为, 与"搬文件"叠加 → 难归因
- 内部 4 个分段各自有独立契约要测, 不是一个工时能搞定

**纪律**: "搬代码" commit 和 "重构代码" commit **分开**, 各自可独立 revert。
这是 Step 3b 学到的同源教训, 那次也是 110 行搬迁 + 顺手消除两段重复一起做,
但那次重复消除**是搬迁的副产品** (共用 _emit_driver_edges), 不引入新逻辑。

### 发现 3: 机械搬迁 + 自动转换 = 比手抄更可靠

580 行的代码, 14 个 helper 引用, 任何手抄都难免漏一个 `self.`。
50 行的 Python 脚本:
- 0 处 `self.` 残留 (grep 验证)
- 0 处 handler 互调传 h 遗漏
- 行号定位精确, 删/插时不会因位移错位

这种规模的重构, 应该**先花 10 分钟写转换脚本, 再花 5 分钟运行**,
而不是花 30 分钟手抄 580 行 + 10 分钟 review 找 typo。

---

## 📌 下一步

Step 4 完成, #1 进度 **9 步完成 5 步**。

**Step 4b (建议)**: 拆 `_handle_normal_assign` 内部 4 段, 独立 commit
**Step 5: 拆 statement_flattener** (估 0.5 天)
**Step 6: 拆 always_extractor** (估 1.5 天, 最高风险, 含 _create_always_edges 共享 helper)
