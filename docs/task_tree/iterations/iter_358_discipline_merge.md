# Iteration 358: ub-mode 纪律合并 — 复杂度棘轮门禁 + 术语表（PLAN P57）

**Metadata**:
- **Iteration #**: 358
- **Task Tree Level**: L1（PLAN `P57`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "合并 ub-mode 与 sv_query 纪律，优中选优，最后我拍板"）
- **Outcome**: ✅ 完成（门禁 4 场景 e2e 通过 + 自检 9 passed + 全量回归通过）

## 🎯 本次目标

把 ub-mode 的开发纪律并入 sv_query 现有纪律，**优中选优**，落成三件可交付物：

1. **复杂度门禁** —— ub-mode "Reduce each function under CRAP 10" 的机械落地；
2. **术语表** —— ub-mode "Maintain a glossary of domain terms"；
3. **可撤销** —— 独立分支 + 未 push 的本地 commit。

方豆拍板的四条约束：适用于**所有**改动 / 必须有测试且有注释 / 改动须可撤销 / 需建立术语表。

## 📊 当前状态 / 预期结果

- ub-mode skill 已装（`~/.openclaw/workspace/skills/ub-mode/`），伴生工具 4 个已装于
  `~/my_skills/vendor/{crapper,dryer,mutator,uml-viewer}`；
- sv_query 已有 4 个检查器（check_docs / check_except_pass / check_cli_layers / gen_cli_surface），
  但**没有任何复杂度约束** —— 函数复杂度纯靠人自觉；
- sv_query 实测 1223 个函数，CC 中位 5 / p90 22 / max 142（`viz_to_elk`），CC>10 占 25.8%。

## 🔬 实际结果

### P57.1 复杂度棘轮门禁 `tools/check_crap.py`

**设计决策（为什么不用 `crapper --threshold`）**:

- `crapper --threshold` 仅在 CRAP 有值时生效；`--no-coverage` 下 CRAP 恒为 nil
  → threshold 永不触发 → 门禁**恒过**（静默失效，正是纪律禁止的）；
- 全树门禁在 sv_query 必红（CC>10 占 25.8%）→ 存量债会永久阻塞每次提交。

所以定为**棘轮 (ratchet)** —— 只拦"新引入 / 跨过阈值"的增长：

| 规则 | 条件 | 结果 |
|---|---|---|
| R1 | 新增函数 CC > threshold | 违规 |
| R2 | 已有函数从 ≤threshold 涨到 >threshold | 违规 |
| R3 | 存量本就 >threshold（即使上涨） | 只报告，不拦截 |
| R4 | 已有函数 CC 下降 | 不违规 |

退出码：`0` 通过 / `2` 有违规 / `3` crapper 未找到（**未执行 ≠ 通过**）。

**不变量 I3 单一实现原则**: crapper 是复杂度的**唯一实现**；本工具只做
**HEAD vs 当前**的增量比对，**不自己算复杂度**。

### 写作过程中实测抓出的 3 个真 bug（如实记录）

1. **`FileNotFoundError`** —— `analyze()` 读 `root/rel`，但当前版本从未 materialize 到
   临时目录 → 改为显式传入 `content` 并按**同一相对路径**落盘
   （namespace 由路径推导，路径一致才能比对）；
2. **假通过** —— `find_crapper()` 在 `CRAPPER_BIN` 指向不存在路径时**静默回退**到别处
   → 改为返回 `None` → 退出码 3（显式降级，不许当成通过）；
3. **baseline 恒空** —— `git_show()` 被拼了两次 `HEAD:` 前缀
   （`git show HEAD:HEAD:src/...` 必失败）→ **所有函数被当成"新增"**
   → 改为传纯路径。

第 3 个尤其危险：门禁看起来在工作，实际判定条件完全错了。

### P57.2 术语表 `docs/GLOSSARY.md`

四组归类：分层与能力 / 查询与分析 / 流程与门禁 / 工具与依赖。
含"棘轮 / CRAP / CC / 变异体 / 攻击前提 / 可撤销"等条目。

