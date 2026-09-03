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
└── L1: Test_Assets_ABC/  [🟡 B 复查中, 方豆 "先记录 A B C, 我们逐个做"]
    ├── L2: A_主路径语法独立regression/  [✅ CLOSED, iter_081: 10 文件 42 测试]
    ├── L2: B_修integration14失败/  [🟡 REOPENED iter_086: 13/14 完成; 剩 picorv32 ELK dangling port 暂缓 (方豆 "elk 先不管")]
    └── L2: C_扩truth层/  [✅ CLOSED, iter_083: 2 文件 10 测试 + spec 修复]
└── L1: Truth_层扩充_T1-T12/  [✅ CLOSED, iter_088~100: truth 32→112]
└── L1: 缺陷_A-F修复/  [✅ CLOSED, iter_101~104: expression/位宽/拼接/ternary 常量/part-select/generate-if 全修]
└── L1: picorv32_ELK修复/  [✅ CLOSED, iter_106: dangling port 修复, integration 全绿]
└── L1: openrtl_工业算法摸底与缺口修复/  [🟡 ACTIVE, iter_109~; 门级原语 iter_112 完成]
    └── L2: generate实例链/嵌套作用域/门级原语/...  [见 iter_109~112, 逐个缺口修复]
    └── L2: Gate_Primitive_Support/  [✅ CLOSED iter_112: leaf cell 建模, tasks/L2_gate_primitive_support.md]
    └── L3: Truth_expansion/  [✅ CLOSED, 全绿]
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
| **17** | **08:50** | **L2** | **iter_064~066 行为断言升级** | **4 域测试行为断言补齐 (4 并行 subagent)** | **103 测试升级** | **✅ constraint 7 / covergroup 22 / sva 11 / module 63 全过; regression 781 passed (2 pre-existing)** | **✅** |
| **18** | **2026-09-01** | **L2** | **C 组功能缺口 #41-#44 (方豆 "一起做")** | **修 EXTRACTION_COVERAGE #41-#44** | **#41 class 方法体赋值 / #42-#43 task 调用站点形参映射 / #44 DPI 评估** | **✅ #41 (iter_075) + #42/#43 (iter_076) 已修, 2 新测试 + 1 升级, regression 766 passed; #44 期望行为不修** | **✅** |
| **19** | **2026-09-01** | **L2** | **id() 复用模式全仓扫描 (iter_075 承诺跟进)** | **扫 src/ 找 id(n) seen/key 非确定源** | **7 处模式逐一定性** | **✅ 全部安全 (同一 AST 树存活); 仅 class_graph_builder 是越界案例 (已修); 零代码改动** | **✅** |
| **20** | **2026-09-01** | **L2** | **测试资产梳理 (TEST_MAP 重梳)** | **实测统计 + 功能域分类** | **301 文件 2997 测试** | **✅ TEST_MAP 重写, 引用全验证; TECH_MAP 同步实测口径; 核心回归集 38/317 ~19s; test_nested_diff 修复** | **✅** |
| **21** | **2026-09-01** | **L1** | **Test_Assets_ABC (方豆 "先记录 A B C")** | **A 主路径语法 regression + B 修 integration + C 扩 truth** | **A: 10 文件 42 测试 (iter_081) / B: 2 断言修复+12 环境定性, integration 0 failed (iter_082) / C: 2 truth 文件 10 测试 + spec 幽灵文件修复 (iter_083)** | **✅ A/B/C 全部完成, regression 808 + truth 28 passed** | **✅** |
| **22** | **2026-09-02** | **L1** | **B 组复查 (方豆 "确认下状态")** | **验证 iter_082 "0 failed" 是否可信** | **实测 integration 417+2 failed+3 skipped** | **iter_082 误分类: real_project_viz 2 个是真实失败 (HOME 重定向使 ~ 路径失效被动态 skip 造成假绿); darkriscv 断言已修 (--svg), picorv32 ELK 根因定位 (SignalRef 解析不一致) 方豆拍板暂缓** | **⚠️ 部分** |
| **23** | **2026-09-02** | **L1** | **cli 3 失败修复 (方豆 "新发现的3个也改一下")** | **修 iter_086 顺带发现的 3 个 cli 失败** | **unit+cli 全绿** | **根因: models.py to_dict/from_dict 不支持 width=None → cache 序列化 TypeError (所有开 cache 的 CLI 测试受威胁); test_compare_greater_appears 断言过时 (SVG 结构); 两测试文件 --no-strict→--strict** | **✅ unit+cli 全绿** |
| **24** | **2026-09-02** | **L1** | **Truth 层扩充 T1-T12 (方豆 "按这个顺序来推进吧")** | **12 项 1:1 golden 缺口补齐** | **truth 32→112 全绿** | **12 文件 + 5 fixture: assign/clock-reset/case/位选/concat/function-task/parameter/alias/class/generate-if-case/SVG 布局/查询精确集; 顺带发现缺陷 A-F** | **✅ 108 passed + 4 既有 skip** |
| **25** | **2026-09-02** | **L1** | **缺陷 A-F 修复 (方豆 "继续")** | **修 truth 层发现的 6 个缺陷** | **零回归** | **A expression 字节切片 / B net-decl 位宽 / C LHS concat zip / D ternary 常量值 / E part-select 宽度 None / F generate-if always; +11 truth 断言; golden ×4 重生成** | **✅ 2835 passed** |
| **26** | **2026-09-02** | **L1** | **picorv32 ELK 修复 (方豆 "继续")** | **修 iter_086 暂缓的 dangling port** | **integration 全绿** | **preference (已 emit 优先) + 最终兜底补发; mem_axi_bvalid 复用孪生, resetn 兜底 1 个** | **✅ 2836 passed + 0 failed** |
| **27** | **2026-09-02** | **L1** | **A-F 收尾 (方豆 "继续")** | **EXTRACTION_COVERAGE 同步 + 无 init net 宽度** | **零回归** | **#11/#15 行更新 + 变更日志; case27 prod (1,0)→(7,0)** | **✅ 2835 passed** |
| **28** | **2026-09-02** | **L1** | **#23/#24 generate 单块 wire (方豆 "继续")** | **GenerateBlock net 声明提取** | **零回归** | **#23 修复 (镜像 F) + #24 验证 (probe); spec/truth 更新; _iter_generate_children 去重** | **✅ 2843 passed + 0 failed** |
| **29** | **2026-09-02** | **L1** | **归档 (方豆 "先归档记录")** | **TEST_MAP/CHANGELOG/CURRENT_TODO 同步** | **文档一致** | **truth 130 / 全仓 329 文件 3148 测试; CHANGELOG 2026-09-02 条目; CURRENT_TODO 单表清理; 记录算法模块调研方向** | **✅** |
| **30** | **2026-09-02** | **L1** | **generate-for 实例化链提取 (方豆 "继续")** | **iter_109: gen 实例路径带索引 + 连接解包 + #45** | **cordic rotator 进图** | **_get_generate_block_name g[i]; get_modules collect_instances 递归 GenerateBlock{Array}; 实例 CONNECTION ElementSelect/Assignment 解包; truth +6** | **✅ (commit c7e17e3)** |
| **31** | **2026-09-02** | **L1** | **CORDIC 嵌套作用域 (方豆 "继续")** | **iter_110: 嵌套 generate 连接信号解析到宿主模块** | **cordic DRIVER 25→100** | **_sig_scope 剥掉末尾实例名 + 全部尾部 [N] 段; shifter.Q→g[i].U.x_i_shifted 按正确作用域 (16 entry)** | **✅ (commit 6f005a1)** |
| **32** | **2026-09-02** | **L1** | **CORDIC 流水线 truth (方豆 "继续")** | **iter_111: 真实工业 fixture 锁 iter_109/110** | **truth +6** | **golden_dataflow_39 (verilog_cordic_core 真实源码) + test_cordic_pipeline_truth (15 rotator / 链 / 作用域); 365 节点 100 DRIVER** | **✅ (commit 329afc3)** |
| **33** | **2026-09-03** | **L1** | **门级原语 leaf cell 建模 (iter_112, 摸底缺口)** | **KoggeStone xor16.S 全无驱动 + and0.and0 递归** | **门输出 DRIVER 边; 原语不再当模块实例** | **native/generate 三处 PrimitiveInstance 过滤 (parity 对齐); adapter get_primitive_instances (+genvar ctx); driver _create_primitive_edges; connection get_path 防自环; unit 8 + truth 6 (golden_dataflow_40 = 真实 xor16.v)** | **✅ 14 新测试, 全量回归见 CURRENT_TODO** |
| **34** | **2026-09-03** | **L1** | **CLA 嵌套 generate 缺口 (iter_113, 方豆 "修这个新发现的generate")** | **top.u_cla.generators[i].cell4 两级实例 generate 0 提取 + inst==type 递归** | **嵌套 generate 内部按索引作用域提取; 递归清零** | **graph_builder.walk generate 下钻 (hp 路径); connection inst_module_name 去 '!= inst_name' 守卫 (type token 权威); cordic 同受 driver 不下钻之害 (truth DRIVER 实为端口自环); unit 4 + truth 6 (golden_dataflow_41 = 真实 CLA)** | **✅ 10 新测试, 全量回归见 CURRENT_TODO** |

