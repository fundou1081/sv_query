# Debug Mindset Skill — 调试思路切换技能

> **TL;DR**: 调试最大的时间浪费是**停留在错误的思维模式里**。这个文档定义 **5 种调试模式 + 触发切换规则**, 让你在 debug 时自由切换思路, 不再陷入"假设-失败-再假设"的死循环.

**来源**: 2026-08-25 picorv32 render_tree RecursionError 3.5h 调试 session (commit `a939d68` + `9eab9ed`).

**配套 Skill Workshop proposal**: `debug-mindset-switcher` (pending, 可以 apply / reject / quarantine).

---

## 🎯 为什么需要这个 Skill

真实调试案例: 一个 3.5h 的 RecursionError 修复, 实际应该 30min 内完成.

| 时间 | 思维模式 | 实际做的 | 应该做的 |
|------|----------|----------|----------|
| 0:00 - 1:30 | **假设模式** (错误) | "2000 层 wire" — 基于 RecursionError 数字 | 应该 **验证假设** — 检查实际源码 |
| 1:30 - 1:50 | **验证假设** (用户挑战后) | `grep -c wire` → 只有 5 个 wire | 用户说 "为什么 2000 层?" → 触发验证模式 |
| 2:00 - 3:00 | **原型修复** (错误方向) | Fix #1, #2, #3 — 全基于错误假设 | 应该 **追踪证据** — 读 traceback 帧分布 |
| 3:30 - 4:00 | **追踪证据** (突破) | 帧分析 → matched_tree 递归形成环 | 找到真因 |
| 4:00 - 4:15 | **测试真实项目** | Fix #4 v3 → picorv32 PASS | 验证 |
| 4:15 - end | **写下来** | docs/debugging_lessons/ | 未来参考 |

**核心教训**: 1.5h 浪费在停留在"假设模式", 直到用户挑战才切换到"验证假设"模式. 如果一开始就按这个 skill 操作, 1.5h 可以省下.

---

## 🧠 5 种调试模式

### 模式 1: VERIFY ASSUMPTION (验证假设) — 默认首选

**进入触发**: 任何时候你对"为什么失败"有假设时.

**做什么**:
1. **显式陈述假设**: "我认为 X 是因为 Y"
2. **找 DISPROVING evidence** (不是 confirming)
3. 如果证据不符 → 切换到模式 2 (追踪证据)
4. 如果证据符合 → 进入模式 3 (原型修复)

**诊断问题**:
- "源码中什么能证明我错了?"
- "我真的看了代码, 还是从 error 信息推断的?"
- "error 信息里的哪个数字, 我没验证就信了?"

**具体行动**:
```bash
wc -l <file>           # 实际文件大小
grep -c "wire\|assign" <file>   # 实际结构数量
head -50 <file>        # 实际代码长啥样
# 读 error 函数的前 10 行
```

**退出触发**:
- 证据证明假设 → 进入模式 3
- 证据反驳假设 → 进入模式 2
- 30min 没进展 → 进入模式 4 (测试真实项目)

### 模式 2: TRACE EVIDENCE (追踪证据) — 假设失败时

**进入触发**: 假设被反驳, 或者根本无假设.

**做什么**:
1. **拿 FULL traceback** (不只是最后几帧)
2. **数 frame 出现次数**: `Counter([frame_line for frame in traceback])`
3. **找出现最多的那一行** — 通常是递归点
4. **逆向追溯**: 谁调用了它? 传了什么?
5. **对 RecursionError 特别检查**:
   - 同样的行反复出现在栈里? (→ cycle)
   - 最深的帧之上的那一帧? (→ 根调用)
   - 每帧之间什么参数在变化? (→ 递归变量)

**诊断问题**:
- "递归是单函数, 还是跨函数?"
- "每帧之间什么 SAME?"
- "什么在 CHANGING? 最终能到 base case 吗?"

**具体行动**:
```python
import traceback
traceback.format_stack()
Counter(...)

# 让递归早点失败, 看 top frames
sys.setrecursionlimit(150)

# 在可疑函数加日志
print(f"depth={_depth}, label={label}")
```

**退出触发**:
- 根因明确 → 进入模式 3
- 帧分散到多个函数 → 进入模式 4
- 60min 没清晰模式 → 进入模式 5 (你已经学到够多了, 写下来)

### 模式 3: PROTOTYPE FIX (原型修复) — 根因明确时

**进入触发**: 假设验证过, 或者追踪证据清晰.

**做什么**:
1. **写最小修复**, 只针对根因
2. **立即测试**
3. 修复工作 → commit + 进入模式 4
4. 修复破坏其他东西 → revert, 进入模式 2 with 新信息

**诊断问题**:
- "这个修的是 ROOT CAUSE 还是 SYMPTOM?"
- "能 fix bug 的最小改动是什么?"
- "如果这个修复 work, 我能从根因分析预见到吗?"

**反模式**:
- ❌ "让我连试多个 fix" — 每个不测试的 fix 都是浪费
- ❌ "顺便修下类似 bug" — scope creep, 破坏稳定性
- ❌ "顺便加 tests" — 不在 fix commit, 单独 commit

