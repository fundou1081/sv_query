# PLAN — 全局唯一计划树

> **唯一真相源**：sv_query **所有代码修改计划**只登记在本文件。
> 迭代记录（[docs/task_tree/iterations/](docs/task_tree/iterations/)）是**历史**；本文件是**现在做什么、做到哪**。
>
> 维护规则见 [AGENTS.md §2](AGENTS.md)；机械校验：`python3 tools/check_plan.py`。
>
> 格式（每行一项，子项用 `-- ` 前缀，id 全局唯一）：
> ```
> current item : P56.2 测试与文档 <已完成>
>
> P0 建图层与查询层的结构化拆分 <已完成>
> -- P0.1 图快照基线工具 <待做>
> ```
> 状态词表：`待做` / `进行中` / `已完成` / `阻塞` / `放弃`（只能这五个）。
> 父项可整体标 `进行中`（表示该组在做）；**叶子项**最多一项 `进行中`，
> 且当 `current item` 标为 `进行中` 时，它必须是那个叶子项。
> **全部完成时**：`current item` 可指向最后完成项并标 `已完成`（无 `待做/进行中/阻塞` 时才允许）。

## 当前项

current item : P62.2 交互式 debug（gate） <待做>

## 计划树

P0 建图层与查询层的结构化拆分 <已完成>
-- P0.1 图快照基线工具：图的节点/边 snapshot diff（拆 P0.2 的前提） <已完成>
-- P0.2 拆 `_trace_drivers_recursive`（343 行）：wrapper 跨实例 / 位级提升 / 自环分类 / q-d 互补 / 边过滤 / 源分类 六类规则拆成独立策略函数 <已完成>
-- P0.3 `GraphBuilder` 6 个后处理 pass 改声明式 pipeline（inputs/outputs，与 UnifiedTracer 一致） <已完成>
P1 视图层去双命名空间 <已完成>
-- P1.1 `visualize module` 换实例级边推导（不再依赖 MIG 的类型映射） <已完成>
-- P1.2 删 `ModuleInstanceGraph.port_to_internal` / `internal_to_port` / `get_internal_signal` / `get_port_path` <已完成>
P2 边缘场景补测 <已完成>
-- P2.1 位选跨模块 / interface 成员 / inout 三态 / class-struct 成员 的 drive-load 回归 <已完成>
P3 长期 backlog <已完成>
-- P3.1 `UnifiedTracer` 三个巨型私有方法（173 / 134 / 151 行） <已完成>
-- P3.2 缓存只有总量 LRU 上限，无"按工程过期" <已完成>
-- P3.3 [docs/EXP_IDEAS.md](docs/EXP_IDEAS.md) 的 10 条退役想法 —— 未来逐个重做 <已完成>

P57 ub-mode 纪律合并：复杂度棘轮门禁 + 术语表 <已完成>
-- P57.1 复杂度棘轮门禁 tools/check_crap.py（crapper 为唯一复杂度实现） <已完成>
-- P57.2 术语表 docs/GLOSSARY.md（四组归类，唯一命名处） <已完成>
-- P57.3 文档登记与检查器接入（WORKFLOW §5 / INDEX / REVIEW_CHECKLIST / CODING_STYLE §12） <已完成>
-- P57.4 提交与全量回归验证（独立分支，可撤销） <已完成>

P58 可视化重定位：结构审查与动态子图计划 <已完成>
-- P58.1 决策记录 + P59~P62 完整计划 <已完成>

P59 旧可视化资产清理 <已完成>
-- P59.1 资产盘点与冻结 <已完成>
-- P59.2 删除/归档旧命令与渲染器 <已完成>
-- P59.3 文档/测试/registry 收口 <已完成>

P60 graph subgraph 动态子图 <已完成>
-- P60.1 设计与 JSON schema <已完成>
-- P60.2 core 实现 <已完成>
-- P60.3 CLI/测试/文档 <已完成>

P61 结构审查 findings（对称性/typo） <已完成>
-- P61.1 结构特征与对称性检查 <已完成>
-- P61.2 finding schema + verify structural <已完成>
-- P61.3 测试/文档 <已完成>

P62 局部 review artifact / debug 交互 <进行中>
-- P62.1 finding 局部 SVG/HTML <已完成>
-- P62.2 交互式 debug（gate） <待做>

