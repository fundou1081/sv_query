# L2 Task: Plan B Step B — Bit-Port Parent Emission

**Status**: ✅ CLOSED
**Parent**: L1_plan_b_real_project_visualization
**Closed**: 2026-08-25 (commit `6e8256c`)

---

## 🎯 Goal

Fix darkriscv ELK "Referenced shape does not exist: port_darkriscv_dot_DLEN" — bit-indexed ports (e.g. `DLEN[0/1/2]`) need parent-port emission.

## 📋 Outcome

✅ Commit `6e8256c` "feat(viz): [Plan B Step B1+B2+B3] bit-port parent emission + real-project test suite".
- Added B1 v3: emit parent-port when bit-indexed port is referenced
- Added real-project test suite (`sim/tests/integration/test_real_project_viz.py`)
- darkriscv ✅ (273KB DOT)