**具体行动**:
```bash
git checkout <file>     # 干净起点
# apply ONE fix
pytest golden regression
pytest real project
# pass → commit, fail → git checkout, 模式 2
```

**退出触发**:
- 修复 work + 没 regression → 进入模式 4 (用更多 case 测)
- 修复破坏东西 → revert, 模式 2
- 3+ 修复尝试失败 → 模式 5 (需要新视角)

### 模式 4: TEST REAL (测试真实项目) — 修复后或找 bug

**进入触发**: 有 working fix 要验证, OR 完全没假设, 想找哪些 case 失败.

**做什么**:
1. **跑失败的 case + 相邻 case**
2. **跑 golden regression** (无 regression)
3. Fix pass 真实 case → done
4. Fix 破坏 golden → revert, 模式 2

**诊断问题**:
- "我测了 EXACT 失败的 case, 还是相似的?"
- "我测了不同方式触发同一 code path 的 case?"
- "我测了 BEFORE fix (确认基线) 和 AFTER (确认 fix)?"

**具体行动**:
```bash
# 跑 picorv32 不同子模块
pytest picorv32_pcpi_mul picorv32_pcpi_div picorv32_axi picorv32_wb picorv32_regs
# 跑其他开源
pytest darkriscv serv zipbones
# golden regression
pytest sim/tests/unit/test_visualize_module_golden.py
# integration
pytest sim/tests/integration/
```

**退出触发**:
- Fix 通过真实 case + 无 golden regression → DONE
- Fix 在测试 case 通过但破坏其他 → 模式 2 (根因更广)
- 真实 case 揭示 NEW bug → 模式 2 with 新 bug context

### 模式 5: WRITE DOWN (写下来) — 永远可用, 经常用

**进入触发**: 找到值得记的 bug, OR 卡 >2h.

**做什么**:
1. **Document BUG**: 失败的现象, 错误信息, stack
2. **Document ROOT CAUSE**: 实际哪里错了
3. **Document PROCESS**: 走了哪些模式, 时间花在哪
4. **Document FIX**: 改了什么 code, 为什么 work
5. **Document LESSON**: 下次会做什么不同

**诊断问题**:
- "如果 6 个月后我忘了所有, 看什么能记起来?"
- "我浪费时间在什么上, 应该跳过?"
- "我在哪个模式停太久?"

**具体行动**:
```bash
# 创建文档
docs/debugging_lessons/<date>_<bug-name>.md
# 更新索引
docs/DOC_INDEX.md (+引用)
# 更新 memory
MEMORY.md (+摘要 + 链接)
memory/<date>.md (daily note)
```

**退出触发**:
- 文档写完 → 回到模式 1 with 新视角 (写文档过程常常 reveal 真问题!)

---

## 🔀 切换规则 — 什么时候切换

### 硬规则 (Always Follow)

| 当前模式 | 触发 | 切换到 |
|----------|------|--------|
| **假设** | 用户问 "为什么 X?" 或 "X 对吗?" | 验证假设 |
| **假设** | 30min 没进展 | 验证假设 (或追踪证据 if 无假设) |
| **验证假设** | 源码反驳假设 | 追踪证据 |
| **验证假设** | 30min 没找到证据 | 测试真实项目 (找失败 case) |
| **追踪证据** | 根因明确 | 原型修复 |
| **追踪证据** | 60min 没清晰模式 | 写下来 (已经学到够多了) |
| **原型修复** | 3 次失败 | 写下来 + reset |
| **原型修复** | Fix 破坏 golden regression | 追踪证据 (更广的问题) |
| **测试真实项目** | 发现 NEW bug | 验证假设 (新 bug) |
| **测试真实项目** | Fix 通过一切 | DONE |
| **写下来** | 文档 reveal 新洞察 | 验证假设 (新视角) |

### 软规则 (用判断)

- **用户质疑 = 立即切换**: 用户问 "为什么 X?" 或 "这个对吗?" → 立即切换到 **验证假设** 模式.
- **卡 >1h = 强制切换**: 任何模式卡 >1h → 切换到 **写下来** (需要新视角).
- **多次修复尝试 = 撤退**: 3+ failed fix → 写下来 + git checkout + 用 **追踪证据** 重新开始.

---

## ⚠️ 反模式 (Things to Avoid)

### 反模式 1: "Trust Error Numbers"
❌ "RecursionError depth=5000 意味着有 5000 层"
✅ Depth=5000 只是说它崩了. 真实结构可能是 5 个 wire 形成 cycle.

### 反模式 2: "Fix Multiple Hypotheses Simultaneously"
❌ "让我同时加 cycle detection + depth limit + cache"
✅ 一次一个 fix. Fix #1 不 work, revert, 试 Fix #2.

### 反模式 3: "Commit Before Real-Project Test"
❌ "Tests pass, ship it!" (只跑 golden tests)
✅ 测真实项目 (darkriscv, picorv32 等) — golden tests 漏真 bug.