P63 class / constraint / covergroup 语义增强 <已完成>
-- P63.1 class relations 增强（约束块/covergroup 摘要） <已完成>
-- P63.2 trace constraints <已完成>
-- P63.3 trace covergroups/coverpoints/covergroup <已完成>
-- P63.4 测试与文档 <已完成>

P64 constraint 继承链 + rand 标记 <已完成>
-- P64.1 继承成员 CLASS_PROPERTY 升级 <已完成>
-- P64.2 constraint defined_in/inherited <已完成>
-- P64.3 rand 标记 + 测试/文档 <已完成>

P65 UVM sequence/factory 静态关系 <已完成>
-- P65.1 role + factory registration <已完成>
-- P65.2 factory_create/sequence_calls/p_sequencer <已完成>
-- P65.3 测试与文档 <已完成>

P66 语义提取 regex 纪律（仅 UVM 宏例外） <已完成>
-- P66.1 规则/检查器/方法调用 semantization <已完成>
-- P66.2 测试/文档/全量回归 <已完成>

P67 可用性验证包：性能 + 反幻觉 walkthrough <已完成>
-- P67.1 查询性能 harness + 3 设计 <已完成>
-- P67.2 反幻觉 CDC walkthrough <已完成>
-- P67.3 结果文档/README/回归 <已完成>

P68 README 项目描述校准 <已完成>
-- P68.1 定位/能力/验证状态同步 <已完成>

P69 长程结构查询对照基准 <已完成>
-- P69.1 对比矩阵/任务/评分协议 <已完成>
-- P69.2 4-task pilot + ground truth <已完成>
-- P69.3 12 题 + source 隔离 <已完成>
-- P69.4 12-task 准确率/成本报告 <已完成>
-- P69.5 token/tool-call 统计 <已完成>
-- P69.6 12-task seed2 + 软隔离 <已完成>
-- P69.7 硬隔离 12×2 fixed（P87；3rd seed 不做） <放弃>

P71 agent 查询可靠性修复 <已完成>
-- P71.1 --top + top_modules/top_ambiguous <已完成>
-- P71.2 driver_count 与 self-edge 对齐 <已完成>
-- P71.3 bit_fallback / top 字段显式化 <已完成>
-- P71.4 测试/契约/文档 <已完成>

P72 filelist 编译失败显式分类 <已完成>
-- P72.1 E_FILELIST_INCOMPLETE/INVALID + E_ELABORATION_FAILED <已完成>
-- P72.2 测试/文档 <已完成>

P73 项目目标/计划/测试缺口审计 <已完成>
-- P73.1 审计文档与下一步排序 <已完成>

P74 交互式 debug 场景 pilot <已完成>
-- P74.1 三场景 fixture + ground truth <已完成>
-- P74.2 连续追问 harness / 模型运行 <已完成>
-- P74.3 结果与场景评估 <已完成>

P75 covergroup bin_details 暴露 <已完成>
-- P75.1 CLI bin name/kind/values + contract/test <已完成>

P76 interactive debug 后续修复 <已完成>
-- P76.1 paths --canonical <已完成>
-- P76.2 未建模 control 显式 unknown <已完成>
-- P76.3 class relative name/scope 提示 <已完成>
-- P76.4 测试/契约/文档 <已完成>

P77 port-map ternary expression 子图 <已完成>
-- P77.1 AGENTS ub-mode + failing tests <已完成>
-- P77.2 PortBinding/lowering -> OP_TERNARY + BRANCH_* <已完成>
-- P77.3 trace/controlflow 读分支边 <已完成>
-- P77.4 文档/全量门禁 <已完成>

P78 P0：post-P77 deep_chain 行为验证 <已完成>
-- P78.1 3 模型 × 1 seed 重跑 <已完成>
-- P78.2 结果/失败点/下一步 <已完成>

P79 P1 交互式 debug 稳定性 <已完成>
-- P79.1 P1 harness + seed2 运行 <已完成>
-- P79.2 结果/稳定性/下一步 <已完成>

P80 实验资产盘点 <已完成>
-- P80.1 multi-turn / long-range / hard-isolation 清单 <已完成>

