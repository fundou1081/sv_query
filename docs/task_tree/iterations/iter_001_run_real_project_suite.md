# Iteration 1: Run Real-Project Test Suite

**Metadata**:
- **Iteration #**: 1
- **Task Tree Level**: L3
- **Parent Task**: L3_understand_bug_class
- **Created**: 2026-08-25 16:00 GMT+8
- **Author**: 方豆 / QClaw

---

## 🎯 Current Goal

Run the real-project integration test suite (`sim/tests/integration/test_real_project_viz.py`) to identify which projects work and which fail.

## 📋 Expected Result

All 5 listed real projects should produce SVG (or be properly skipped):
- darkriscv (273KB expected)
- picorv32 (full picorv32.v with target=picorv32_core)
- serv (may skip due to filelist)
- neorv32 (may skip due to complex filelist)
- zipcpu (may skip due to large module)

## 🔬 Actual Result / Observation

```
darkriscv ✅ PASS (273KB DOT)
picorv32 ❌ FAIL — RecursionError
serv ✅ PASS (8.5KB DOT) — actually ran despite being marked skip
neorv32 (skipped)
zipcpu (skipped)
```

**Key finding**: picorv32 fails with `RecursionError: maximum recursion depth exceeded`. Initial hypothesis (WRONG): "picorv32 ALU has 2000 layers of intermediate wire chains".

## 💡 Other Valuable Info

- Real-project test suite was created in commit `6e8256c` (Plan B Step B3)
- The test only checks 1 module per project (target module param)
- serv being skipped but actually working — should investigate why skip
- Initial "2000 layers" hypothesis was **wrong** — only had 5 wires (proven later in iteration 3)

## 🔄 Next Action

Run picorv32 with different sub-targets to identify which sub-module triggers RecursionError.