### 反模式 4: "Skip Write Down"
❌ "Bug 修了, 继续, 不用记"
✅ 写下来花 30min, 省 3h 下次.

### 反模式 5: "Single Mode Tunnel Vision"
❌ 在 **假设模式** 待 3h, 试图让假设 work
✅ 触发 fired 就切换. 用户质疑是 feature, 不是打断.

---

## ✅ 切换前诊断 Checklist

切换模式前, 问自己:

1. **我现在在哪个模式?** (诚实: 我在假设还是在真的验证?)
2. **什么 evidence 让我留在这个模式?** (具体数据, 不是感觉)
3. **什么会让我切换?** (具体触发或阈值)
4. **切换的成本是什么?** (revert 时间, 心智 context 丢失)
5. **切换成本 < 留下的成本吗?** (是 → 切换)

---

## 📚 实战案例: RecursionError Debug

**Setup**: `RecursionError: maximum recursion depth exceeded`

**Hour 0-1:30 (WRONG — 假设模式)**:
- 看 error: "depth exceeded"
- 假设: "肯定有 2000 层 wires"
- 留在假设模式: "我给 render_tree 加 max-depth limit"
- ❌ 从未质疑假设

**Hour 1:30 (SWITCH TRIGGER: 用户质疑)**:
- 用户: "为什么 2000 层?"
- → 切换到 **验证假设** 模式

**Hour 1:30-2:00 (验证假设)**:
- `grep -c "wire" picorv32_pcpi_mul.sv` → 5
- `wc -l picorv32_pcpi_mul.sv` → 119
- 假设被反驳
- → 切换到 **追踪证据** 模式

**Hour 2:00-3:30 (追踪证据)**:
- 拿 full traceback
- 帧计数分析: 最多帧在 `_safe()` 和 `render_tree()`
- 发现 matched_tree 递归在 line 684
- 检查 `_signal_cache` 设计: read-only, 不能 break cycle
- → 切换到 **原型修复** 模式 (根因明确)

**Hour 3:30-4:15 (原型修复)**:
- Fix #4 v3: `_being_rendered` set + try/finally + op_id = None
- 测 picorv32_pcpi_mul → PASS
- → 切换到 **测试真实项目** 模式

**Hour 4:15-4:30 (测试真实项目)**:
- 跑 golden regression → 5/5 PASS
- 跑 darkriscv/serv/zipbones → 全 PASS
- → DONE

**Hour 4:30-5:00 (写下来)**:
- 创建 `docs/debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md`
- 更新 MEMORY.md
- 更新 DOC_INDEX.md
- → 未来参考 ready

---

## 🚦 Quick Reference: 模式触发

```
USER ASKS "WHY X?"   → 验证假设
STUCK >30MIN        → 验证 或 测试真实
STUCK >1H           → 写下来
3 FAILED FIXES      → 写下来 + reset
SOURCE DISPROVES    → 追踪证据
NEW BUG FOUND       → 验证假设 (新 bug)
GOLDEN REGRESSION   → revert, 追踪证据
FIX PASSES REAL     → DONE
```

---

## 🧩 Integration

### 何时自动应用

这个 skill 设计成在以下情况**自动应用**:
- 调试 session >30min
- 用户质疑你的假设
- 多次 fix 失败
- 出现 RecursionError / cycle / cache bug

### 与其他 skill 的关系

- **skill-creator** — 创建 skill 的 meta-skill
- **critical-thinking-framework** — 6 问分析 claims
- **consulting-methods-toolkit** — 结构化问题解决框架

### Skill Workshop Status

Pending proposal: `debug-mindset-switcher-20260825-599314c1db`

Apply 时机:
- ✅ 当你意识到卡在错误模式时
- ✅ 当用户明确要求时 (e.g. "应用 debug mindset skill")
- ❌ 不要 uncritically apply — skill 是 thinking aid, 不是 automation

---

## 🏷️ Tags

`#debugging` `#meta-skill` `#mindset` `#root-cause-analysis` `#cycle-detection` `#recursion-error` `#thinking-modes` `#sv_query`

---

## 📎 相关文档

- 案例: `docs/debugging_lessons/2026-08-25_picorv32_render_tree_cycle.md`
- 修复 commit: `a939d68` (feat(viz): [Plan B Step F] cycle detection + expression_tree cleanup)
- 文档 commit: `9eab9ed` (docs(debugging_lessons): add picorv32 render_tree cycle case study + index update)

---

**作者注**: 这个 skill 来自 3.5h debug session, 我在 **假设模式** 卡了 1.5h, 用户不得不手动质疑才触发切换. 5 个模式 + 触发表设计目的: 防止这类 stuckness 再发生.

下次遇到 RecursionError / cycle bug:
1. **先** 验证假设 (看实际代码, 不信 error 数字)
2. **再** 追踪证据 (traceback 帧分布, frame count)
3. **然后** 原型修复 (一次一个 fix, 测了再 commit)
4. **最后** 写下来 (未来自己会感谢现在的你)