P81 long-range 统一 runner <已完成>
-- P81.1 run_long_range.py + hard sandbox <已完成>
-- P81.2 1 task smoke + 文档 <已完成>

P82 long-range 4-task pilot <已完成>
-- P82.1 4 题 × 2 模型 × 2 臂 × 2 seed <已完成>
-- P82.2 结果/失败点 <已完成>

P83 long-range 查询协议修复 <已完成>
-- P83.1 --depth 1 / queries / fact check <已完成>
-- P83.2 4 题 ×2 seed 复跑 <已完成>

P84 constraint/mux 邻域场景 <已完成>
-- P84.1 邻域 fixture + deterministic truth <已完成>
-- P84.2 agent pilot <已完成>
-- P84.3 结果/边界 <已完成>

P85 neighborhood source/T2 pilot <已完成>
-- P85.1 neighborhood runner + fact check <已完成>
-- P85.2 2 场景 ×3 模型 ×2 臂 ×2 seed <已完成>
-- P85.3 结果/决策 <已完成>

P86 统一双评分 <已完成>
-- P86.1 canonical + semantic scorer <已完成>
-- P86.2 bench 接入/测试/文档 <已完成>

P87 12-task fixed protocol <已完成>
-- P87.1 12-task fixed seed1 <已完成>
-- P87.2 seed2/汇总 <已完成>

P88 外部 VeriBug 验证（成本过高，跳过） <放弃>
-- P88.1 Icarus/VeriBug adapter 与小样本 <放弃>

P89 最终验证摘要 <已完成>
-- P89.1 能力边界/未验证项固化 <已完成>

P90 agent 查询成本归因 <已完成>
-- P90.1 3 任务 cold/warm 归因 <已完成>
-- P90.2 决策：暂停 serve/batch，先修 cache/telemetry <已完成>
-- P90.3 DSH session 真实 telemetry 调查 <已完成>

P91 大 filelist top-aware 裁剪 <已完成>
-- P91.1 保守 scanner + `filelist prune` CLI <已完成>
-- P91.2 AXI/SERV 实测与边界 <已完成>

P92 snapshot 预构建（D） <已完成>
-- P92.1 snapshot PathResolver + paths --from-snapshot <已完成>
-- P92.2 AXI/SERV 实测与边界 <已完成>

P93 A/D 充分测试 <已完成>
-- P93.1 prune fallback/边界测试 <已完成>
-- P93.2 snapshot/paths 一致性与 12-task pruned matrix <已完成>

P94 A+D vs 原版模型对比 <已完成>
-- P94.1 A+D T2 snapshot runner <已完成>
-- P94.2 12 题 seed1 对比/边界 <已完成>

P95 严格 A/D agent 协议 <放弃>
-- P95.1 repo deny + query-only workspace <放弃>
-- P95.2 24-cell 严格重跑 <放弃>

P96 sv_query skill pilot <已完成>
-- P96.1 通用 skill + 3-cell pilot <已完成>
-- P96.2 负结果/边界 <已完成>

P97 inline skill prompt pilot <已完成>
-- P97.1 skill 内容直接注入 prompt <已完成>
-- P97.2 3-cell A/B/负结果 <已完成>

P98 受限 svq_query 工具 pilot <已完成>
-- P98.1 DSH tool + patch（禁 bash/fs） <已完成>
-- P98.2 DeepSeek 3-cell pilot <已完成>
-- P98.3 12 题 ×2 模型 ×2 次 <已完成>

P99 Worker 辅助工具硬化 <已完成>
-- P99.1 compact.js/tests/README <已完成>
-- P99.2 重装 + 3-cell smoke <已完成>

P100 svq_query details / neighborhood <已完成>
-- P100.1 kind/condition/distance details <已完成>
-- P100.2 mux details probe <已完成>
-- P100.3 bounded neighborhood BFS <已完成>

P101 neighborhood condition schema <已完成>
-- P101.1 conditions + condition_atoms <已完成>
-- P101.2 mux depth5 条件复测 <已完成>

P102 Worker 辅助 BFS 测试 <已完成>
-- P102.1 可注入 queryFn 的 neighborhood.js <已完成>
-- P102.2 7 个 BFS Node tests + smoke <已完成>

