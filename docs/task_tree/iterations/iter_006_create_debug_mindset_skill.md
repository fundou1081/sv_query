# Iteration 6: Create Debug Mindset Skill

**Metadata**:
- **Iteration #**: 6
- **Task Tree Level**: L1
- **Parent Task**: L1_plan_b_real_project_visualization (cross-cutting)
- **Created**: 2026-08-25 22:17 GMT+8
- **Author**: 方豆 / QClaw

---

## 🎯 Current Goal

User request: "最好能做到，以后这样的debug问题，能自由的做到思路转换。一些常识性的问题，或者说直觉。在什么情况下深入调查，什么情况下切换思路，主要把这个记录下来。形成一些技能。写入文档"

Create a reusable skill that captures debug intuitions from tonight's session.

## 📋 Expected Result

- Skill Workshop proposal: 5 debugging modes + switch rules + anti-patterns
- Project doc: `docs/debugging_lessons/debug-mindset-skill.md`
- DOC_INDEX.md updated
- Commit

## 🔬 Actual Result / Observation

✅ All deliverables:
- Skill proposal `debug-mindset-switcher-20260825-599314c1db` (pending)
- `docs/debugging_lessons/debug-mindset-skill.md` (8505 bytes, 362 lines) — comprehensive
- DOC_INDEX.md updated to reference new skill doc
- Commit `50620e6` "docs(debugging_lessons): add debug mindset skill (5 modes + switch rules)"

5 modes defined:
1. Verify Assumption (default first)
2. Trace Evidence (when hypothesis fails)
3. Prototype Fix (when root cause clear)
4. Test Real (after fix)
5. Write Down (always available)

## 💡 Other Valuable Info

- Skill applied directly in this session — caught Mode 1 → Mode 2 → Mode 3 → Mode 5 transitions
- Switch trigger table is the most actionable part — encodes "when to leave each mode"

## 🔄 Next Action

User asks: "好的，那么继续 调查 plan b 的step g" — start Plan B Step G investigation.