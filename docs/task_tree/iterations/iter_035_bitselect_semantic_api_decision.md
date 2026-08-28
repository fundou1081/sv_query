# Iteration 035: BitSelect G3 决策确认 (选项 3 semantic API) + WIP 状态核实

**Metadata**:
- **Iteration #**: 035
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #2 (统一 BitSelectHandler)
- **Created**: 2026-08-28 07:46 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ⚠️ **部分完成** — 决策已确认归档, 但实现未完成、未提交, 且发现纪律违规

---

## 🎯 本次目标

用户指令 (2026-08-28 07:46): **"选择 semantic api 。"**

即 `BITSELECT_HANDLER_G2_PLAN.md` G3 的**选项 3**: 用 pyslang API 替代 regex (治本方案)。

前置背景: 上一轮对话中, 我 (DSH Agent) 主动指出 "两套实现全 regex" 与项目
2026-08-15 "pure semantic API" 方向矛盾, 并按 `AGENTS.md` "新决策与旧决策冲突 → 停下来问"
把决策权交回方豆。本次是方豆的答复。

---

## 📊 当前状态 / 预期结果

**预期**: 确认选项 3, 然后开始实施 (预计 1-2 天)。

**开工时实际状态 (探索后发现, 与预期不符)**:

`git status` 显示存在**未提交的 WIP**:
```
 M src/trace/core/extractors/_common.py       (+492 行)
 M src/trace/core/graph_builder.py            (+145 行)
 M sim/tests/integration/test_bitselect_handler_diff.py
?? sim/tests/unit/test_common_bit_selects.py  (未跟踪)
```

读代码发现 `_common.py:374-387` 注释明确记载:
> 用户指令 [2026-08-28 06:36]: "走 g3 的 3" (用 pyslang API 替代 regex, 治本)

**即: 方豆 1 小时前已下过同一指令, 前一 session 已开工但未完成、未提交、未记录。**

---

## 🔬 实际结果

### 1. 决策已归档

新建 `docs/architecture/bitselect_semantic_api_decision.md`, 含时间 / 问题 / 5 个方案对比 /
决策结果 / 利弊权衡 (按 `AGENTS.md` 架构决策必备字段)。

### 2. WIP 功能性核实 (实测, 非推测)

| 测试 | 结果 |
|---|---|
| `test_common_bit_selects.py` + `test_bitselect_handler_diff.py` | **12 passed, 1 failed** |
| 唯一失败 `test_nested_diff` | fixture `data[3:0][1:0]` **SV 语法非法**, pyslang 报 `SelectAfterRangeSelect` — 非新代码缺陷 |
| `test_case27_1to1_truth.py` | ✅ **4 passed** |

### 3. 回归对比 (关键: 用 git stash 做了真实 A/B 对照)

| 版本 | 结果 |
|---|---|
| **带 WIP** | 33 failed, 1422 passed |
| **stash 后 (干净 HEAD)** | 33 failed, 1417 passed |

**结论: 33 个失败在 HEAD 上同样存在, WIP 引入 0 回归。**

### 4. 33 个失败的根因 (诊断到底, 未止步于"预先存在")

```
AssertionError: 1 != 0 : Error: [Errno 1] Operation not permitted:
  '/Users/fundou/.svq/cache/a98ed4f3b51ee3fa.json'
```

`src/trace/core/cache/ast_cache.py:30` — `CACHE_DIR = Path.home() / ".svq" / "cache"`

`~/.svq/cache` 在**我的 workspace-write 沙箱之外**, 实测 `touch` 被拒。
**这是我的执行环境限制, 不是项目代码缺陷** — 方豆本地跑应当正常。

---

## 💡 关键发现 / 关键技术 / 决策

### 🔴 发现 1: WIP 里存在 silent fallback — 违反 AGENTS.md 核心纪律 #2

`src/trace/core/extractors/_common.py:440-441`:
```python
if not _HAS_PYSLANG:
    return  # 退化: 让调用方走 regex 老路径
```
`_common.py:397` 同样写着 "调用方在没 pyslang 时直接走 regex 老路径"。

这正是 `AGENTS.md` **核心纪律 #2 "禁止 fallback 模式"** 明令禁止的
"primary 失败就 secondary path" 静默退化。讽刺的是: 本次改造的**目的**就是消除 regex,
而实现却内置了一条 "回到 regex" 的静默退路。

**应改为**: 显式 raise 或返回 sentinel + WARNING (参考 `coverage_generator.py` 的 `NO_TREE_MARKER`)。

### 🔴 发现 2: regex 债只清了一半

WIP 只改造了**路径 B** (`graph_builder._create_hierarchical_bit_nodes`)。
**路径 A** (`src/trace/core/bit_select_handler.py:290`) 仍是原样 regex。
选项 3 的目标是两套都改, 当前状态未达成。

### ⚠️ 发现 3: 前一 session 违反了"任务前后必须更新文档"