P103 deep_chain tool probe <已完成>
-- P103.1 3-step path+neighborhood <已完成>
-- P103.2 负结果/边界 <已完成>

P104 granular path <已完成>
-- P104.1 path --all + 最细变体 <已完成>
-- P104.2 deep_chain 复测 <已完成>
-- P104.3 xor 语义边界 <已完成>

P105 svq_query evidence intent <已完成>
-- P105.1 file/line/source_context <已完成>
-- P105.2 deep_chain 7/7 复核 <已完成>

P106 evidence 默认关闭回归 <已完成>
-- P106.1 12 题 ×2 模型 evidence=false <已完成>

P107 Worker 辅助 evidence 测试 <已完成>
-- P107.1 evidence.js 注入式重构 <已完成>
-- P107.2 13 tests / 36 total <已完成>

P108 evidence=true 成本 <已完成>
-- P108.1 3-cell ×2 模型对照 <已完成>

P109 svq_query 默认决策 <已完成>
-- P109.1 opt-in profile，不做全局默认 <已完成>

P110 Blind realistic validation <已完成>
-- P110.1 首轮 blind/发现 path 默认 bug <已完成>
-- P110.2 fresh set 9/10，false-confident 0 <已完成>

P111 Snapshot/evidence 一键化 <已完成>
-- P111.1 setup_snapshot.py + env <已完成>
-- P111.2 新 snapshot e2e 10/10 <已完成>

P112 Explicit unknown/abstention 合同 <已完成>
-- P112.1 not_found/ambiguous/truncated <已完成>
-- P112.2 confidence + evidence 绑定 <已完成>

P113 Contract blind + interface fixes <已完成>
-- P113.1 5 contract tasks <已完成>
-- P113.2 F1-F4 contract fixes <已完成>
-- P113.3 deep_path + source-root inference <已完成>

P114 Fresh untouched blind validation <已完成>
-- P114.1 5 new tasks ×2 models <已完成>
-- P114.2 10/10, false 0 <已完成>

P115 10-task ×2-seed validation <已完成>
-- P115.1 10 new tasks ×2 seed <已完成>
-- P115.2 39/40 valid JSON, false 0 <已完成>

P116 Answer JSON format robustness <已完成>
-- P116.1 tolerant parser + json_repaired <已完成>
-- P116.2 P115 rescore 40/40 <已完成>

P117 Constrained verify claim <已完成>
-- P117.1 verify claim --from-snapshot <已完成>
-- P117.2 tool intent=verify <已完成>
-- P117.3 3 claims ×2 模型 6/6 <已完成>

P118 OpenTitan UART real-project pilot <已完成>
-- P118.1 filelist + snapshot <已完成>
-- P118.2 5 real tasks ×2 模型 <已完成>
-- P118.3 记录 edge-evidence 缺口 <已完成>

P119 Edge-level source evidence <已完成>
-- P119.1 snapshot edge source_location/expression <已完成>
-- P119.2 tool edge_evidence + source fallback <已完成>
-- P119.3 OpenTitan T3 复测 <已完成>
-- P119.4 trace evidence --from-snapshot edge fallback <已完成>

P120 OpenTitan T5 answer schema <已完成>
-- P120.1 explicit verify claims + status-only schema <已完成>
-- P120.2 T5 2/2 <已完成>

P121 OpenTitan continuous run <已完成>
-- P121.1 5 tasks ×2 模型连续跑 <已完成>
-- P121.2 9/10；canonical path 歧义 <已完成>

P122 Canonical path + runner hardening <已完成>
-- P122.1 path 默认 canonical <已完成>
-- P122.2 per-cell timeout/isolation <已完成>
-- P122.3 continuous 10/10 <已完成>

P123 OpenTitan I2C second-block pilot <已完成>
-- P123.1 i2c filelist/snapshot <已完成>
-- P123.2 3 tasks ×2 模型 6/6 <已完成>
-- P123.3 纠正 worker 两处语义误判 <已完成>

P124 Independent task intake <已完成>
-- P124.1 从 OpenTitan DV testplan/checklist 提取 3 个任务 <已完成>
-- P124.2 人工 spec/source ground truth <已完成>

