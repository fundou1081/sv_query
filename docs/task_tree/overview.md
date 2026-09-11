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
└── L1: Covergroup_联系  [✅ CLOSED iter_162~166: G1-G4 全闭环, 观察域转正]
└── L1: 参数化 class 支持 (GenericClassDef)  [✅ CLOSED iter_170: 统一成员访问面, P1-P3 通]
└── L1: 文档清理与文档卫生  [✅ CLOSED iter_171: 归档 63 份 + check_docs.py + AGENTS v1.5]
└── L1: 缓存目录可配置  [✅ CLOSED iter_172: env+XDG 解析 + 不可写降级, 29 假失败清零]
└── L1: adapter 层拆解  [📋 方案待讨论 iter_173: base.py 死层 + SemanticAdapter 分域]
    └── 规划: covergroup_tracing_plan.md (Q1-Q4 / G1-G4) + tasks/L1_covergroup_linkage.md
    └── 注: class 追踪 C1~C5 已闭环 (iter_134~159, 见 CURRENT_TODO + class_tracing_plan.md; overview 行欠账待补)
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
| **40** | **2026-09-03** | **L2** | **connection RangeSelect 命名 (iter_119, S2 backlog)** | **.+:.a(a[i*4+:4]) 连接命名恒 '?'** | **[hi:lo] 切片命名** | **semantic RangeSelect: left/right 在 expr + selectionKind (IndexedUp/Down/Simple); [base+:width] right 是宽度; _eval_select_index 接入两端; S2 占位 2→0; unit +3** | **✅ y[1:0]/[3:2] 命名; 回归见 commit** |
| **41** | **2026-09-03** | **L2** | **generate 实例连接 key 碰撞 (iter_120, iter_119 观察深挖)** | **G2[0] 连接缺失 (minimal 0 连接 / 嵌套错挂)** | **per-entry 归属正确** | **双根因: ① legacy get_generate_instances 嵌套丢 root 覆盖 indexed 族 (iter_117 后冗余, 移除) ② module_to_path key 无父路径 → 多实例同名 gen 碰撞 → 逐实例 paths_by_info; minimal 0→4 连接, 4 层 4 条全对; 101 批次零回归; unit +1** | **✅ per-entry 连接全归位** |
| **42** | **2026-09-03** | **L2** | **SVA 对抗缺口 (iter_121, 方豆 "constraint covergroup sva 对抗")** | **formal 泄漏/序列不展开/局部/函数/generate 0 断言/option 污染** | **6 缺口全修** | **syntax 语境区分 (容器 Token/Invocation callee/IdentifierSelectName base); post-pass 引用展开+实参并入; kind 精确匹配; generate 下钻+member 解包; 对抗 6 场景全绿** | **✅ unit +8, SVA 83 零回归** |
| **43** | **2026-09-03** | **L2** | **对抗 7-8 (iter_122)** | **cross 匿名名空串 / inline-with 无节点** | **#8 修 + #7 诊断** | **cross 合成名 cross_items; inline-with: 语义树过程体无约束符号落点, receiver 类解析需专项 (backlog)** | **⚠️ #8 ✅ covergroup 28 passed; #7 记录** |
| **44** | **2026-09-03** | **L2** | **inline 约束语义决策 (iter_125, 方豆 "先确认 semantic")** | **#7 该不该用 syntax** | **决策落档** | **验证: 语义树 StatementKind≠SymbolKind, ConstraintBlock 只计 named → inline 语义不可达 (固有不对称); 方豆拍板暂缓 + 文档维护 (未来改善观察项); iter_121 补丁定性为 syntax 症状修 (semantic 消歧重构待改进)** | **✅ 决策文档 + 无代码变更** |
| **45** | **2026-09-04** | **L2** | **准确性审计 A1/A2 (iter_126)** | **A1 无 target generate 嵌套实例内部缺失 / A2 总线直连位查询空答** | **A1 CLI 入口 opt-in; A2 位提升** | **A1 首版默认自动 target → 8 回归失败 (库无 target 类型级全模块契约被锁定) → 收窄: build_graph 新参 auto_target_single_top (默认关) + build_viz_tracer 无 --module 时启用; cordic CLI 365→542/667 rects genblk 内部出现; A2 位提升非空 (top.y[3]→u_sub.y); 原 A1 测试弱断言 (self-loop s==d) 重写为非自环真实驱动** | **✅ unit 5; 全量 2913 passed / 0 failed** |
| **46** | **2026-09-04** | **L2** | **准确性审计 A3 (iter_127)** | **实例输出端口 internal DRIVER 自环计入 fanin 驱动源** | **查询层跳过 internal 自环** | **两类自环区分: internal 标记 (恒 src==dst, 非源) vs nonblocking 真自环 (state<=state+1, 保留); query/signal.py 主循环 + _find_drivers (depth=1) 两处同规则; 图结构不改 (自环边供 out_edges/可视化); fanin(top.u_sub.y) [a,自身]→[a]** | **✅ unit +4; 全量 2913 passed / 0 failed** |
| **47** | **2026-09-04** | **L2** | **审计待验证候选实测 (iter_128, 方豆 "继续验证吧")** | **inout/struct/interface/时钟域/顶层输入 5 候选未实测** | **2 修复 + 2 缺口登记 + 1 预期** | **修复: ①fanin CLOCK/RESET 边守卫 (时序采样非数据源, 跨模块时钟链假驱动 top.clk 消除) ②A2 位提升条件 not drivers→not has_driver_edge and not drivers (struct 字段泄漏 + 位选中间递归 seen 污染双修); 缺口登记: inout 跨模块连接缺失 (connection_extractor 无 inout 分支) + interface 成员级无桥 (建模决策待拍板); 顶层输入空 fanin = 预期锁定** | **✅ unit +8; 全量 2921 passed / 0 failed** |
| **48** | **2026-09-04** | **L2** | **inout + interface 建模 (iter_129, 方豆拍板选 1+4)** | **inout 跨模块连接缺失 / interface 成员级无桥 + fanin 假驱动** | **单向 CONNECTION 建模** | **inout: connection_extractor 补 inout 分支 (output 式 inst_port→parent 同线), fanin 顶层 inout 穿透到实例三态链 (top.sda 空→[u_io.data]); interface: A2 提升目标限 data 类 (禁模块实例, 假 clk 消) + 成员桥 (connection_extractor 收集 InterfacePortSymbol links + graph_builder 后处理按实例是否驱动成员定单向方向: writer u_w.b.addr→bf.addr / slave bf.addr→u_s.b.addr)** | **✅ unit +7; 全量 2928 passed / 0 failed** |
| **86** | **2026-09-08** | **L1** | **属性读取真实点收尾 (iter_183)** | **方豆 "继续"** | **真实点 5 处修复** | **scanner 跳过 Store (74→70); 逐点定性: ~60 处 = 我们 dataclass 误报 (TraceNode/viz 模型), 6 处 wrapper 自身属性; **真实 5 处** (port_sym.type×2 / _symbol.name / member_val.name×2 / node.body) 已修; **关键发现: `hasattr(x,"name")` 在 pyslang 上不安全** (只吞 AttributeError, UnicodeDecodeError 穿透) → 应用 `safe_attr(x,"name",None) is not None`** | **✅ 全族清零** |
| **85** | **2026-09-08** | **L1** | **pyslang 属性读取 safe_attr 收敛 (iter_182, iter_181 backlog)** | **方豆 "继续"** | **热路径 70 点** | **新增 tools/scan_pyslang_attrs.py (AST 启发式) → 全仓 126 处未保护属性读取; 热路径收敛 70 点/8 文件 (`.name`→"" / `.type`→None / `.body`→[] — 默认值按"可继续执行"语义选); 自伤如实记录: 导入深度 `..._safe` 应为 `.._safe` → 7 模块 ImportError (已修); 剩余 56 点 (可视化/CLI 路径) 登记** | **✅ 热路径收敛** |
| **84** | **2026-09-08** | **L1** | **benchmark 复跑稳定性专项 (iter_181)** | **方豆 "继续"** | **⚠️ 2 修 + 根因族定位** | **修: flakiness 子进程缺 top_modules (与主测量对齐) + native_adapter 两处 top.name 未守护; 根因族: wrapper 语料非 UTF-8 identifier → pyslang **属性 getter** 抛 UnicodeDecodeError, 命中点随 elaboration/内存变化 → 间歇崩溃或部分 elaboration (nodes 1,778~3,057 / clk 88~205 / 5 次 1 无输出) — iter_180 "runs=2 退化" 真身; 教训: getter 级需 safe_attr (safe_str 无效); 对策: 结构性下限 + 3 次重试 → pr5 13 passed+1 skip; backlog: src 全量属性读取 safe_attr 包装** | **⚠️ 部分完成** |
| **83** | **2026-09-08** | **L1** | **bench 深结构基准 pr5_wrap (iter_180, C 路线第二项)** | **方豆 "走C路线"** | **兑现 iter_145 TODO** | **wrapper 真实 Cfg (4slv/3mst/32b/64b) 实例化 axi_xbar_intf: nodes 168→2,814 / 模块 271 / 深度 11 / clk fanout 0→187; pr5 套件 13 passed+1 skipped; 基准表 docs/BENCH_BASELINE.md; **深结构炸出 2 真实 bug (已修)**: _expr_helpers 缺 safe_str 导入 (此前补丁空操作) + _common.py:589 非 UTF-8 解码崩溃 (iter_141 漏点); 新登记: runs>1 复跑退化** | **✅** |
| **82** | **2026-09-08** | **L1** | **混合真实场景语料库 (iter_179, C 路线第一项)** | **方豆 "走C路线"** | **6 tests / 35 subtests** | **7 语料 (env 包 packet/嵌套约束/全栈混合/generate+类/子模块+module cg/logic 实参 Conversion/参数化嵌套) + test_mixed_corpus_truth.py 表驱动; 每语料锁 5 维度 (提取/Q1 采样链+驱动集/Q2 反向/Q3 约束/fanin) 精确集合; 断言值全部实测 (2 处首版写错按实测修正)** | **✅** |
| **81** | **2026-09-08** | **L1** | **参数化成员解析收尾 (iter_178, A 路线最后一项)** | **方豆 "继续"** | **2,245 + 739 全绿** | **先写会失败的参数化测试 (E5 this 成员链 / E13 内嵌参数化类成员) 证明缺口 → 统一成员入口 `_class_members_by_name` (走 adapter.get_class_members, 参数化用特化成员) 替换 `_is_class_member`/`_member_class_name` 的 `list(cls)`; 修完暴露并修复**嵌套参数化特化收录缺口** (扫描器下钻成员类型; adapter 侧 semantic/classes.py + covergroup_extractor.py 同步); 新增 2 测试** | **✅ A 路线完成** |
| **80** | **2026-09-08** | **L1** | **adapter 拆解 Step 10 + 专项收尾 (iter_177)** | **(方案 Step 10)** | **5 死方法移出; 专项闭环** | **定性: 75 方法面 = 外部调用 53 / 仅内部 10 / 零调用 12; 12 候选中 property (root/parser/trees)、wrapper 类 API (get_parent_module 等)、dunder 均保留 → 真死方法 5 个 (get_generate_instances 92 行/iter_modules/visit_module/get_class_name/get_definition) 移出 → legacy/dead_semantic_adapter_methods.py (156 行); 文档漂移修正 ×3 (PYSLANG_SEMANTIC_USAGE 两行/EXTRACTION_COVERAGE #46 + ARCHITECTURE 结构节); 自伤记录: 先删后归档顺序错误 → 从 git 恢复 92 行; gate: 2,243 / 739 / API 冻结 (60 方法) / docs ✅** | **✅ 专项闭环** |
| **79** | **2026-09-08** | **L1** | **adapter 拆解 Step 4-9 (iter_176)**: 六域 mixin 拆分 | **(方案 Step 4-9)** | **facade 3,036 → 227 行** | **62 方法搬入 `core/semantic/` 六域 (source_core 6 / modules 14 / ports_ifaces 10 / connections 4 / exprs_drivers 23 / classes 5) + `_expr_helpers` 396 行 + `_wrappers` 2 类; `SemanticAdapter(6 mixin)` MRO 组合, 方法名/签名零变化; 搬迁修 6 个真实问题 (dedent 错位/相对导入深度×2/typing 缺导入/方法体延迟 import 被包遮蔽/2 处 undefined 名 — 后者用 AST 静态扫描一次找全); gate: unit+regression+truth 2,243 / cli+integration 739 (与拆分前一致) / API 面 MRO-wide 冻结一致** | **✅ Step 4-9 完成** |
| **78** | **2026-09-08** | **L1** | **adapter 拆解 Step 3 (iter_175)**: 拆 474 行表达式分派函数 | **(方案 Step 3)** | **474 → 70 行** | **结构实测: 20 并列 if 分支, 其中 2 条件重复且前一处分支级 return → 后一处不可达 (死代码, 删除); latent bug: `_fold_sel` 定义在死分支内却被活分支 (ElementSelect/RangeSelect 非常量 selector) 调用 → 原路径必 UnboundLocalError, 提升为模块级 `_fold_select_index(sel, ctx)` 修复; 脚本化搬迁 16 个 kind 分支到模块级 `_expr_*` 纯函数 (控制流逐一保持, body dedent 8); 首版漏末尾 `return signals` → replication 套件 17 failed+13 errors 立即暴露并修复; gate: unit+regression+truth 2,243 / cli+integration 739 / API 面一致 / 新增 15 helper 单测** | **✅ Step 3 完成** |
| **77** | **2026-09-08** | **L1** | **adapter 拆解 Step 0-2 (iter_174)**: API 安全网 + legacy 移出 | **方豆 "用移出代替删除，这样可以恢复。去做吧"** | **Step 0/1/2 ✅** | **Step 0 API 面冻结测试 (65 方法+signature+3 property, 4 测试); Step 1 legacy 等价矩阵逐条核对 (4 文件多数断言已在 semantic 路径 — 仅 3 helper+1 inline 需移植, 2 处 shape 适配, 1 死 helper 删, 1 legacy 用例退役; 零覆盖损失); Step 2 `git mv src/trace/core/base.py legacy/base_pyslang_adapter.py` (-2,341 行) + legacy/README 恢复步骤 + 8 处注解改 SemanticAdapter + core/__init__ 导出清理 + 守卫测试扩展 (base.py 不得复活/src 不得 import); gate: unit+regression 2,064 / cli+integration 739 / truth 164 / API 面一致 / docs ✅** | **✅ Step 0-2 完成** |
| **76** | **2026-09-08** | **L1** | **adapter 拆解方案稿 (iter_173, A 路线第三项)** | **方豆 "拆 semantic, 做好方案和我讨论, 包括回归测试计划"** | **方案稿交付 (待拍板)** | **诊断实测: core/base.py 2,341 行 legacy 层 (PyslangAdapter+ASTWalker+3 Collector) 在 src/ 从未实例化 (仅 8 类型注解 + 4 测试实例化 1,546 行) — V2 清理漏项; SemanticAdapter 3,049 行/77 方法/42 外部调用, 7 个 ≥100 行条目占 40% (头号 474 行 _extract_signals_from_expr, 13 外部调用); 方案: P-A 删死层 (先做等价矩阵) + P-B mixin 分域 (调用方零改动) + 巨函数拆分; Step 0 API 面冻结测试作安全网; 回归映射 6 域快/深 gate + 基线 1112/2059/739/truth 19; 决策点 D1-D4** | **📋 待讨论** |
| **75** | **2026-09-08** | **L1** | **缓存目录可配置 + 不可写降级 (iter_172, A 路线第二项)** | **方豆 "缓存目录先更改, 更通用, 避免未来失败"** | **29 假失败 → 0** | **根因三层: 硬编码 `Path.home()/.svq/cache` / mkdir 裸调用 / 写盘裸调用 → CLI exit 1; 方案 B (env+XDG+降级) 优于只加 env; `resolve_cache_dir()` 显式>SVQ_CACHE_DIR>XDG_CACHE_HOME/svq>home; 构造与写失败 → 内存降级 + warning (含提示, 不刷屏); list_cache 裸 except 收窄 (AGENTS §2.5); 11 测试 (含子进程 CLI 端到端 rc=0); **cli+integration 由 19+10 假失败 → 739 passed/0 failed**; 全量 2059 passed** | **✅ 完成** |
| **74** | **2026-09-08** | **L1** | **文档清理与文档卫生 (iter_171, A 路线第一项)** | **方豆 "先进行A，先把文档清理"** | **归档 63 份 + 4 项检查全 0** | **盘点 370 md (零入链 119); git mv 归档 63 份 (可视化历史 13/计划重构 20/审计报告 15/重复索引 2/专向稿 7/实验薄文档 4/重复 TESTING 1/sim 旧报告 4/根设计稿 2); docs/INDEX.md 重建为唯一入口 + 计数单一真相源; 新增 tools/check_docs.py (死链/归档越界/未登记/计数漂移) — 37→0/18→0/36→0/33→0; AGENTS v1.5 文档卫生 5 条; 顺带修 CONTROL_FLOW_DESIGN 不存在引用 ×2 + pyproject 注释引用已删 shim + 悬空规划引用** | **✅ 完成** |
| **73** | **2026-09-06** | **L1** | **参数化 class 专项 (iter_170): GenericClassDef 统一成员访问面** | **方豆 "按A，开专项做"** | **P1-P3 全通** | **突破: 实例特化 ClassType 可迭代 (defaultSpecialization 坏绑定绕行实例类型); baseClass 链收参数化父类; SemanticAdapter.get_class_members 统一入口 (ClassType 迭代 def / GenericClassDef → 特化成员); 改造 4 处 (class_graph_builder×3/function_extractor/covergroup_extractor); P1 宽度参数 / P2 多特化逐实例隔离 / P3 参数 extends 继承约束传播; 11 测试; 全量 2048 passed; 边界: 类型级宽度取首见特化** | **✅ 专项完成** |
| **72** | **2026-09-06** | **L1** | **Covergroup 参数化/高级形态对抗 (iter_169)** | **方豆 "参数class 等等"** | **发现 GenericClassDef 缺口** | **参数化 class = GenericClassDef (不可迭代无 body) → 提取/图/方法 3+1 断点, 支持 = class 域独立小项目 (defaultSpecialization(scope) 需 Scope — 决策待方豆); 验证 6 高级形态通过 (typedef 前置全链/option 语句/class cross/$rose/enum/static 显式) +6 测试** | **⚠️ 参数化决策待拍** |
| **71** | **2026-09-06** | **L1** | **Covergroup 混合场景对抗 (iter_168): env 嵌套 + 全栈混合** | **方豆 "混合 class module covergroup 更接近真实场景"** | **2 缺口修** | **槽展开 (query/covergroup.py): class 成员实例 env.p — IS_INSTANCE_OF 指类型槽 tb_env.p 非活对象 top.e.p → auto 落非数据槽 → _class_instances 槽展开 (owner×成员递归); 嵌套约束 (query/constraint.py): ConstraintTracer 单级→泛化嵌套链 top.e.p.addr → packet.c_addr (trace_constraints 本身受益); M3 全栈 (assign+submodule+class 方法+双域 cg) Q1/Q2 验证通过; 10 混合测试, 2031 passed** | **✅ 混合对抗完成** |
| **70** | **2026-09-06** | **L1** | **Covergroup 对抗轮 (iter_167): 找盲点** | **方豆 "先来再做一些对抗性测试"** | **2 bug 修 + 边界登记** | **A2 自定义类型 cast 类型名当信号 (Cast 跳类型子节点); C4 查询错实例静默 bogus id (校验实例集→missing); 登记 6 边界 (A5 变量索引/A8 $root 层次/B1 extends auto 实例枚举缺/B6 同名 class D5 同源/C5 同名 cg 全返回); 验证 6 通过 (匿名 cp/嵌套调用/interface cg/iff/子模块 host/select-id/extends 约束); 12 对抗测试** | **✅ 对抗轮完成** |
| **69** | **2026-09-06** | **L1** | **Covergroup G4 (iter_166): Accuracy Claim 转正 — 观察域闭环** | **方豆 "开工!"** | **G4 ✅ 纯文档** | **audit §1 建模决策 +3 行 (观察域不进主图/bins 命中=运行时) / §2 L1 观察结构 + L2 联系查询承诺 / §3 covergroup 移出 hybrid 例外 (剩 SVA/procedural/inline) + 运行时边界明写; README 追踪范围纳入 + class 决策历史注 (演进不改原句); G1-G4 全闭环 (iter_162~166), 47 测试全量 2009 passed** | **✅ covergroup 联系闭环** |
| **68** | **2026-09-06** | **L1** | **Covergroup G3 (iter_165): 查询 API Q1-Q3** | **方豆 "切回g3 继续 coverage"** | **G3 ✅** | **query/covergroup.py (D4 范式观察域独立): Q1 trace_covergroup_sampling (采样信号→fanin 委托, class 实例端点 D3 单实例自动/多实例显式) / Q2 trace_coverpoints 反向三域 (module 顶层宿主锚 host_module 新增 / class 类型级 / 实例级) / Q3 rand-约束委托 ConstraintTracer; UnifiedTracer 薄委托×3 + 惰性 cgs 复用编译器不双编; 11 测试 (module/class/多实例歧义; Q2 类型级 vs 实例级分开查询域)** | **✅ G3 完成** |
| **67** | **2026-09-06** | **L1** | **Class 域 P1 修复 (iter_164): 方法实参 logic Conversion 壳丢实参** | **方豆 "先处理发现的 class 域问题"** | **P1 修 + P2 澄清** | **根因 (插桩定位): logic 实参 → bit 形参 (4→2 态) slang 插 Conversion 壳 (无 .expr/.symbol) → _parse_invocation_call 守卫静默 continue 丢实参 → 展开断; 修: 实参 + Assignment rhs 剥 Conversion 链 (iter_136 端口同款); module function logic 入参同受益; P2 (连续 build 退化) 复测 = P1 混淆 (bit fixture 稳定, 如实修正 iter_163); 6 测试 + Q4 fixture 升级 logic 端口回归覆盖** | **✅ P1 修复** |
| **66** | **2026-09-06** | **L1** | **Covergroup G2 (iter_163): 实例化绑定 (Q4)** | **instance_rule + 定义×实例绑定** | **G2 ✅** | **实证: class 内 cg = CovergroupType + 同名 ClassProperty, ctor 语句只在 syntax 层; embedded cg 只能新方法赋值 (LRM); instance_rule (module_scope/ctor_new/uninstantiated, this.cg+条件 new 识别) + covergroup_binding.py 纯映射 (B 隔离不建图) — Q4: p.cg 采样 p.addr; 12 测试 (Q4 端到端绑定+fanin 贯通); 顺带实证 class 域既有隐患: 方法实参 logic 4 态 → 展开断 (bit 通, 与 covergroup 无关) 登记 backlog** | **✅ G2 完成** |
| **65** | **2026-09-06** | **L1** | **Covergroup G1 (iter_162): in_class 归属 + signal 结构化解析** | **方案 B 首步 — 提取补全 + 解析 (plan G1)** | **G1 ✅** | **实证推翻 "class 内提取缺失" 前提 (遍历可达); 真缺口 = in_class 恒空 (coverage.py --class 过滤静默失效) + signal 原始串; 修: 遍历带 scope_class 归属 + SampledSignal (module/class_prop 类型级/select, syntax 走查器 — Invocation 无 "Call" 字样坑 callee 泄漏对抗捕获, 常量/调用 callee 跳过); signal 原文保留 8 消费方零改动; 24 新测试; covergroup 72 + CLI 67 + unit/regression 1980 passed (1 opensource 测试 env 假失败 = sandbox ~/.svq cache 写拒绝)** | **✅ G1 完成** |
| **64** | **2026-09-06** | **L1** | **Covergroup 联系: 方案 B 拍板 + G1 开工 (iter_161)** | **方豆 "哪个方案维护性更好" → "按b 先更新文档, 再开始做"** | **B 落档 + G1 启动** | **维护性判据落档 (8 消费方零涟漪 / kind 守卫饱和 / 单一 fanin 实现 / Claim 干净); plan 决策点 1/3 定 (类型级为主 / 动态=文档标记); tasks/L1_covergroup_linkage.md + overview 挂树; G1 = class 内 covergroup 提取 + signal 结构化解析** | **🟡 G1 进行中** |
| **63** | **2026-09-06** | **L1** | **Covergroup 联系规划 (iter_160, 方豆 "规划 covergroup 要和 signal / class rand var 联系")** | **现状实证 + 方案对比** | **规划稿提交** | **CovergroupExtractor 独立 / Coverpoint.signal = syntax 原始串 / class 内 covergroup 提取缺失 / 实例化未建模; 方案 B (独立结构+查询桥, D4 范式) 建议; G1~G4 路线; commit de93489** | **✅ 规划 (待拍板→iter_161 定)** |
| **62** | **2026-09-05** | **L3** | **benchmark 环境修复 + topModules 编译能力 (iter_145)** | **benchmark usage 11 skip (误判 HOME env 数月)** | **恢复 + 真因** | **真因三层: ①/tmp filelist 缺失 ②axi repo 版本演进 (axi_xbar_dp_ram 不存在) ③free-floating type-param 预 elab (axi_demux, CVA6 cvxif 同款); 修: SVCompiler/UnifiedTracer top_modules (options.topModules 只 elaborate 目标树 — iter_140 弃用 方案落地, picorv32 IM 0 = 自包含真实数据) + GenericClassDefSymbol 防崩 (真 bug) + pr5 filelist 自动生成 + 断言按真实数据修正 (旧阈值靠 pulp pr2 大参数/free-floating 虚高, wrapper 深度基准 TODO); pr5 10 passed, picorv32 11 passed** | **✅ 全量 3071 passed (serv 1 env 假失败同前)** |
| **61** | **2026-09-05** | **L2** | **A2 位对位切片偏移桥 (iter_143, Claim L3 #3 收窄残留)** | **bus↔切片连接 .y(y[7:4]) 位查询停 bus 粒度** | **双向位级贯通** | **_expand_bus_conn_bit_bridges 第二段: 一端 bus 一端切片 CONNECTION, 声明序低位对齐 (bus[blo+off] ↔ slice[slo+off]); bus 侧位节点存在才建, 切片侧单 bit 缺失则创建 (真实位 — 切片连接驱动); 不建 BIT_SELECT 聚合边 (防 bus 提升查询收位驱动污染悬空位 top.y[3]); 宽度不匹配 skip; 证据: fanin(top.y[7])={a[3]链} (偏移4) / fanin(u_sub.a[3])={top.a[7]} / 悬空位 {u_sub.y} 干净; A2 位对位 (同构+切片) 全闭环** | **✅ unit +3; 全量 3061 passed (serv 1 env 假失败同前)** |
| **60** | **2026-09-05** | **L2** | **interface 多写共享诊断闭环 (iter_142, Claim L3 #2)** | **master+slave 同线多写归属/合并** | **7 场景实测定性** | **iter_129 单向桥方向 (实例内部有 incoming DRIVER = 写方, 否则读方) 逐实例独立判定: 双 writer 多源集合 / writer+reader 读不反向 / top 直驱并入 / modport 方向 / 同成员回读 均正确 — 无真缺陷; 归属单点依赖协议时序 = 语义边界 (与 inout #1 同构); 反例表剩 2 项 + 1 重构; Accuracy Claim 文档演进标注 (iter_136~141)** | **✅ 诊断闭环, 无代码改动** |
| **59** | **2026-09-05** | **L2** | **解码健壮性批量修复 (iter_141, iter_140 续)** | **CVA6 建图解码崩溃 (UnicodeDecodeError 打地鼠)** | **系统性修复** | **pyslang pybind 属性/str() 在非 utf8 identifier 抛 UnicodeDecodeError 的点全换 safe_attr/safe_str + 新 helper safe_symbol_name (always_extractor find_clock / driver find_reset+_detect_binary_op / function_extractor / semantic_adapter get_function_name+get_assignments+MemberAccess / _common 全文件含 iter_bit_selects str(syn) / expression_tree str(token) 删冗余解码) — 崩溃→warning; CVA6 建图推进后 Segmentation fault = 8GB 内存/原生边界 (iter_059 先例, 非代码 bug, 大内存可验)** | **⚠️ 部分: unit+integration 1543 passed** |
| **58** | **2026-09-05** | **L2** | **CVA6 strict 编译: 特征代码 + 修复 (iter_140, Claim L3 #7)** | **cva6 strict 编译 179/44 错** | **编译配方打通** | **特征代码法**: ①44 错 = cvxif_example 未实例化 type-param free-floating 模块 (pyslang 默认 type=logic 检查 body → InvalidMemberAccess; Verilator 只 elaborate 实例树不报; 最小复现确认) → filelist 剔 3 示例 ②compiler.py override-orphan 假错 修复 (override 指向 drop 模块不 fatal, 跳过重编; 重建须置 _comp=None) ③解码健壮性 ×2 (_common.get_signal / semantic_adapter MemberAccess, 大设计非 utf8 identifier 崩溃); CVA6 core 编译通过 (root: cva6/copro_alu/fifo_v3); 完整建图剩 解码点 (iter_141 续)** | **⚠️ 部分: unit+cli 1514 / unit+integration 1543 passed** |
| **57** | **2026-09-05** | **L2** | **条件控制信号排除 (iter_139, iter_138 方案 2 方豆拍板)** | **三态 en 混入数据 fanin (i2c 不对称杂音)** | **控制边不进数据源** | **BRANCH_*/CASE_* 与 CLOCK/RESET 同规则 (query/signal.py): 控制信号 (en/sel) 不 append 不递归 — 已记录在 DRIVER.condition (铁律16) + 条件边 (detailed 可查), 不重复; i2c 双驱动 fanin(sda) = {data_master, data_slave, u_slave.data} (双侧对称去 en); ternary {a,b} / case {a,b,c} 数据源保持; unit +4; 全量 3058 passed (serv 1 env 假失败同前)** | **✅ Claim L3 #1 缺陷部分闭环** |
| **56** | **2026-09-05** | **L2** | **inout 多驱动归属诊断 (iter_138, iter_129 backlog / Claim L3 #1)** | **i2c 开漏 外部+实例同驱哪边算源** | **定性 + 方案** | **6 场景实测: iter_129 单向建模已覆盖 (双器件多源 / 外部驱动+只读无反向污染 / 级联穿透); 定性: 归属单点依赖运行时 en = 静态语义边界 (fanin = 可能驱动方集合, 已实现); 真缺陷 = 三态 en BRANCH 链不对称杂音 (顶层缺/实例进) → iter_139 方案 2 修** | **✅ 语义澄清 + 缺陷修复 (iter_139)** |
| **55** | **2026-09-05** | **L2** | **A2 位对位同构直连 (iter_137, audit A2 后续项 / Claim L3 #3)** | **顶层输出总线位查询停 bus 粒度 (u_sub.y)** | **位级贯通** | **双修: ①graph_builder._expand_bus_conn_bit_bridges: bus↔bus 同宽 CONNECTION 补位桥边 (仅两侧位节点都存在 — 不造假节点; 纯 bus 直通 BUSFIX 保持总线粒度, iter_126 truth 不变; filter 后跑不建悬空边) ②query CONNECTION-SIGNAL 分支: src 位节点 bus 父 (剥 [N]) 是 PORT_OUT → 位桥出口不 append、递归其内部驱动 (parent 属性不可靠, driver 建位节点 parent=None); fanin(top.y[3]) == fanin(top.u_sub.y[3]) (贯通 sub 内 y[3] 源 + 输入跨桥到顶层位 a[3]/b[3]); 残留: 切片/非零 base 偏移映射** | **✅ unit +3; 全量 3054 passed (serv 1 env 假失败同前); audit L3 #3 收窄** |
| **54** | **2026-09-05** | **L2** | **iter_119 slang 观察闭环: input Conversion 壳剥壳 (iter_136)** | **G2[0] input 连接缺失 (疑 slang 合并)** | **连接完整 + 观察定性** | **复现: 非 slang 合并 — 真身 = input 端口位宽≠连接位宽时 pyslang 包 ExpressionKind.Conversion, get_instance_connection 无剥壳分支 → signal_name '?' → 整条 conn 静默丢 (nested 4/4 a 侧缺; output 侧 Assignment 不受影响故 y 侧 iter_120 已修 / a 侧残留且无断言覆盖); 修: Conversion 链式剥壳 → _conn_expr_to_signal (RangeSelect→a[1:0]); unit +3; 全量 3051 passed (serv 1 env 假失败同前)** | **✅ slang 观察闭环; audit L3 反例 #5 移除** |
| **53** | **2026-09-05** | **L2** | **Accuracy Claim 落档 (iter_135, 方豆问询 "图=准确映射?")** | **能否说图一定是代码的准确映射** | **分层可核查声明** | **结论: 不能无限制说 (图 = 建模决策 + 范围限定 + 已知反例); audit 文档头部新增 📜 Accuracy Claim: L1 结构层 ✅ 已验证域 / L2 查询层 ✅ 限建模粒度语义 (总线/端口粒度停靠规则) / L3 深层语义层 ❌ 不承诺 (7 项反例 = inout 多驱动/interface 多写/A2 位对位/gate G2-G3/slang entry/semantic 消歧/CVA6 编译受阻 — 修一项移一项); 纯文档** | **✅ 无代码改动** |
| **52** | **2026-09-05** | **L2** | **嵌套 generate 深层重复段假节点清理 (iter_134, iter_133 backlog)** | **aes ROUND[1].U_ROUND.ROUND[1].U_SUB ×351 / cordic U.genblk1[i] ×105** | **假节点清零** | **gen_block 语义 = 实例**直接宿主** generate: hp 末段前一段形如 name[N] 才取 (祖先 generate 段是嵌套实例化展开的合法形态, 不再从 hp 任意位置取); 连带: wrapper cross 守卫 get_edge→get_edges 全查 (u_leaf.y→u_mid.y 双边误判无内部驱动致跨 entry) + PORT_OUT 有 wrapper_passthrough 驱动时显式递归追内部 deep (test_deep_hierarchy 回归暴露); aes 279/1116→0 / cordic 105→0; cordic truth 假路径→真路径** | **✅ unit +3; 全量 3048 passed (serv 1 env 假失败: HOME 重定向空 glob→空 filelist)** |
| **51** | **2026-09-05** | **L2** | **iter_131/132 真实复验 (iter_133)** | **真实设计验证查询修复 + 深层 generate 边界** | **复验通过 + backlog 登记** | **aes 4834 节点/272 实例: fanin 位隔离零跨 entry; 暴露嵌套 generate 深层重复段假节点 (ROUND[1].U_ROUND.ROUND[1].U_SUB, 351/4834=7.3%, baseline 既有, 主链 0 污染) — iter_109/110 宿主 ctx 更深边界, 登记 audit** | **✅ 复验通过; 🐛 新 backlog (iter_134 已修)** |
| **50** | **2026-09-05** | **L2** | **generate per-entry fanin 位隔离 (iter_132)** | **fanin(top.y[3]) 串入 G[0..2] (wrapper cross + A2 提升双根因)** | **位隔离** | **双修: ①A2 提升加 not has_incoming_conn (位节点有实例输出 CONNECTION = 有真实驱动源, 不提升到父总线) ②PORT_OUT via CONNECTION wrapper cross 加"无内部驱动才跨"守卫 (设计注释早有意图, 实现漏检查); fanin(y[i]) 恰 [G[i].u_leaf.y]; bus 聚合/wrapper/纯直通/xor 全保** | **✅ unit +3; 全量 2934 passed / 0 failed** |
| **49** | **2026-09-04** | **L2** | **真实验证 + usage 债务 (iter_130/131)** | **iter_126~129 副作用核查 / usage 4 失败** | **验证收尾 + 1 真回归修复 + 3 债务清理** | **iter_130: aes/CORDIC/CLI 零副作用 (worktree 基线对比); iter_131: dataflow _find_paths bus 查询首个非空候选即返 (iter_118 per-entry 后丢 req_i[1..7], arbiter 40→8→1) → 合并所有候选组合, 8 paths 恢复 + golden 同步; p6/m12/factory 3 债务** | **✅ unit +3; 主全量 2928 passed; usage 清零** |
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