维护约定：已有术语的含义**只能澄清、不能改写**；别处有第二种说法时**改别处**，
不在术语表里加"也可能是"。

### P57.3 文档登记

| 文件 | 改动 |
|---|---|
| `docs/dev/CODING_STYLE.md` | 新增 §12 复杂度棘轮上限；§5 加指针 |
| `docs/dev/WORKFLOW.md` | §5 检查器表 4 → **5**，登记 `check_crap.py` + 退出码 3 语义 |
| `docs/dev/REVIEW_CHECKLIST.md` | §1 机械检查块加入 `check_crap.py` |
| `docs/dev/DISCIPLINE.md` | 不变量表后加术语表唯一命名处指针 |
| `AGENTS.md` | §3 提交前必跑加入 `check_crap.py` |
| `docs/INDEX.md` | 登记 `GLOSSARY.md` |
| `PLAN.md` | 新增 P57 计划组（4 个子项） |
| `CURRENT_TODO.md` | 当前 item → P57.3；门禁块加入 `check_crap.py` |
| `.gitignore` | 忽略 `.metrics/`（crapper/dryer/mutator 产物） |

## 🧪 测试

- **纯逻辑层** `sim/tests/unit/test_discipline_check_crap.py` —— 9 passed；
- **真实 e2e**（临时 git 仓库 + 真 crapper）四场景全对：
  - 无改动 → exit 0；
  - 新增高 CC 函数 → exit 2「新增函数 CC=21 > 阈值 10」；
  - 已有函数跨阈值 → exit 2「复杂度从 1 涨到 15, 跨过阈值 10」；
  - 存量本就超阈值且上涨 → 只报告，exit 0；
- **退出码复核**: 正常 0 / 违规 2 / `CRAPPER_BIN` 指向不存在路径 → **3**。
- **全量回归**: **2734 passed / 0 failed** (7 skipped / 152 deselected, 35 subtests)，340.89s。
  基线 2725 → 2734 (+9 = 本次新增的 9 个自检)，0 failed。

### 测试自身的 bug（如实记录）

首次跑 pytest **2 项失败**。根因在**测试自身**而非被测代码：辅助函数 `_v(ns, fn, cc)`
返回 `((ns,fn), cc)`，再被用作 `{_v(...): 13}` 的 key → dict 键变成嵌套元组，
`compare()` 解包出 `ns=("a","fn"), name=13`。
修法：拆成 `_k(ns, fn)` 只产出比对键。**不是**改被测代码去迁就测试。

## 💡 关键发现 / 决策

| 项 | 决策 |
|---|---|
| 门禁形态 | 棘轮（R1~R4），非全树 |
| 阈值 | CC > 10 |
| 复杂度实现 | 只有 crapper（不变量 I3） |
| crapper 缺失 | exit 3，显式降级，**不等于通过** |
| 进 CI | **暂不进** —— crapper 需 `tree-sitter` + `tree-sitter-language-pack`，CI 装它会拖慢且引入新失败面 |
| 可撤销手段 | 独立分支 + 未 push 的本地 commit |

## ⚠️ 边界

- 门禁只看 `git status` 里**新增/修改的** `src/**/*.py`（与 check_except_pass 同范围），
  **已提交但未 push 的改动不在范围内** —— 这是增量比对的固有边界，已在脚本 docstring 写明；
- 门禁**不拦存量**（R3），因此存量高 CC 函数仍需人工重构；
- 重复度 (dryer) / 变异体存活率 (mutator) **暂不设门禁** —— ub-mode 有，但本轮只做复杂度
  （一次只加一个门禁，便于定位失败原因）；
- CI 未接入门禁（见上表）。

## 🔗 相关

- 计划: [PLAN.md P57](../../../PLAN.md)
- 术语表: [docs/GLOSSARY.md](../../../docs/GLOSSARY.md)
- 纪律: [docs/dev/CODING_STYLE.md §12](../../../docs/dev/CODING_STYLE.md)
- 门禁脚本: [tools/check_crap.py](../../../tools/check_crap.py)