| **35** | **2026-09-03** | **L2** | **truth target 模式升级 (iter_114, iter_113 兑现)** | **cordic/genfor truth 的 driver 盲区 (generate 实例内部从未断言)** | **rotator 内部逻辑真断言** | **builder 切 target; cordic +4 (x_1/y_1/z_1×15 驱动/操作数/输出链/45 内部状态), genfor submodule 断言改实例作用域 (top.g[i].U.x→xo); 旧 'DRIVER>50' 实为 connection 端口自环 120** | **✅ +10 断言, 61 批次 passed** |
| **36** | **2026-09-03** | **L2** | **gate 端子方向改善 G-1 (iter_115, 方豆 "改善端子方向的改进")** | **多输出 buf/双向 tran 用位置约定会错** | **端子方向权威判定** | **探查: 输出端子 (含 InOut) 全被 slang 包成 Assignment, NInput/NOutput 是模板 ports, Fixed/UDP 逐端子带 direction; 重写解析: 输入→每个输出, tran InOut 互驱, supply0 常量无源; unit +5** | **✅ buf o2←a / tran t⇄a / UDP y←a,b; 61 批次零回归** |
| **37** | **2026-09-03** | **L2** | **7 skip 处置 (iter_116, 方豆 "再看那7个skip是啥")** | **serv/neorv32/zipcpu SVG skip + d1 mutex ×4** | **能去的去掉, 不符目的的重写** | **serv 解锁 (filelist+serv_top, 747KB SVG 4.1s); neorv32 (VHDL)/zipcpu (wrapper 重构) 移除; d1 lookupName 收编 (直排 -c 每 case subprocess, mutex 真根因: 同进程累计查询必崩, 与 pytest 无关)** | **✅ skip 7→0, real_project_viz 4 passed + d1 8 passed** |
| **38** | **2026-09-03** | **L2** | **索引段加倍假节点 (iter_117, 方豆 "开工, 修复这个问题")** | **aes U_SUB.ROM[4].ROM[4] ×84 / dblclockfft GENSTAGES[0].GENSTAGES[0] ×63/模块** | **索引段唯一** | **get_path: 父路径已以 [N] 结尾 → gen_block 置 None (hp 正则二次取段是根因); genfor/CLA 正常是 legacy 族同 key 覆盖掩盖 (无 legacy 族即暴露); aes 84→0 / fftmain 63→0; unit +3** | **✅ 真实验证清零, 74 批次零回归** |
| **39** | **2026-09-03** | **L2** | **极端场景验证 (iter_118, 方豆 "构造极端场景确认正确性")** | **generate RHS 位选丢 genvar 索引 (S8 深链死端; case27 iter_035 起潜伏)** | **per-entry RHS 索引** | **9 类极端场景; _fold_sel ctx 求值 (Literal ConstantValue/op 枚举名踩坑×2); 新 unit +3; chain truth/golden 随修复更新 (prim_arbiter DRIVER 90→118); S2 connection RangeSelect 命名 '?' 记录 backlog** | **✅ case27/链/S8 per-index; 回归处置后见 commit** |
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