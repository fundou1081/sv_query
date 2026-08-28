# sv_query 架构改造 Todolist (长期追踪)

> **创建日期**: 2026-08-27 20:36
> **维护人**: QClaw Agent + 方豆
> **来源**: [ARCHITECTURE_REVIEW_2026-08-27.md](ARCHITECTURE_REVIEW_2026-08-27.md) §五
> **状态字段**: ⬜ pending / 🟡 in_progress / ✅ done / ⚠️ blocked / 🚫 won't_fix

## 🎯 7 项改造任务 (按 ROI 排序)

### #1 拆 driver_extractor (4101 行 → 10 个文件)  ✅
- **ROI**: 🔥🔥🔥 高
- **工作量**: 6 天 (实测, review 估 2-3 天是乐观)
- **状态**: ✅ **done (2026-08-28 20:45, 全部 9 步完成)**
- **目标**: 把 4101 行单文件拆成按语法类组织的子目录
- **子任务**:
  - [x] 盘点 driver_extractor 全部公开方法 (def 清单) — 67 顶层 + 11 嵌套 = 78 def
  - [x] 设计新目录结构: `src/trace/core/extractors/{assign, always, wire_init, function, case, ternary, bit_select, struct, generate, alias}_extractor.py`
  - [x] 设计 ExtractorResult 新协议 (按需扩展)
  - [x] G2 计划: 拆文件的具体切割点 + import 链 + 测试覆盖 — G2 plan 完成
  - [x] **Step 1+2: 拆 alias_extractor** (0.5 天, 极低风险) — commit `b6708b5`, 1461 tests 0 regression
  - [x] **Step 3: 拆 wire_init_extractor** (0.3 天, 完成核心) — commit `a2dac7c`, 1461 tests 0 regression. _create_var_nodes (22 行) 已拆, _create_net_decl_edges (~123 行) 依赖 7 个 helper, 留 Step 3b
  - [x] ✅ **Step 3b: 拆 _create_net_decl_edges → net_decl_extractor.py** (实际 0.5 小时, 非估计的 1+ 天) — 见 [iter_037](task_tree/iterations/iter_037_step3b_net_decl_extractor.md)
        - **更正原估计的错误前提**: 原写 "_build_signal_source 需先提到 _common"。实测 6 个直接依赖 (传递闭包 12 个 / 563 行) 是**全文件共享基础设施** (_get_signal 35 处调用 / _store_expr_tree 7 / _build_signal_source 6 / _append_edge 6 / _get_all_real_signals 5 / _ensure_signal_node 4), 搬走会波及 Step 4-7 未拆区域 → 改用 Step 1+2 已验证的 **Callable 依赖注入**, helper 定义留在原处
        - 顺手消除两段近乎逐行重复的循环 → 抽出 `_emit_driver_edges()` 共用
        - `driver_extractor.py` 3836 → **3754 行** (净减 82)
        - **验证**: integration 13→13 / cli 20→20 / unit 13→4 (全沙箱所致) / truth 4 passed = **0 回归**; 另写探针对比两条路径 (顶层 net decl + generate-for 展开) 输出 **byte-identical**
  - [x] ✅ **Step 4: 拆 assign_extractor (580 行: 5 方法 + 2 专属 helper)** — 见 [iter_038](task_tree/iterations/iter_038_step4_assign_extractor.md)
        - **闭包规模**: 31 方法 / 2028 行 (Step 3b 的 12/563 大一个量级)
        - **关键设计: 用 AssignHelpers dataclass 打包注入** (而非逐个 Callable) — 13 个共享 helper 一并打包, 调用方一次构造, 内部统一 `h.xxx` 访问, 避免 5 个 handler 签名膨胀到 15+ 行
        - 4 个 assign 专属 helper 随之搬走, 13 个共享 helper 仍留 driver_extractor (Step 5-7 共用)
        - **机械搬迁**: 50 行 Python 脚本按行号切分 + 规则转换 (self.→h. / handler 互调传 h=h), 0 处 self. 残留, 0 处遗漏
        - `driver_extractor.py` 3754 → **3211 行** (净减 543, 累计 #1 拆出 891 行)
        - **验证**: integration 13→13 / cli 20→20 / unit 13→4 (沙箱) / truth 4 passed = **0 回归**; 4 个 dispatch 分支 (concat/ ternary/ call/ binary+invocation) 探针 byte-identical; 历史 net_decl + generate-for 路径亦 byte-identical
  - [ ] ⚠️ **Step 4b: 拆 `_handle_normal_assign` (329 行)** ← 建议 (不与搬文件混, 单独 commit 便于归因)
  - [x] ✅ **Step 5: 拆 statement_flattener (8 方法/204 行)** — [iter_040](task_tree/iterations/iter_040_step5_statement_flattener.md)
        - 依赖极简: 仅 `_get_signal` (Callable 注入) + `_cond_ast_by_str` (参数传入, 非全局)
        - 6 个 visitor 纯模块内互调, 无外部依赖
        - `driver_extractor.py` 3211 → **3035 行** (#1 累计 -1066 行)
        - 验证: integration 13→13 / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed / flattener 全路径探针 (if/case/loop/timing) byte-identical
  - [x] ✅ **Step 6: 拆 always_extractor (9 方法/~790 行)** — [iter_041](task_tree/iterations/iter_041_step6_always_extractor.md)
        - **共享 helper 边界**: `_is_compile_time_symbol` / `_is_sv_literal_token` 被 always 块外的 `_expr_is_compile_time` / `_filter_signal_conditions_by_module` 共用 → 留 driver_extractor, 经 AlwaysHelpers 注入
        - `_create_always_edges` 453 行**只搬不拆** (行为重构留待独立 commit)
        - `driver_extractor.py` 3035 → **2292 行** (#1 累计 -1809 行)
        - 验证: integration 13→13 / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed / always 全路径探针 (ff+async reset / comb case / ternary) byte-identical
  - [x] ✅ **Step 7: 拆 function_extractor (7 方法/648 行)** — [iter_042](task_tree/iterations/iter_042_step7_function_extractor.md)
        - 共享边界: `_get_signal` / `_subroutine_expander` 注入; `_get_all_signals` 随模块搬走
        - `_find_invocations` / `_handle_invocation` / `_get_all_signals` / `_get_constructor_call` 在 driver_extractor 留薄壳 (Assign/AlwaysHelpers 注入点引用)
        - `driver_extractor.py` 2292 → **1685 行** (#1 累计 -2416 行)
        - 验证: integration 13→13 (修 staticmethod 前 44) / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed / function+task 探针 byte-identical
  - [x] ✅ **Step 8: 删除死代码 (4 方法/255 行)** — [iter_043](task_tree/iterations/iter_043_step8_dead_code_removal.md)
        - 死代码: `_expand_and_append_assignment` (85) / `_collect_assignments_from_stmt` (98) / `_legacy_collect_stmts_with_context` (22) / `_extract_condition_str` (50)
        - **关键**: 1687 行剩余的是共享 helper + 薄壳 (被 extractor 注入), 真正能删的是死代码
        - 第一次删除误删 extract() → 加 extract 保护后重删
        - `driver_extractor.py` 1687 → **1432 行** (#1 累计 -2669 行)
        - 验证: integration 13→13 / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed / 4 探针 byte-identical
  - [x] ✅ **Step 9: 全套最终回归 — #1 收官** — [iter_044](task_tree/iterations/iter_044_step9_final_regression.md)
        - 全套: truth 4 passed / integration 13 (先期) / cli 20 (先期) / unit 4 (沙箱) = **0 回归**
        - **6 探针全部 byte-identical**: assign 4 分支 / flattener / always / function / net_decl / generate-for
        - 最终: driver_extractor **4101 → 1431 行** (净拆 2670 行 / 65%)

### #2 统一 BitSelectHandler (去重 graph_builder 那套)  ✅
- **ROI**: 🔥🔥 中高
- **工作量**: 1 天
- **状态**: ✅ **done (2026-08-28 11:40)** — 两条路径均改用 semantic API, silent fallback 清零, 0 回归
- **目标**: ~~选一套保留, 另一套标 deprecated~~ → **改为: 两套都改用 pyslang semantic API 替代 regex** (G3 选项 3)
- **决策记录**: [architecture/bitselect_semantic_api_decision.md](architecture/bitselect_semantic_api_decision.md) / [iter_035](task_tree/iterations/iter_035_bitselect_semantic_api_decision.md) / [iter_036](task_tree/iterations/iter_036_bitselect_g3_cleanup.md)
- **子任务**:
  - [x] 对比两套实现的输出 diff (golden fixture 跑两次) — 完成, 见 `sim/tests/integration/test_bitselect_handler_diff.py`
  - [x] 边界 fixture 实测 (parameter / generate / nested / struct) — 完成 06:33
  - [x] **G3 决策 = 选项 3 (pyslang semantic API 替代 regex)** — 方豆 06:36 "走 g3 的 3" + 07:46 "选择 semantic api"
  - [x] 路径 B 改造: `_common.iter_bit_selects` / `BitSelectHit` / `_PyslangSelectWalker` + `graph_builder` 接入 — ✅ 提交 `bec0f51`
  - [x] ✅ **修 for-loop / generate-for 驱动源丢失** — `hit.full_id` 保留 `[i]`, 不再生成 `[?]` placeholder. **复核确认真修复** (测试文件未被改动, 断言原样通过)
  - [x] ✅ **重新生成 golden** (18 JSON) — 在**真 bug 修复之后**执行, 顺序正确
  - [x] ✅ **修 silent fallback `_common.py`** — 查证 pyslang 是核心依赖 (pyproject/requirements 硬声明, 全仓另 12 处均直接 import), `try/except`+`_HAS_PYSLANG` 全删, 改显式 import + `raise ValueError`
  - [x] ✅ **路径 A 改造 `bit_select_handler.py`** — `_create_hierarchical_bit_nodes` 改用同一个 `iter_bit_selects` helper, 模块级 `import re` 删除, 新增 `_get_pyslang_root()` 显式报错
  - [x] ✅ **额外修复**: `graph_builder` 的 `if pyslang_root is None: return` 同属 silent fallback (iter_035 漏标), 一并改显式 raise
  - [x] ⚠️ **更正**: `graph_builder.py:442` 的 `import re` **不是位选残留** — 属 `_collect_struct_members()` 拆 `parent.member`, 与位选无关, **保留**
- **G2 实测发现 (06:33 更新)**:
  - 边/节点存在性一致 (0 差异)
  - 唯一差异: RangeSelect 节点 4 个属性 (bit_range / parent_bit_* / width) 路径 B 漏设
  - 🆕 边界 fixture 额外发现:
    - Parameter 位选 (`data[W-1:0]`): pyslang elaboration 折叠 W-1→7, 正常
    - Generate-for 动态位选 (`acc[i]`): 🔴 不产生 BIT_SELECT 边, 是 #8 新项
    - Nested 位选: SV 非法, pyslang 报错
    - Struct 字段位选 (`pkt.addr[3:0]`): 正常
    - **regex 实际比想象鲁棒** (pyslang 折叠 + struct 前缀可匹配)
  - 🆕 **新架构债**: 两套实现完全不用 pyslang API, 全 regex
- **G3 选项 (06:33 更新)**:
  1. **复制路径 A 到路径 B (推荐, 0.5 天)** — 修 #2 真实 bug, 风险低
  2. 删路径 A 的 _create_hierarchical_bit_nodes (1 天) — 中风险
  3. **用 pyslang API 替代 regex (1-2 天)** — 治本, 但风险高
  4. 纯文档说明 (0.1 天) — 不修 bug
  5. **选项 1 + 新建 #8 修 generate-for 动态位选** (推荐, #2 0.5 天 + #8 1+ 天)
- **产出**: [docs/BITSELECT_HANDLER_G2_PLAN.md](BITSELECT_HANDLER_G2_PLAN.md)
- **依赖**: 无

### #3 建 EXTRACTION_COVERAGE.md 总表  ✅
- **ROI**: 🔥🔥 中高
- **工作量**: 半天 (估)
- **状态**: ✅ **done (2026-08-27 23:48)** — commit pending
- **目标**: 33 种 SV 语法 × 5 档支持 (✅/⚠️/🔶/❌/🔸) × 对应 fixture × 对应 test 的总表
- **子任务**:
  - [x] 从 `memory/2026-08-27.md` Phase 1A 矩阵抽 33 种语法
  - [x] 对每种语法填: 支持度 / fixture 路径 / test 路径 / 已知限制 / 实施建议
  - [x] 把现有 7 个 spec_golden fixture + 32 个 orphan_regression + 30+ golden_dataflow + 7 demo = 101 fixture 全标上
  - [x] 链接 SV_SYNTAX_MAPPING.md + PYSLANG_SEMANTIC_USAGE.md + SIGNAL_GRAPH_SPEC.md
  - [x] **修正 2 个 Phase 1A 误报**: alias 方向 (Bug #1) + function 递归 (Bug #4), 加 "🟢 已确认误报修正" 章节
- **产出**: [docs/EXTRACTION_COVERAGE.md](EXTRACTION_COVERAGE.md) (7814 bytes, 33 语法 × 5 档)
- **依赖**: 无

### #4 建 docs/EXTRACTION_FAILURES.md 集中表  ⬜
- **ROI**: 🔥 中
- **工作量**: 1 天
- **状态**: pending
- **目标**: 集中记录所有已知 fallback 路径 + 触发条件 + 用户如何避免
- **子任务**:
  - [ ] grep 全部 silent fallback / try-except-pass / sentinel default 模式
  - [ ] 分类: API fallback / 端口 fallback / 表达式 fallback / 位宽 fallback / 等等
  - [ ] 每条写: 位置 / 触发条件 / 行为 / 修复建议
  - [ ] 跟 Bug #2/#3 (刚修的) 关联
- **依赖**: 无

### #5 UnifiedTracer 20 步管线 → 依赖图  ⬜
- **ROI**: 🔥 中
- **工作量**: 2 天
- **状态**: pending
- **目标**: 引入显式依赖声明 (类似 Airflow DAG), 让每步声明 inputs/outputs
- **子任务**:
  - [ ] 盘点 20 步的真正依赖关系 (哪些可并行 / 哪些必须串行)
  - [ ] 设计 PipelineStep 协议 (input_keys / output_keys)
  - [ ] 重构 UnifiedTracer.build_graph 用 DAG 拓扑排序
  - [ ] 测试: 故意打乱顺序看是否报错
- **依赖**: 无

### #6 expression tree 提取独立成 builder  ⬜
- **ROI**: 🟡 低中
- **工作量**: 2 天
- **状态**: pending
- **目标**: driver_extractor 只负责"原始 driver 边", 表达式树/常量/函数信息独立
- **子任务**:
  - [ ] 找 driver_extractor 里所有写 expr_trees/const_map/func_info 的位置
  - [ ] 抽到独立 extractor
  - [ ] ExtractorResult 协议加 build 顺序约束
  - [ ] 回归
- **依赖**: 跟 #1 (拆 driver_extractor) 部分重叠, 建议 #1 完成后做

### #7 迁 pyslang 11.0 native API  ⬜
- **ROI**: 长期高
- **工作量**: 1-2 周
- **状态**: pending
- **目标**: 用 `inst.hierarchicalPath` / `inst.portConnections` / `inst.body` 替代自建 MIG
- **子任务**:
  - [ ] 评估 11.0 native API 在 CVA6/coralNPU/darkriscv/zipcpu/riscv_core/vortex 上的等价性
  - [ ] 写 native API vs 自建 MIG 的 diff 验证脚本
  - [ ] G3 计划: 替换点 + 风险 + 回退策略
  - [ ] 实施 (分批: 先 hierarchicalPath, 再 portConnections, 再 body)
  - [ ] 性能 benchmark (预期 4x speedup)
  - [ ] 回归全套
- **依赖**: MEMORY.md 2026-06-25 用户指示 "先记录下来", 等你后续触发

---

## 📊 进度总览

| # | 任务 | ROI | 状态 | 启动 | 完成 |
|---|---|---|---|---|---|
| 1 | 拆 driver_extractor | 🔥🔥🔥 | ✅ done | 20:38 | 20:45 (4101→1431 行) |
| 2 | BitSelect 改 semantic API | 🔥🔥 | ✅ done | 06:23 | 11:40 (两路径 + fallback 清零) |
| 3 | EXTRACTION_COVERAGE.md | 🔥🔥 | ✅ done | 23:48 | 23:48 |
| 4 | EXTRACTION_FAILURES.md | 🔥 | ⬜ pending | — | — |
| 5 | 管线 → 依赖图 | 🔥 | ⬜ pending | — | — |
| 6 | expression tree 独立 | 🟡 | ⬜ pending | — | — |
| 7 | pyslang 11.0 native API | 长期高 | ⬜ pending | — | — |
| 8 | generate-for 动态位选 | 🔥 | ✅ done | 08-28 | 21:30 (BIT_SELECT+DRIVER+CLOCK 边) |

**总进度**: **#1 ✅ done**; #2 ✅ done; #3 ✅ done; **#8 ✅ done (2026-08-28 21:30)**; 其他 4 项 pending. **总 4/8 (50%)**.

---

## 🔄 状态变更日志

- **2026-08-27 20:36** — todolist 创建, 7 项 pending. 启动 #1 拆 driver_extractor 计划.
- **2026-08-27 20:38** — #1 启动 Step 1+2 (alias_extractor), G2 plan 完成. 预计 6 天总工作量.
- **2026-08-27 21:33** — #1 Step 3 完成 (commit `a2dac7c`). _get_signal/_fold_constant/_create_var_nodes 拆出, driver_extractor 净减 262 行 (-6.4%). 新增 Step 3b 后续处理 _create_net_decl_edges.
- **2026-08-27 23:46** — todolist 进度总览表修正 (之前显示 0/7 但实际 #1 已 in_progress). 修后续梳理下一步.
- **2026-08-27 23:48** — #3 EXTRACTION_COVERAGE.md 完成 (7814 bytes, 33 语法 × 5 档 × 101 fixture). 修正 2 个 Phase 1A 误报 (alias 方向 / function 递归). 总进度 1.5/7 (21%).
- **2026-08-28 06:23** — #2 G2 计划 + diff 验证脚本完成. 实测 3 fixture × 2 路径, 边/节点存在性完全一致, 唯一差异是 RangeSelect 节点 4 个属性路径 B 漏设. G3 待决策 (4 选项, 推荐选项 1, 0.5 天). 总进度 2/7 (28.5%).
- **2026-08-28 06:33** — #2 加 4 边界 fixture (parameter / generate / nested / struct). 修正结论: regex 比想象鲁棒; 真实额外 bug 是 generate-for 动态位选 (新建 #8). 新架构债: 两套实现全 regex, 未用 pyslang API. G3 选项扩到 5 个 (新增选项 3 pyslang API 治本 + 选项 5 推荐 #2+#8 组合).
- **2026-08-28 07:46** — #2 **G3 决策确认 = 选项 3 (pyslang semantic API 替代 regex, 治本)**. 方豆 06:36 "走 g3 的 3" + 07:46 "选择 semantic api" 两次指示. 归档 [决策记录](architecture/bitselect_semantic_api_decision.md) + [iter_035](task_tree/iterations/iter_035_bitselect_semantic_api_decision.md).
  - **核实 WIP 状态**: 前一 session 已按 06:36 指示开工但**未提交、未记录文档** — 路径 B 已改造 (`_common.py` +492 行 / `graph_builder.py` +145 行), 路径 A 未动.
  - **实测**: bitselect 相关 12 passed / 1 failed (失败项 fixture 是非法 SV, 非代码缺陷); case27 1to1 truth 4 passed.
  - **A/B 回归对照 (git stash)**: 带 WIP 33 failed / 干净 HEAD 亦 33 failed — **WIP 引入 0 回归**. 33 项失败根因是 `~/.svq/cache` 在 AI 沙箱外不可写 (`ast_cache.py:30` 用 `Path.home()`), 属执行环境限制, 非项目缺陷.
  - 🔴 **发现纪律违规**: `_common.py:441` `if not _HAS_PYSLANG: return  # 退化: 让调用方走 regex 老路径` — 违反核心纪律 #2 "禁止 fallback". 待修.
  - 🔴 **选项 3 仅完成一半**: 路径 A (`bit_select_handler.py:290`) 仍是 regex.
- **2026-08-28 07:50** — #2 **补充核实, 更正 07:46 的错误结论**.
  - 期间另一 agent (QClaw) 并行完成实现, 产出 `BITSELECT_HANDLER_G3_OPTION3_REPORT.md` (报 8 regression).
  - **更正 1**: 07:46 "0 回归" 是**误判** — 当时只跑 `unit + cli`, **漏跑 integration**. 重测 integration A/B: 带 WIP 25 failed vs 干净 HEAD 16 failed → **净引入 9 个回归** (QClaw 报 8, 实际 9).
  - **更正 2**: QClaw "全部是 golden 比对差异" **不成立**. `test_for_loop_in_always` / `test_generate_for` 是**功能断言**失败: 驱动源 **1 → 0**, 即 for-loop/generate-for 内位选驱动关系被弄丢. `test_golden_risk_strict_uart` 风险项 25 → 28.
  - ⚠️ **故 QClaw 建议的"重新生成 golden"不可直接采纳** — 会把真 bug 固化成 baseline, 违反 "禁止为通过而改 assertion/golden".
  - ✅ 单元测试 A/B: 13 failed vs 13 failed, **0 新增**; `case27_1to1_truth` 4 passed.
- **2026-08-28 08:28** — #2 **提交 `bec0f51`** (方豆指示 "重新生成 golden, 覆盖全一些").
  - 先**修真 bug** 再重录 golden: 符号下标 (`q[i]`/`out[i]`) 改用 `hit.full_id` 保留 `[i]`, 不再生成 `[?]` placeholder 节点; 无 target_module 时用首 top instance 名前缀匹配 DriverExtractor.
  - 重新生成 18 个 golden JSON (subfunction 16 + cdc_risk 2).
- **2026-08-28 11:20** — #2 **独立复核 (git worktree A/B 对照), 确认可信**.
  - 方法: 在父提交 `49b475c` 建独立 worktree 做基线, 与 `bec0f51` 对比 integration.
  - **结果: 23 failed → 13 failed, 净引入 0 回归, 修好 10 个**. 7:50 报告的 9 个回归已全部清零.
  - ✅ **关键验证: for-loop/generate-for 是真修复而非掩盖** — `test_advanced_grammar.py` **测试文件本身未被该 commit 改动** (`git show --stat` 为空), 断言原样通过, 排除"为通过改 assertion"。golden 重录发生在真 bug 修复**之后**, 顺序正确.
  - 剩余 13 个 integration 失败均**先期存在**且与 #2 无关 (nested 非法 SV / human_output × 5 / tree_output × 5 / real_project_viz × 2).
  - ⚠️ `sim/tests/unit` 13 failed 是 **AI 沙箱限制** (子进程 CLI 写 `~/.svq/cache` 被拒), 非代码缺陷, 方豆本地应全绿.
  - 🔴 **仍未完成**: silent fallback (`_common.py:440-441`) + 路径 A regex (`bit_select_handler.py:305`) + `graph_builder.py:442` 残留 `import re`.
- **2026-08-28 11:40** — #2 **✅ 完成** (iter_036). G3 选项 3 两条路径全部落地:
  - **路径 A** (`bit_select_handler.py`) 改用 `_common.iter_bit_selects`, 模块级 `import re` 删除 — 至此位选 regex 反推**彻底消失**.
  - **silent fallback 清零**: 查证 pyslang 为核心依赖 (pyproject/requirements 硬声明 + 全仓另 12 处直接 import, 0 处 try/except), 原 `_HAS_PYSLANG` 开关前提不成立, 全删改显式 import; `iter_bit_selects(module=None)` 与 `graph_builder` 的 `pyslang_root is None` 均由静默 return 改 `raise ValueError`.
  - **额外修复**: `graph_builder` 那处 silent fallback 是 iter_035 漏标的同类问题.
  - ⚠️ **更正 iter_035 的误判**: `graph_builder.py:442` 的 `import re` 属 `_collect_struct_members()` 拆 `parent.member`, **与位选无关, 保留不删**.
  - **回归 (worktree A/B, 基线 `bec0f51`)**: integration 13→13 (0 回归), cli 23→**20** (0 回归, 另修好 3 个 `test_visualize_graph_source`), unit 13→13 (全沙箱所致), `case27_1to1_truth` 4 passed.
- **2026-08-28 15:20** — #1 **Step 3b 完成** (iter_037). 拆 `_create_net_decl_edges` (110 行) → `extractors/net_decl_extractor.py`.
  - **更正遗留估计**: 原注释写 "依赖 7 个 helper, 1+ 天, _build_signal_source 需先提到 _common"。实测直接依赖 6 个 / 传递闭包 12 个 (563 行), 但这些是**全文件共享基础设施** (_get_signal 35 处调用), 搬走会牵动 Step 4-7 未拆区域 → 沿用 Step 1+2 的 **Callable 依赖注入**模式, 实际耗时 **0.5 小时**。
  - 顺手消除原函数两段近乎逐行重复的循环 (顶层 net decl / generate-for 展开), 抽出 `_emit_driver_edges()`。
  - `driver_extractor.py` **3836 → 3754 行** (净减 82)。
  - **验证**: integration 13→13, cli 20→20, unit 13→4 (剩余全部 `Operation not permitted` 沙箱所致), truth 4 passed → **0 回归**。另写探针 A/B 对比两条代码路径输出 **byte-identical**, 特别确认 generate-for 的 3 个 `gen_accum[N].prod` 仍是独立节点 (Plan G3 历史 bug 高发点)。
- **2026-08-28 16:10** — #1 **Step 4 完成** (iter_038). 拆 `_create_assign_edges` + 4 个 sub-method + 2 个 assign 专属 helper (580 行) → `extractors/assign_extractor.py`.
  - **闭包规模**: 31 方法 / 2028 行 (Step 3b 的 12/563 大一个量级)
  - **关键设计: 用 `AssignHelpers` dataclass 打包注入** (而非逐个 Callable) — 13 个共享 helper 一并打包, 调用方一次构造, 内部统一 `h.xxx` 访问。这与 Step 1+2/3b 用的逐个 Callable 是**同源但不同规模**的方案: 2-6 个依赖时前者更显式, 13 个依赖时后者签名不膨胀。判定标准是"handler 签名能否保持 ~50 行阈值"
  - 4 个 assign 专属 helper 随之搬走, 13 个共享 helper 仍留 driver_extractor (Step 5-7 共用, 不能提前搬)
  - **机械搬迁**: 50 行 Python 脚本按行号切分 + 规则转换 (self.→h. / handler 互调自动传 h=h), 0 处 self. 残留, 0 处遗漏
  - `driver_extractor.py` 3754 → **3211 行** (净减 543, #1 累计拆出 891 行 / 4101 → 3211)
  - **验证**: integration 13→13 / cli 20→20 / unit 13→4 (沙箱) / truth 4 passed = **0 回归**; 4 个 dispatch 分支 (concat/ ternary/ call/ binary+invocation) 探针 byte-identical; 历史 net_decl + generate-for 路径亦 byte-identical
  - `_handle_normal_assign` 329 行**未动** (行为重构不与搬文件混 commit, 单独留 Step 4b)
- **2026-08-28 17:30** — #1 **Step 4b 完成** (iter_039). 拆 `_handle_normal_assign` (329 行) → 4 个具名 helper.
  - 主函数 **329 → 33 行** (含 docstring), 仅保留控制流调度
  - 4 个 helper: `_prepare_lhs_and_dst` (53) / `_resolve_rhs_signals` (78) / `_build_ternary_edge_signals` (183) / `_build_simple_edge_signals` (62)
  - **诚实标注**: 实施中 2 个失误 (早期 return 改 4 元组 + 漏写 helper 末尾 return), 当场测试发现, 未污染 commit
  - 验证: integration 13→13 / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed / 4 dispatch 探针 byte-identical
  - 183 行的 `_build_ternary_edge_signals` 仍超 AGENTS.md ~50 行阈值, 但合理: 含 3 个递归嵌套 helper 共 60 行, 主体调度而非单层复杂度
- **2026-08-28 18:20** — #1 **Step 5 完成** (iter_040). 拆 8 个 `_flatten_*` 方法 (204 行) → `extractors/statement_flattener.py`.
  - 依赖极简: 仅 `_get_signal` (Callable 注入) + `_cond_ast_by_str` (作为参数传入, 非全局单例 — 遵守纪律 #2)
  - 6 个 visitor 纯模块内互调, 无外部依赖
  - `driver_extractor.py` 3211 → **3035 行** (#1 累计 -1066 行)
  - 验证: integration 13→13 / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed; flattener 全路径探针 (if/else + case + for loop + timing, 19 边/11 节点) byte-identical
  - 实施中 3 次小修正 (参数转发 / StatementKind import / 薄壳函数名下划线), 均当场测试暴露
- **2026-08-28 19:10** — #1 **Step 6 完成** (iter_041). 拆 always 相关 9 个方法 (~790 行) → `extractors/always_extractor.py`.
  - **共享 helper 边界**: `_is_compile_time_symbol` / `_is_sv_literal_token` 被 always 块外的 `_expr_is_compile_time` / `_filter_signal_conditions_by_module` 共用 (assign/always/function 三处), 不能搬走 → 留 driver_extractor, 经 AlwaysHelpers 注入
  - `_create_always_edges` 453 行**只搬不拆** (行为重构留待独立 commit, 与 Step 4b 同策略)
  - `driver_extractor.py` 3035 → **2292 行** (#1 累计 -1809 行)
  - **诚实标注**: 删除区间吞掉了下一个方法的 `@staticmethod` 装饰器 → 25 个测试失败, 错误信息 `takes 1 positional argument but 2 were given` 直接定位, 加回即修复
  - 验证: integration 13→13 (修复前 38) / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed; always 全路径探针 byte-identical
- **2026-08-28 19:55** — #1 **Step 7 完成** (iter_042). 拆 function/task 相关 7 个方法 (648 行) → `extractors/function_extractor.py`.
  - 共享边界: `_get_signal` / `_subroutine_expander` 注入; `_get_all_signals` 随模块搬走
  - **4 个方法在 driver_extractor 留薄壳** (`_find_invocations` / `_handle_invocation` / `_get_all_signals` / `_get_constructor_call`) — 因 Assign/AlwaysHelpers 注入点引用
  - `driver_extractor.py` 2292 → **1685 行** (#1 累计 -2416 行)
  - **诚实标注**: `_parse_bit_range` 的 `@staticmethod` 被删区间吞掉 (**Step 6 同类错误第 2 次**), 31 个测试失败; 用基线对比法系统检查确认无其他丢失
  - 验证: integration 13→13 (修复前 44) / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed; function+task 探针 byte-identical
- **2026-08-28 20:20** — #1 **Step 8 完成** (iter_043). 删除 4 个真死代码方法 (255 行).
  - `_expand_and_append_assignment` (85) / `_collect_assignments_from_stmt` (98) / `_legacy_collect_stmts_with_context` (22) / `_extract_condition_str` (50) — 全仓无调用者
  - **澄清 Step 8 含义**: 1687 行剩余的是共享 helper + 薄壳 (被 6 个 extractor 注入), 真正能删的是死代码
  - **诚实标注**: 第一次行号区间删除误删 extract() → 7 个测试失败; 改用 extract 保护 (区间内含 def extract 则跳过) 后重删
  - `driver_extractor.py` 1687 → **1432 行** (#1 累计 -2669 行)
  - 验证: integration 13→13 / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed; 4 探针 (assign/flatten/always/function) 全部 byte-identical
- **2026-08-28 20:45** — #1 **Step 9 完成, 全部 9 步收官** (iter_044).
  - 全套回归: truth 4 passed / integration 13 (先期) / cli 20 (先期) / unit 4 (沙箱) = **0 回归**
  - **6 探针全部 byte-identical** (assign/flattener/always/function/net_decl/generate-for)
  - 最终: driver_extractor **4101 → 1431 行**, 净拆 2670 行 (65%) 到 7 个独立模块
  - **9 个迭代经验沉淀**: 共享 helper 不跟业务搬 / 注入多打包 dataclass / 搬与重构分 commit / 行号删除要保护 / 行为等价要探针 / 死代码要全仓搜
- **2026-08-28 21:30** — **#8 done** (iter_045). 修 generate-for 动态位选.
  - **调查发现**: BIT_SELECT 边部分已被 #2 semantic API 顺带修复 (G2 时代 0 条 → 当前 5 条); 真正剩余的是 DRIVER 边缺失
  - **根因**: `get_always_blocks` 不枚举 generate 内 always 块 + `find_assignments` 缺 Timed/Block/List/ExpressionStatement 分支导致 `_genvar_context` 永不填充 + `acc[i]` 无法 substitute
  - **修复**: find_assignments 补 4 分支 + `_iter_children` 加 stmt/list 属性 + get_assignments 保持只返回 continuous + always_extractor 遍历 generate always + genvar 注入 (消费侧真实 id 登记)
  - **验证**: 全套 0 回归 / 6 探针 byte-identical / 新测试 `test_generate_for_dynamic_bitselect` 有效 (revert 修复即失败)