06:36 接到指令后开工, 但:
- ❌ 没建 task 文件, 没写 iteration 记录
- ❌ `ARCHITECTURE_TODOLIST.md` #2 仍写 "G3 待决策", 与实际"已决策并开工"不符
- ❌ 代码未提交

这恰好印证了方豆本轮新增的纪律 (`AGENTS.md` v1.3): **文档更新和实际工作同等重要**。
若无本次核实, 下一 session 会以为 #2 还停在"等决策", 可能重复开工或误删 WIP。

### 技术事实 (实测确认)

- `RangeSelectExpression`: `.left.value` / `.right.value`
- `ElementSelectExpression`: `.selector.value`
- `root.visit(callback)` — callback 返回 `True`/`False` 控制深入
- parameter 位选经 `eval(EvalContext)` 可得真实整数

---

## 🔄 补充核实 (2026-08-28 07:50, 方豆要求"再检查一下当前任务状态")

### 🔴 重大更正: 之前 "0 回归" 的结论是**错的**

07:46 我用 `sim/tests/unit + cli` 做 A/B 对照, 得出 "WIP 引入 0 回归"。
**但我没跑 `sim/tests/integration/`** — 而回归恰恰全在那里。这是我的**覆盖面失误**。

期间另一 agent (QClaw) 并行完成了 G3 实现并产出 `docs/BITSELECT_HANDLER_G3_OPTION3_REPORT.md`,
报告 8 个 regression。**我重新用 git stash 做了 integration 的 A/B 对照**:

| 测试套 | 带 WIP | 干净 HEAD | 净引入 |
|---|---|---|---|
| `sim/tests/unit` | 13 failed | 13 failed | ✅ **0** |
| `sim/tests/integration` | **25 failed** | **16 failed** | 🔴 **9** |
| `test_case27_1to1_truth.py` | 4 passed | — | ✅ 全绿 |

**实测净引入 9 个回归** (QClaw 报 8, 实际 9 — 多一个 `prim_arbiter-dataflow_analyze`):
```
test_advanced_grammar.py::TestForLoopExtraction::test_for_loop_in_always
test_advanced_grammar.py::TestForLoopExtraction::test_generate_for
test_cdc_risk_open_source.py::test_golden_risk_strict_uart
test_subfunction_golden_open_source.py[prim_arbiter-dataflow_analyze]
test_subfunction_golden_open_source.py[prim_arbiter-sva_coverage]
test_subfunction_golden_open_source.py[strict_uart-risk_analyze]
test_subfunction_golden_open_source.py[strict_uart-stats]
test_subfunction_golden_open_source.py[strict_uart-sva_coverage]
test_subfunction_golden_open_source.py[strict_uart-timing_analyze]
```

### 🔴 更正 2: QClaw "全部是 golden 比对差异" 的判断**不成立**

QClaw 报告 §Regression 根因 称 "全部 8 个 regression 都是 golden file 对比测试",
并据此建议 **选项 A: 重新生成 golden**。**实测推翻**:

```
test_for_loop_in_always:
  AssertionError: 0 != 1 : always_ff q[i] <= data[i] 应有 1 个驱动源 (data)

test_generate_for:
  AssertionError: 0 != 1 : generate for out[i] = clk 应有 1 个驱动源 (clk)
```

这两个**不是 golden 文件比对**, 是**功能断言**: 驱动源从 1 个变成 **0 个**。
即 for-loop / generate-for 内的位选驱动关系**被 G3 改动弄丢了**。

`test_golden_risk_strict_uart` 也显示风险项 **total 25 → 28** (多出 3 项), 方向可疑。

**若按 QClaw 建议直接重新生成 golden, 会把 "驱动源丢失" 这个真 bug 固化成新 baseline** —
这正是 `AGENTS.md` 禁止的 "为通过而改 assertion/golden"。

### 结论

G3 选项 3 **主目标达成** (RangeSelect 4 属性齐 / struct 3 条边对齐 / regex 消除),
但**引入了真实功能回归**, 尚不可提交。

---

## 📌 下一步 (未做, 等方豆确认)

1. 🔴 **最高优先: 查 for-loop / generate-for 驱动源丢失** — `test_for_loop_in_always` /
   `test_generate_for` 驱动数 1 → 0, 是真 bug, **不可用重新生成 golden 掩盖**
2. **修 silent fallback** (`_common.py:441`) — 纪律硬伤
3. **改造路径 A** (`bit_select_handler.py:290`) — 仍是 regex, 选项 3 只完成一半
4. **清理** `graph_builder.py:442` 残留 `import re`
5. 待 1-4 完成后再评估: 剩余 golden 差异是否属"新 ground truth", 才谈重新生成
6. 全套回归 + 提交 (代码与文档同一 commit)

**本次未提交任何代码改动** — 仅新增/更新决策记录与本迭代记录。
