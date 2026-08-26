# Task Tree Overview — sv_query Project Debug & Development

> **Purpose**: Global view of all ongoing/closed tasks in sv_query project. Each L1 task has its own file under `tasks/`. Each iteration has its own file under `iterations/`.
>
> **Workflow**: One iteration = one observable action (read code, run test, fix bug, etc.). Each iteration file captures goal, expected result, actual result, and other valuable info.
>
> **Setup**: 2026-08-25 23:48 GMT+8 by 方豆 / QClaw (per user instruction)

---

## 🌳 Task Tree (Current State)

```
sv_query_project/
└── L1: Plan_B_Real_Project_Visualization/  [ACTIVE, 🔴 BLOCKED on G]
    ├── L2: Plan_B_Step_A/  [CLOSED ✅, commit 915c284 等]
    ├── L2: Plan_B_Step_B/  [CLOSED ✅, commit 6e8256c, bit-port parent emission]
    ├── L2: Plan_B_Step_C+D/  [CLOSED ✅, commit 8e98abd]
    ├── L2: Plan_B_Step_E/  [CLOSED ✅, sys.setrecursionlimit workaround]
    ├── L2: Plan_B_Step_F/  [CLOSED ✅, commit a939d68, cycle detection for picorv32_pcpi_mul]
    └── L2: Plan_B_Step_G/  [✅ CLOSED (commit 52bedd1), picorv32_wb cross-module port FIXED]
        ├── L3: Understand_bug_class/  [CLOSED ✅]
        ├── L3: Trace_evidence/  [CLOSED ✅, edge e1308 identified]
        ├── L3: Identify_root_cause/  [CLOSED ✅, _map_to_elk_id Branch 1 returns IDs without emit]
        ├── L3: Fix_v1_connection_handler/  [FAILED ❌, port count 422→436 but target still missing]
        ├── L3: Fix_v2_recursive_existing/  [FAILED ❌, no effect, port nowhere in graph]
        ├── L3: Fix_v3_emit_instance_ports/  [CLOSED ✅, ROOT CAUSE FIX]
        └── L3: Verify_no_regression/  [CLOSED ✅, all projects pass, golden 5/5]
```

---

## 📊 Iteration Summary

| # | Time | Level | Parent Task | Goal | Expected | Actual | Status |
|---|------|-------|-------------|------|----------|--------|--------|
| 1 | 16:00 | L3 | Understand_bug_class | Run real-project test suite | Identify failing projects | darkriscv ✅, picorv32 ❌, serv ✅ | ✅ |
| 2 | 17:30 | L3 | Trace_evidence | Identify which picorv32 sub-target fails | List failing modules | picorv32_pcpi_mul ✅, picorv32_wb ❌ | ✅ |
| 3 | 18:00 | L3 | Identify_root_cause | Find why picorv32_pcpi_mul fails | Traceback analysis | Cycle in matched_tree recursion | ✅ |
| 4 | 19:30 | L3 | Fix_v3_cycle_detection | Apply Fix #4 v3 | picorv32_pcpi_mul passes | ✅ + golden regression 5/5 | ✅ |
| 5 | 22:00 | L1 | Plan_B_Step_F | Document + commit Plan B Step F | Commits a939d68 + 9eab9ed | ✅ Both committed | ✅ |
| 6 | 22:17 | L1 | Debug_mindset_skill | Create reusable debug skill | Skill + doc | ✅ Both created (50620e6) | ✅ |
| 7 | 22:28 | L2 | Plan_B_Step_G | Start picorv32_wb investigation | Understand bug | Edge e1308 missing port identified | ✅ |
| 8 | 22:50 | L3 | Fix_v1_connection_handler | Add CONNECTION to referenced set | Port emitted | +14 ports, target STILL missing | ❌ |
| 9 | 23:10 | L3 | Fix_v2_recursive_existing | Make defensive check recursive | Port emitted | No effect (port nowhere) | ❌ |
| 10 | 23:30 | L2 | Plan_B_Step_G | Revert + write down | Clean state + lessons doc | ✅ All clean, golden 5/5 PASS | ✅ |
| 11 | 23:48 | L1 | Setup_task_tree | Create iteration tracking infra | Folder structure + overview | ✅ This file + 2 subfolders | ✅ |
| 12 | 23:48 | L1 | Setup_task_tree | Create iteration tracking infra | Folder structure + overview | ✅ This file + 2 subfolders | ✅ |
| 13 | 23:55 | L3 | Investigate_alternate_path | Read _map_to_elk_id | Find true root cause | ✅ Found Branch 1 issue | ✅ |
| 14 | 00:05 | L3 | Fix_v3_emit_instance_ports | Apply V15 cross-instance port emit fix | picorv32_wb PASS | ✅ 539813 bytes, golden 5/5 | ✅ |
| 15 | 00:10 | L2 | Verify_no_regression | Test all sub-targets + golden | All pass | ✅ All 7 projects, golden 5/5 | ✅ |
| **16** | **07:30** | **L2** | **Reconfirm_picorv32_wb** | **Re-verify after 7h** | **Still passes** | **✅ All pass, fix stable** | **✅** |

---

## 🔥 Active Task: Plan B Step G (Cross-Module Port Edge)