P125 Execute independent intake tasks <已完成>
-- P125.1 修正 discovery/direct-driver/unknown/canonical schema <已完成>
-- P125.2 3 tasks ×2 模型执行 <已完成>
-- P125.3 决定 search/verify/stop <已完成>

P126 文档/运维刷新 <已完成>
-- P126.1 CURRENT_TODO 刷新 <已完成>
-- P126.2 TESTING 刷新 <已完成>
-- P126.3 EXTRACTION_COVERAGE / KNOWN_LIMITATIONS 刷新 <已完成>

P127 两个新增 DV-derived 任务 <已完成>
-- P127.1 UART TX override + I2C SDA interference <已完成>
-- P127.2 alias/root schema 修正 <已完成>

P128 Freeze v0.3.0-agent-query <已完成>
-- P128.1 freeze doc + tag <已完成>

P129 Clean-clone/tag install smoke <已完成>
-- P129.1 tag clone + setup_snapshot + query/verify smoke <已完成>

P130 冻结后长任务回归 + testbench 角可行性 <已完成>
-- P130.1 12-task regression 24/24 <已完成>
-- P130.2 OpenTitan TB 候选调查 <已完成>

P131 coverage limitation schema <已完成>
-- P131.1 builtin-shadow root cause <已完成>
-- P131.2 explicit CLI/schema limitation <已完成>
-- P131.3 strict regression tests <已完成>

P132 constraint neighborhood query <已完成>
-- P132.1 cross-block co-constraint graph <已完成>
-- P132.2 importance metrics <已完成>
-- P132.3 synthetic + I2C smoke <已完成>

P133 module/instance architecture graph <已完成>
-- P133.1 MIG ports + CONNECTION edges <已完成>
-- P133.2 JSON/DOT/SVG view <已完成>
-- P133.3 synthetic + I2C smoke <已完成>

P134 real-use three-scenario pilot <已完成>
-- P134.1 random→constraint→RTL <已完成>
-- P134.2 verify incl unknown <已完成>
-- P134.3 architecture/connection <已完成>
-- P134.4 fix architecture --json --svg <已完成>

P135 FIFO/bus connectivity <放弃>
-- P135.1 FIFO read/write boundary model <放弃>
-- P135.2 parent bus / bit-select aggregation <放弃>

P136 remaining real-use issues <已完成>
-- P136.1 false missing-file warning <已完成>
-- P136.2 architecture snapshot/cache <已完成>
-- P136.3 TB random → RTL snapshot join <已完成>
-- P136.4 unknown machine flag <已完成>
-- P136.5 solve…before / dist extraction <已完成>

P137 discipline remediation <已完成>
-- P137.1 semantic AST solve/dist (regex gate) <已完成>
-- P137.2 FIFO edge visibility centralized <已完成>
-- P137.3 warning/unknown/tb-join cleanup <已完成>
-- P137.4 check_crap commit range <已完成>

P138 Project adaptation policy <已完成>
-- P138.1 remove automatic FIFO inference <已完成>
-- P138.2 external adapter template <已完成>
-- P138.3 retain parent bus / bit aggregation <已完成>

P139 boundary-aware guided trace <已完成>
-- P139.1 trace frontier command <已完成>
-- P139.2 guided trace protocol <已完成>
-- P139.3 tests <已完成>
-- P139.4 worker validation nits <已完成>

P140 explicit-boundary guided trace <已完成>
-- P140.1 external boundary runner <已完成>
-- P140.2 I2C S1 replay <已完成>
-- P140.3 negative tests <已完成>
-- P140.4 worker validation nits <已完成>

P141 deep from/to scenarios <已完成>
-- P141.1 deep cross-module path tests <已完成>

P142 random constraint chain <已完成>
-- P142.1 trace constraint-chain <已完成>
-- P142.2 chain schema/tests <已完成>


## 已完成（保留最近记录，便于核查上一轮）

P5 位级 drive/load 精度修复 <已完成>
P6 表达式驱动的逐位映射 <已完成>
P7 位精确性扩展（续） <已完成>
P8 常量位分解 <已完成>
P9 signedness 建模与符号扩展 <已完成>
P10 整数类型位宽提取 <已完成>
P11 packed struct/union 宽度、signedness 与成员布局 <已完成>
P12 packed 成员位级查询桥 <已完成>
-- P12.1 成员位 → 聚合位换算（parent 链，struct/union/嵌套） <已完成>
-- P12.2 未被引用的成员节点补齐（查询可达） <已完成>
-- P12.3 测试与文档 <已完成>