**Bug**: ELK "Referenced shape does not exist: port_picorv32_wb_dot_picorv32_core_dot_clk" when running picorv32 with `--module picorv32_wb`.

**Confirmed evidence**:
- Edge `e1308, kind=connection` at root level, source `sig_clk_wire`, target `port_picorv32_wb_dot_picorv32_core_dot_clk`
- Edge added by `_emit_cross_instance_connection_edges` (line 1934+) with `_meta.v15_added: True`
- Port shape **nowhere** in graph (root + nested both empty)
- 422 port emits total, 306 port refs, 1 missing

**Failed fixes**:
- Fix #1: Add CONNECTION to `_referenced_input_fulls` walk → 422 → 436 emits, target still missing
- Fix #2: Make `_post_existing` recursive → no effect

**Next investigation direction** (per user instruction 23:48:34):
- Read `_map_to_elk_id` (called from `_emit_cross_instance_connection_edges`)
- Trace exactly how `port_picorv32_wb_dot_picorv32_core_dot_clk` is generated
- Find what code path SHOULD have emitted it but didn't
- Direction is OK to be wrong — record all findings as iterations

---

## 📁 Folder Structure

```
docs/task_tree/
├── overview.md              # THIS FILE
├── tasks/                   # Task definitions (L1, L2, L3...)
│   ├── L1_plan_b_real_project_visualization.md
│   ├── L2_plan_b_step_a.md  (CLOSED)
│   ├── L2_plan_b_step_b.md  (CLOSED)
│   ├── L2_plan_b_step_c+d.md  (CLOSED)
│   ├── L2_plan_b_step_e.md  (CLOSED)
│   ├── L2_plan_b_step_f.md  (CLOSED)
│   ├── L2_plan_b_step_g.md  (ACTIVE)
│   ├── L3_understand_bug_class.md  (CLOSED)
│   ├── L3_trace_evidence.md  (CLOSED)
│   ├── L3_identify_root_cause.md  (CLOSED)
│   ├── L3_fix_v1_connection_handler.md  (FAILED)
│   ├── L3_fix_v2_recursive_existing.md  (FAILED)
│   └── L3_investigate_alternate_path.md  (ACTIVE)
└── iterations/              # Iteration-by-iteration records
    ├── iter_001_run_real_project_suite.md
    ├── iter_002_identify_failing_picorv32_subtargets.md
    ├── iter_003_picorv32_pcpi_mul_traceback_analysis.md
    ├── iter_004_fix_v3_cycle_detection.md
    ├── iter_005_document_and_commit_plan_b_step_f.md
    ├── iter_006_create_debug_mindset_skill.md
    ├── iter_007_start_picorv32_wb_investigation.md
    ├── iter_008_dump_elk_graph_find_missing_port.md
    ├── iter_009_fix_v1_connection_handler.md
    ├── iter_010_fix_v2_recursive_existing.md
    ├── iter_011_revert_and_write_down.md
    ├── iter_012_setup_task_tree_infrastructure.md
    └── (next iterations as work continues)
```

---

## 📝 Iteration File Format

Each iteration file in `iterations/` follows this format:

```markdown
# Iteration N: [Short Title]

**Metadata**:
- **Iteration #**: N
- **Task Tree Level**: L1 / L2 / L3
- **Parent Task**: [parent task ID]
- **Created**: YYYY-MM-DD HH:MM GMT+8
- **Author**: 方豆 / QClaw

---

## 🎯 Current Goal

[What we're trying to accomplish in this iteration]

## 📋 Expected Result

[What we expected to happen if our hypothesis/plan was correct]

## 🔬 Actual Result / Observation

[What actually happened. Include code snippets, error messages, file paths, line numbers.]

## 💡 Other Valuable Info

[Any additional context, dead-ends, related findings, future investigation ideas]

## 🔄 Next Action

[What to do next based on actual result]
```

---

## 🚦 Status Legend

- ✅ **CLOSED**: Task completed successfully
- 🟡 **IN PROGRESS / ACTIVE**: Currently working
- 🔴 **BLOCKED**: Cannot proceed without resolution
- ❌ **FAILED**: Attempted and reverted/closed without success

---

**Last updated**: 2026-08-26 07:35 GMT+8 (after re-verification of Plan B Step G fix)
**Status**: ✅ Plan B Step G fix is STABLE and working. All real projects pass. Golden regression 5/5.

## 🎉 闭环总结 (2026-08-26 07:35)

| Step | Commit | Status |
|------|--------|--------|
| A | (prior) | ✅ |
| B | `6e8256c` | ✅ |
| C+D | `8e98abd` | ✅ |
| E | (folded into F) | ✅ |
| F | `a939d68` | ✅ |
| **G** | **`52bedd1`** | **✅ FIXED + RE-VERIFIED 7h later** |

**Tonight's commits (4 total)**: `a939d68`, `9eab9ed`, `50620e6`, `52bedd1`

**Real-project visualization status (07:35 GMT+8)**:
- ✅ picorv32_wb (was failing, NOW FIXED)
- ✅ picorv32_core, picorv32_pcpi_mul, picorv32_pcpi_div, picorv32_axi, picorv32_regs
- ✅ darkriscv
- ✅ Golden regression 5/5

Open-source project visualization is **correct and verified**. Ready for next task.