P13 信号追踪能力补强（2026-10-27 评审 backlog） <已完成>
-- P13.1 缓存 key 纳入 SVQ_BIT_BRIDGE 模式（P0 静默错误） <已完成>
-- P13.2 粗粒度回退显式标记（precision/warnings） <已完成>
-- P13.3 capabilities bit_precision 契约 + 输出 is_signed/parent/bit_range <已完成>
-- P13.4 深层 packed 成员节点（o.inner.a） <已完成>
-- P13.5 三元/case 分支按位映射 <已完成>
-- P13.6 多驱动标记 + 静态 memory 位精度 <已完成>

P14 不可静态判定项显式标注 <已完成>
-- P14.1 动态 memory 索引显式 unknown（precision/dynamic_index） <已完成>
-- P14.2 测试与文档 <已完成>

P15 位级端点便捷入口 <已完成>
-- P15.1 `--bits` 归一化（paths/dataflow/impact；缺失回退总线 + 标记） <已完成>
-- P15.2 测试与文档 <已完成>

P16 动态索引递归传播 <已完成>
-- P16.1 图级动态传播（种子/下游/动态写污染/作用域解析/缓存） <已完成>
-- P16.2 测试与文档 <已完成>

P17 动态条件传播 <已完成>
-- P17.1 条件/时钟/复位/控制依赖传播（含计算条件、多边同对） <已完成>
-- P17.2 测试与文档 <已完成>

P18 可信性与测试入口补强（方豆 2026-10-29 排序：1→2→3，不做函数 inline/signed 逐位） <已完成>
-- P18.1 层次化条件作用域解析（u.q → 实例路径/端口，修动态漏标） <已完成>
-- P18.2 函数调用诚实标记（function_call + precision=unknown，不做 inline） <已完成>
-- P18.3 `--bits` 范围（3:0）与显式映射（src=1,dst=5） <已完成>
-- P18.4 全量测试与文档收尾 <已完成>

P19 函数条件诚实标记 <已完成>
-- P19.1 函数调用出现在 if/case/ternary/clock 条件（图上无结果节点）时标 function_call <已完成>
-- P19.2 测试与文档 <已完成>

P20 宏/动态拼接函数条件覆盖 <已完成>
-- P20.1 宏展开/令牌拼接/ifdef/DPI/层次函数在条件中的识别 <已完成>
-- P20.2 测试与文档 <已完成>

P21 真实工程查询 smoke <已完成>
-- P21.1 strict_uart/verilog-axi/picorv32 构建+查询+缓存冒烟 <已完成>
-- P21.2 smoke 工具/基线/文档 <已完成>

P22 fanin/fanout 条件输出 <已完成>
-- P22.1 driver/load 条件文本与条件信号输出（JSON 字段/过滤） <已完成>
-- P22.2 测试与文档 <已完成>

P23 路径条件组合 <已完成>
-- P23.1 depth>1 沿最短路径组合条件（含嵌套 chain） <已完成>
-- P23.2 测试与文档 <已完成>

P24 多路径条件 OR <已完成>
-- P24.1 枚举多路径 + per-path 原始条件保留 + OR 组合（含截断标记） <已完成>
-- P24.2 测试与文档 <已完成>

P26 遍历完整性与运行期系统函数 <已完成>
-- P26.1 fanin/fanout truncated_by_depth + cycles_detected（capped 三态） <已完成>
-- P26.2 $random/$urandom 等运行期系统调用标记（unknown） <已完成>
-- P26.3 测试与文档 <已完成>

P27 Agent JSON 契约 <已完成>
-- P27.1 capabilities json_contract（字段/版本/精度/错误） <已完成>
-- P27.2 契约测试与文档 <已完成>

P28 JSON 契约扩展 <已完成>
-- P28.1 paths/dataflow/impact/graph nodes/error_entry 契约 <已完成>
-- P28.2 测试与文档 <已完成>

P29 JSON 契约扩展（locate/evidence/controlflow） <已完成>
-- P29.1 graph edges/search/stats/trace evidence/controlflow analyze+list 契约 <已完成>
-- P29.2 测试与文档 <已完成>

P30 JSON 契约扩展（结构/元数据） <已完成>
-- P30.1 instances/hierarchy/ports/params/connections/class 契约 <已完成>
-- P30.2 测试与文档 <已完成>

P31 功能分层收敛：低完成度能力降级到 exp <已完成>
-- P31.1 audit/diagnose/view 降级到 exp + 默认隐藏（capabilities 默认不提供） <已完成>
-- P31.2 测试与文档 <已完成>

P32 trace evidence 稳定性 <已完成>
-- P32.1 evidence source_text/always 回退与字段一致性 <已完成>
-- P32.2 测试与契约 <已完成>

P33 Grounding P0：canonical signal identity <已完成>
-- P33.1 canonical resolver / not_found / ambiguous + resolved_signal <已完成>
-- P33.2 测试、JSON 契约与文档 <已完成>

P34 双向一致性与 claim verification <已完成>
-- P34.1 fanin/fanout/path/connection/bit 一致性检查 + verify 原语 <已完成>
-- P34.2 测试与文档 <已完成>

P35 include_control API 修复 <已完成>
-- P35.1 显式 unsupported + 测试与文档 <已完成>

P36 trace profile（波形关联元数据） <已完成>
-- P36.1 signal profile：clock/reset/sequential/source/bit/aliases <已完成>
-- P36.2 测试与契约 <已完成>

P37 evidence 粒度（driver/path） <已完成>
-- P37.1 per-driver/per-path evidence <已完成>
-- P37.2 测试与文档 <已完成>

P38 class 关系查询 <已完成>
-- P38.1 继承/成员/实例/方法调用链 relations <已完成>
-- P38.2 测试与文档 <已完成>

P39 波形路径联调 <已完成>
-- P39.1 waveform path lookup（严格完整路径/别名/位回退） <已完成>
-- P39.2 profile 类型/时钟边沿/复位语义增强 <已完成>
-- P39.3 测试与契约 <已完成>

P40 波形值语义（type/stage） <已完成>
-- P40.1 type/enum/struct/array 元数据 <已完成>
-- P40.2 sequential stage / 时间语义 <已完成>

P41 波形联调收尾 <已完成>
-- P41.1 struct member type <已完成>
-- P41.2 waveform manifest 联调输出 <已完成>

P42 波形路径别名收尾 <已完成>
-- P42.1 interface/modport connection 别名 <已完成>
-- P42.2 测试与文档 <已完成>

P43 generate 路径覆盖 <已完成>
-- P43.1 genblk 路径 lookup + generate scope type <已完成>
-- P43.2 测试与文档 <已完成>

P44 Scope 层收敛 <已完成>
-- P44.1 产品方向 scope/trace/verify 分层文档 <已完成>
-- P44.2 capabilities mode <已完成>
-- P44.3 scope 聚合命令 + canonical ID <已完成>
-- P44.4 测试与文档 <已完成>
-- P44.5 scope 可发现性（interface/generate/class） <已完成>

P45 模拟 waveform 端到端 <已完成>
-- P45.1 fixture: $root/generate/interface/modport/struct/bit <已完成>
-- P45.2 测试与修复 <已完成>

P46 其他功能收尾 <已完成>
-- P46.1 stats.modules 修正（模块清单） <已完成>
-- P46.2 测试与文档 <已完成>

P47 class member / UVM 可发现性 <已完成>
-- P47.1 语义推导 member candidates（不造图节点） <已完成>
-- P47.2 测试与文档 <已完成>

P48 条件化简 / 互斥 <已完成>
-- P48.1 L1 局部布尔化简 + 语法级互斥 <已完成>
-- P48.2 测试与文档 <已完成>

P49 全图证明级一致性 <已完成>
-- P49.1 全图 reciprocity（--full） <已完成>
-- P49.2 测试与文档 <已完成>

P50 bit-level consistency <已完成>
-- P50.1 bit parent/range/width/edge 结构检查 <已完成>
-- P50.2 测试与文档 <已完成>

P51 位选越界源头修正 <已完成>
-- P51.1 indexed part-select 归一化（+:/ -:） <已完成>
-- P51.2 multi-top 位选 namespace 修正 <已完成>
-- P51.3 直接表达式位展开 guard <已完成>
-- P51.4 测试与文档 <已完成>

P52 parent width 元数据 <已完成>
-- P52.1 定位 out_hdr_next width <已完成>
-- P52.2 定位 mem_done[1] <已完成>
-- P52.3 修正/测试/文档 <已完成>

P53 取实例 width <已完成>
-- P53.1 实例 body width 提取 <已完成>
-- P53.2 测试与文档 <已完成>

P54 generate parameter width 验证 <已完成>
-- P54.1 fixture + 文档 <已完成>

P55 generate if/case width 强化 <已完成>
-- P55.1 if/case 活跃分支 fixture <已完成>
-- P55.2 测试与文档 <已完成>

P56 generate if/case 嵌套 generate-for <已完成>
-- P56.1 嵌套 fixture/测试 <已完成>
-- P56.2 测试与文档 <已完成>
-- P11.1 聚合宽度/signedness（var/net/port，含嵌套） <已完成>
-- P11.2 成员宽度/位偏移（p.a → 4 位 + 在 p 中的位段） <已完成>
-- P11.3 测试与文档：聚合/成员矩阵 + 基线 <已完成>
-- P10.1 `integer/int/byte/shortint/longint/time` 位宽（syntax keyword + semantic bitWidth） <已完成>
-- P10.2 懒建节点宽度回填 + 缓存版本 <已完成>
-- P10.3 测试与文档：类型矩阵 + 图基线 <已完成>
-- P9.1 图节点 signedness：TraceNode.is_signed + adapter 提取 + 序列化/缓存版本 <已完成>
-- P9.2 查询层：有符号字面量 & 有符号信号扩展（符号位/零扩展） <已完成>
-- P9.3 测试与文档：signed/unsigned 扩展矩阵 + 图基线 <已完成>
-- P8.1 拼接字面量段逐位（`{a, 4'h0}`） <已完成>
-- P8.2 常量源切片值位（`y=4'hA` → 1'b1/1'b0） <已完成>
-- P8.3 测试与文档：常量/零扩展/位运算常量 <已完成>
-- P7.1 直接拷贝 `assign y=a` 的查询层位映射（one 模式也能位精确） <已完成>
-- P7.2 纯拼接 `{a,b}` 逐位映射（按表达式顺序 + 操作数宽度切段） <已完成>
-- P7.3 测试与文档：拷贝/拼接/多驱动/常量边界 <已完成>
-- P6.1 查询层 fanin：按运算符把 s[i] 映射到操作数位（同索引/前缀/移位） <已完成>
-- P6.2 查询层 fanout：按运算符把 a[i] 映射到结果位（前缀/移位） <已完成>
-- P6.3 测试与文档：运算符矩阵 + 粗粒度回落 + 不得跨位 <已完成>
-- P5.1 F1 缺位回退按位过滤（消切片/多驱动跨位污染） <已完成>
-- P5.2 F2 位节点死胡同补父总线追溯（消断链） <已完成>
-- P5.3 位级测试加强：逐位对应 + 负向污染/断链守卫 + 反例固化 <已完成>
-- P5.4 F3 slice 节点按位展开（LHS/RHS 切片 → 逐位节点 + 偏移映射） <已完成>
-- P5.6 F5 load 方向位精度（fanout 按位；表达式驱动需逐位边） <已完成>
-- P5.5 F4 bus↔无位节点侧合成位桥（one 默认 / full 可选；iter_293） <已完成>

P4 已完成归档 <已完成>
-- P4.1 单一命名空间收口：影子节点归零、extractor 4→2（iter_276） <已完成>
-- P4.2 删除 `port_to_internal` 自映射（iter_277） <已完成>
-- P4.3 `distance` 真实跳数 + 底座健壮性审计（iter_278） <已完成>

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-25 | 建立本计划树；P0~P3 来自底座审计结论（iter_278） |
| 2026-10-26 | P0/P1/P2/P3 全部完成（iter_279~288）；计划树进入"无待办"状态 |
| 2026-10-27 | P5~P12 位精确性系列完成（iter_289~300）；P13 评审 backlog 登记（iter_301，见 architecture/trace_capability_review_2026-10-27） |
