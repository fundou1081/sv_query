# AGENT_FEATURE_MAP — core 层 JSON 能力地图

> **读者**: 正在决定"下一步该调哪个稳定命令"的 agent 开发者。
> **范围**: 只收 `core` 层、带 `--json`、声明稳定 schema 的命令。
> **明确排除**: `exp` / `view` / `dev` / `out` 四层（`audit`、`diagnose`、
> `trace overview`、`review render`、`architecture graph` 等均不在此表）。
> **快照**: 本文基于 `8a8afe5c`（P141/P142）并经 P143 校验（`trace constraint-chain` mode 修正为 `trace`）
> 实测，数据源见文末「来源」。
> **写法**: 中文说明 + 英文命令/字段名；所有字段均与真实 CLI 输出核对过，
> 未核对的推测一律放进「Unresolved」，不写成事实。

---

## 0. 一分钟结论

1. 先跑 `sv_query capabilities --json`。它是命令面唯一真相源，含
   `layer/group/mode/cost/json/stateful/recommended/schema_version`。
2. `core` 共 **40** 个命令，`schema_version = "1"`（层级声明）。
3. **判断成功看 `ok`，不要只看 exit code**：`drivers` 对未知信号返回
   `ok:false` 但 exit code 仍为 0。
4. 图里"没有这条关系"用 `found:false`；"端点根本不存在"用 `ok:false`
   （或 `status:unknown`）。两者语义不同。
5. `trace constraint-*` 是 **co-membership / co-constraint 图**，
   不是 solver 证明；`trace frontier` 是**断点报告**，不做 FIFO 分类。
6. core 不自动推断项目语义。跨 FIFO/自定义边界必须走
   `examples/project_adaptations/` 的显式 boundary map，输出带 `proven:false`。

---

## 1. 汇总表（40 / 40 core JSON 命令）

| 命令 | 解决的问题 | 典型消费步骤 | schema version |
|---|---|---|---|
| `capabilities` | 列出工具面与契约，决定用什么 | 0. 开工探路 | 1 |
| `scope` | 一个 scope 的类型/父/子/端口/参数 | 1. 进入 scope | 1 |
| `instances` | 列实例；给路径看实例详情 | 1. 建立实例清单 | 1 |
| `hierarchy` | 机器可读的实例层级树 | 1. 看架构层级 | 1 |
| `ports` | 模块端口总览（方向/位宽/边数） | 1. 查模块接口 | 1 |
| `params` | 实例的生效参数与 override 状态 | 1. 确认配置差异 | 1 |
| `connections` | 实例端口 ↔ 内部信号 | 1. 追端口连线 | 1 |
| `class` | class 列表/成员/实例/关系 | 1. 理解 class 结构 | 1 |
| `drivers` | 谁驱动这个信号（上游） | 2. 反向追因果 | 1 |
| `loads` | 这个信号被谁使用（下游） | 2. 正向追因果 | 1 |
| `paths` | 两信号间的结构路径（可定向） | 2. 判断连通性 | 1 |
| `dataflow analyze` | 源→目标的数据流/时序/条件 | 2. 跨模块数据流 | 1 |
| `controlflow analyze` | 驱动该信号的条件 | 2. 解释何时被驱动 | 1 |
| `controlflow list-conditioned` | 枚举所有带条件驱动的信号 | 2. 找分析入口 | 1 |
| `trace impact` | 下游影响面 + 启发式风险排序 | 2. 改动影响评估 | 1 |
| `trace frontier` | 结构 trace 停在哪、下一步查什么 | 2. 遇断点继续查 | 1 |
| `trace evidence` | 源码 always/if 块证据 | 2. 为结论找原文 | 1 |
| `trace profile` | 信号画像：位映射/clock/reset/时序 | 2. 波形关联前置 | 1 |
| `trace lookup` | 完整 hier path → canonical id | 2. 波形路径映射 | 1 |
| `trace manifest` | 批量 waveform path → canonical+profile | 2. 批量波形对齐 | 1 |
| `verify consistency` | 图的双向一致性自检 | 3. 用图前先验图 | 1 |
| `verify claim` | 验证一条 claim：真/假/证不了 | 3. 防幻觉裁决 | 1 |
| `verify structural` | sibling 端口集合对称性审查 | 3. 结构缺陷候选 | 1 |
| `trace constraints` | 属性受哪些 constraint block 约束 | 4. 约束定位 | 1 |
| `trace constraint-neighborhood` | 一个随机变量的跨 block 邻域图 | 4. 约束影响面 | 1 |
| `trace constraint-chain` | 两个随机变量间最短约束链 | 4. 变量间关系 | 1 |
| `trace tb-join` | TB 随机字段 → RTL 信号候选 join | 4. TB/RTL 对齐 | 1 |
| `trace covergroups` | 列 covergroup 定义 | 4. 覆盖结构盘点 | 1 |
| `trace coverpoints` | 信号被哪些 coverpoint 采样 | 4. 覆盖反查 | 1 |
| `trace covergroup` | 一个 covergroup 的采样链/约束链 | 4. 覆盖到约束 | 1 |
| `snapshot save` | 把当前图状态存为快照 | 5. 建基线 | 1 |
| `snapshot list` | 列快照；给 tag 看详情 | 5. 查基线 | 1 |
| `snapshot compare` | 两个快照/SV 文件的结构差异 | 5. 回归对比 | 1 |
| `snapshot delete` | 删除快照 | 5. 清理 | 1 |
| `stats` | 图规模与 kind/module 统计 | 6. 判断图是否可用 | 1 |
| `search` | 文本/正则搜源码 | 6. 非图路径定位原文 | 1 |
| `graph nodes` | 枚举图节点（可过滤/加富字段） | 6. 兜底枚举 id | 1 |
| `graph edges` | 枚举图边 | 6. 兜底枚举关系 | 1 |
| `graph subgraph` | seed 的 k-hop 局部子图（有预算） | 6. 控制上下文大小 | 1 |
| `filelist prune` | top-aware 保守 filelist 裁剪候选 | 6. 大项目降载 | 1 |

> `schema version` 列 = `capabilities` 中该命令的 `schema_version` 字段；
> 全部 core 命令都是 `"1"`。注意：**单命令 JSON 输出里不带 `schema_version`**，
> 版本只在 `capabilities` 顶层与 `layers.core.schema_version` 声明。

---

## 2. 按工作流展开

### 2.1 范围 / 清单（scope & inventory）

#### `capabilities`
- **解决**: 一次拿到全部命令的层、组、模式、成本、是否 JSON、是否
  `recommended`、schema 版本，以及 `json_contract` / `bit_precision`。
- **输入**: `capabilities [--recommended] [--include-exp] [--json] [--pretty]`
- **result**: 顶层即 payload（非 `result` 信封）：
  `schema_version`, `layers`, `core_groups`, `counts`, `planned_new`,
  `bit_precision`, `json_contract`, `commands[]`。
  每个 command：`name/planned_name/aliases/layer/group/mode/kind/cost/json/
  stateful/readonly/stability/schema_version/recommended/envelope/write_scope/note`。
- **坑**: 默认不列 `exp`；`--include-exp` 才出现。`mode` 由
  `mode_of()` 推断。`envelope` 为 `standard|direct`，`write_scope` 为
  `none|cache|output`；不要把 direct 当标准信封。
- **例**: `sv_query capabilities --json`

#### `scope`
- **解决**: 给定一个 scope 路径，返回其类型、父、直接子实例、端口、
  生效参数、直接子信号；`kind` 可为 `instance|generate|class`。
- **输入**: `scope <path> --file/-f <sv> | --filelist <f>`
- **result**: `scope`, `canonical_id`, `kind`, `module_type`, `parent`,
  `children[]`(`full_path/name/module_type/canonical_id`),
  `ports[]`(`name/direction/width/canonical_id/internal_signal`),
  `parameters[]`(`name/value/is_overridden/is_local_param`),
  `signals[]`(`name/canonical_id/kind/width/is_port/direction`),
  `members[]` / `instances[]`（class scope）。
- **坑**: 只接受 RTL scope；给信号或 class instance 会 `ok:false`、
  `result:null`，并在 `errors[]` 里给 `hint`（class 请用 `class` /
  `trace covergroup --instance`）。模块名与实例路径都可作为 scope 起点。
- **例**: `sv_query scope top.u_core --filelist rtl.f --json`

#### `instances`
- **解决**: 无参数时列全部实例；给实例路径时返回该实例详情（类型/父/
  直接子/端口）。
- **输入**: `instances [path] [--module/-m <m>] [--depth/-d N]`
- **result（direct 信封，无 `result` 包装）**:
  - 列表模式：`ok`, `count`, `module`, `instances[]`
    (`full_path/name/module_type/parent`)。
  - 详情模式：`ok`, `full_path`, `name`, `module_type`, `parent`,
    `children[]`, `ports[]`。
- **坑**: 详情模式字段与列表模式不同，消费前先看有无 `full_path`。
  找不到时 `ok:false` + `error/path/hint`，不是空列表。
- **例**: `sv_query instances top.u_core --filelist rtl.f --json`

#### `hierarchy`
- **解决**: 输出实例层级树，等价于机器可读版架构展示。
- **输入**: `hierarchy [--module/-m <root>] [--depth/-d N]`
- **result（direct）**: `ok`, `root_count`, `instance_count`,
  `tree_node_count`, `root`, `depth`,
  `tree[]`(`full_path/module_type/children[]/synthetic`)。
- **坑**: 顶层包装节点是 `synthetic:true`（`module_type:null`），
  不要把 synthetic root 当真实实例统计。`--module` 可指定子树根。
- **例**: `sv_query hierarchy --module top --depth 3 --filelist rtl.f --json`

#### `ports`
- **解决**: 模块/实例的端口总览：方向、位宽、入边数、出边数。
- **输入**: `ports <module-or-instance>`
- **result（direct）**: `ok`, `module`, `count`, `by_direction`,
  `ports[]`(`port/id/direction/width/in_edges/out_edges`)。
- **坑**: `width` 是 `[msb, lsb]`；1-bit 端口常见 `[0,0]`。边数是图内
  直接边，不是端口在源码中的引用次数。
- **例**: `sv_query ports top.u_core --filelist rtl.f --json`

#### `params`
- **解决**: 给出实例的**生效**参数；`is_overridden` 区分实例 override
  与默认值。
- **输入**: `params <instance-path>`
- **result（direct）**: `ok`, `instance`, `module_type`, `count`,
  `parameters[]`(`name/value/is_overridden/is_local_param`)。
- **坑**: 只接受实例路径。给模块类型会 `ok:false` + `hint`。无参数时
  `count:0` 是正常结果，不是失败。
- **例**: `sv_query params top.u_core.u_fifo --filelist rtl.f --json`

#### `connections`
- **解决**: 实例的端口 ↔ 内部信号映射，输出带 `resolved_as`。
- **输入**: `connections <instance-path>`
- **result（direct）**: `ok`, `resolved_as`(`instance|unknown`),
  `instance`, `module_type`, `parent`, `port_count`,
  `ports[]`(`port/direction/width/internal_signal`)。
- **坑**: 当前实现**只接受实例路径**；给模块类型会显式报错
  `target is not an instance path` 并提示可用实例（与 registry note 的
  "模块→四类边" 描述不一致，见 U3）。`resolved_as:unknown` 是显式降级。
- **例**: `sv_query connections top.u_core --filelist rtl.f --json`

#### `class`
- **解决**: 不给名字 → 列全部 class；给名字 → 类型级成员 + 实例级节点；
  `--member` 查某成员的实例；`--relations` 查继承/成员/实例/约束/方法。
- **输入**: `class [name] [--member <m>] [--relations]`
- **result（direct，三/四种形状）**:
  - 列表：`ok`, `count`, `classes[]`。
  - 详情：`ok`, `class`, `member_count`, `members[]`,
    `instance_count`, `instances[]`。
  - `--member`：`ok`, `class`, `member`, `count`, `instances[]`,
    `candidate_count`, `candidates[]`
    (`canonical_id/member/class_instance/in_graph/kind/width/is_rand/
    rand_mode/type`), `note`。
  - `--relations`：`ok`, `class`, `relations`
    (`extends/ancestors/subclasses/descendants/members/instances/
    member_instances/constraints/constraint_blocks/covergroups/uvm/methods`)。
- **坑**: `--member` 的 `instances` 只含图内已存在节点；完整路径在
  `candidates`，两者的 `in_graph` 不同。class 关系是类型级语义，
  不等价于实例化后的图边。
- **例**: `sv_query class packet --relations --filelist tb.f --json`

---

### 2.2 追踪 / 因果（trace & causality）

> 这一组是 agent 的主力。所有命令都支持 `--file` 单文件或 `--filelist`
> 多文件；真实项目请用 `--filelist`，单文件只能看到该文件内的模块。

#### `drivers`（别名 `trace fanin`）
- **解决**: 谁驱动这个信号：沿 `DRIVER` 边反向遍历，给出上游节点、
  多驱动/条件驱动/冲突等标记。
- **输入**: `drivers <signal> [--depth N] [--max-results N] [--evidence]
  [--module <m>] [--batch ...]`
- **result**: `signals[]`, `total_signals`, `failed_signals`,
  `total_count`, `total_pre_filter`, `truncated`。
  每个 signal：`signal/index/resolved_signal/resolution/precision/
  coarse_fallback/top_modules/top_ambiguous/bit_fallback/dynamic_index/
  function_call/runtime_system_call/conditions/condition_truncated/
  truncated_by_depth/cycles_detected/count/pre_filter_count/truncated/
  driver_count/multi_driver/conditional_drivers/driver_conflict/
  driver_conflict_analysis/error/candidates/suggestions/drivers[]`。
  driver 节点：`id/module/kind/width/width_msb/width_lsb/distance/
  precision/is_signed/parent/bit_range/condition/conditions/
  condition_paths/condition_simplified/...`。
- **坑**: 未知信号返回 `ok:false` 但 exit code 为 0（batch 语义），
  必须看 `ok`。`truncated` 是 `--max-results` 截断；`truncated_by_depth`
  是 depth 边界还有边；两者独立。`precision:unknown` 表示运行期索引/
  函数调用等静态不可判定来源，是显式降级不是 bug。
- **例**: `sv_query drivers top.u.a --filelist rtl.f --json`

#### `loads`（别名 `trace fanout`）
- **解决**: 这个信号被谁使用：沿 `DRIVER` 边正向遍历。
- **输入**: `loads <signal> [--depth N] [--max-results N] [--evidence]
  [--include-clock] [--include-reset]`
- **result**: 与 `drivers` 同构，节点数组为 `loads[]`，无
  `driver_count` 等 driver 专属字段。
- **坑**: 默认不跟 `CLOCK`/`RESET` 边；需要时显式 `--include-clock` /
  `--include-reset`。`--include-control` 当前显式报 unsupported，不静默
  忽略。
- **例**: `sv_query loads top.u.a --filelist rtl.f --json`

#### `paths`
- **canonical 字段**: `--canonical` 追加 `canonical_policy` 与
  `candidate_count`；默认不加。
- **无向爆炸**: 默认无向，`--max-depth` 默认 50；大规模设计优先
  `--directed --canonical`，否则搜索空间指数增长。
- **解决**: 两个信号之间是否存在结构路径；默认无向（逆流也可达），
  `--directed` 只沿数据流方向。
- **输入**: `paths <src> <dst> [--all] [--directed] [--canonical]
  [--evidence] [--max N] [--bits s,d] [--from-snapshot tag]`
- **result（direct）**:
  - 单路径：`ok`, `src`, `dst`, `src_resolved`, `dst_resolved`, `bits`,
    `directed`, `found`, `hop_count`, `path[]`。
  - `--all`：额外 `count`, `truncated`, `all_paths[][]`。
  `bits` 结构：`{src:{requested_bit,requested_range,resolved,precision,
  coarse_fallback,kind}, dst:{...}, coarse_fallback}`。
- **坑**: `found:false` 是"查询成功但无路径"（exit 0），不是错误；
  端点不存在则 `ok:false` + `unknown[]` + `hint`，exit 1。
  默认无向结果**不能**当作数据流方向结论；要方向请 `--directed`。
- **例**: `sv_query paths top.a top.y --directed --filelist rtl.f --json`

#### `dataflow analyze`
- **端点合同**: 返回路径最后一项必须等于请求 dst；父/BIT_SELECT 候选
  不得伪装成到达目标。
- **解决**: 源→目标的有向数据流：路径、条件、时钟域、寄存器边界
  延迟、异步跨越、timing risk。
- **输入**: `dataflow analyze <from> <to> [--max-paths N] [--bits s,d]
  [--evidence]`
- **result**: `from_signal`, `to_signal`, `from_resolved`, `to_resolved`,
  `bits`, `is_reachable`, `paths_count`, `intermediate_signals[]`,
  `primary_latency_cycles`, `primary_is_async`, `all_conditions[]`,
  `clock_domain`, `timing_risk`, `paths[]`。
  path：`path_id/segments[]/distance/has_conditional/latency_cycles/
  is_async_crossing/latency_note/stage_breakdown`。
  segment：`from_signal/to_signal/driver/condition/timing/assign_type/
  distance`（`--evidence` 时加 `evidence`）。
- **坑**: `is_reachable:false` 是正常结论。`timing_risk` 是模型输出，
  不是 STA 证明。`latency_cycles` 是寄存器边界口径，不是仿真周期。
- **例**: `sv_query dataflow analyze top.a top.y --filelist rtl.f --json`

#### `controlflow analyze`
- **解决**: 某信号的驱动条件：哪些驱动受哪些 if/case/条件控制。
- **输入**: `controlflow analyze <signal> [--conditions-only]
  [--evidence]`
- **result**: `signal`, `conditioned_drivers[]`(`to_node/conditions[]`，
  condition 为 `{expr, edge{src,dst,kind,condition}}`),
  `condition_status`, `warnings[]`。
  `--conditions-only` 输出扁平条件列表（原 `controlflow conditions` 视图）。
- **坑**: `condition_status` 非 `complete` 时条件集合可能不完整；
  `warnings[]` 必须读。条件文本是显示字符串，不是规范化布尔 AST。
- **例**: `sv_query controlflow analyze top.u.s3 --filelist rtl.f --json`

#### `controlflow list-conditioned`
- **解决**: 枚举所有带条件驱动的信号，用于找分析入口。
- **输入**: `controlflow list-conditioned`
- **result**: `signals[]`, `count`；顶层可能带 `subcommand`
  （`"list-conditioned"`）。
- **坑**: 这是枚举/入口发现，不解释条件；逐个信号仍需
  `controlflow analyze`。成本标为 `expensive`。
- **例**: `sv_query controlflow list-conditioned --filelist rtl.f --json`

#### `trace impact`
- **解决**: 改动一个信号的下游影响面：路径、覆盖标签、启发式风险分。
- **输入**: `trace impact [signal] [--min-risk 30] [--batch ...]
  [--max-results N]`
- **result**: `signals[]`, `total_signals`, `total_paths`,
  `total_high_risk_count`, `failed_signals`, `risk_model`。
  signal：`signal/index/resolved_signal/resolution/precision/
  coarse_fallback/total_paths/high_risk_count/modules[]/paths[]`。
  path：`path/path_type/risk/risk_score/fanout/coverage/condition/
  clock_domain/suggestion`。
- **坑**: `risk_model = "heuristic_v1 (未标定; 仅用于相对排序)"`。
  `risk_score` **不能**当绝对风险；只在同一张图内做相对排序。
  `coverage` 是 SVA/covergroup 标签，不是覆盖率数字。
- **例**: `sv_query trace impact top.rst_n --filelist rtl.f --json`

#### `trace frontier`
- **解决**: 结构 trace 走到断点时，报告断点类型、所在实例、路径，以及
  下一步应该 probe 什么（`connections` / `instances` / `ports`）。
- **输入**: `trace frontier <signal> [--direction fanin|fanout|both]
  [--max-depth 8] [--max-frontier 50] [--from-snapshot tag]`
- **result**: `signal`, `frontier[]`, `summary`, `note`。
  frontier 行：`direction`, `node`, `reason`, `instance`, `path[]`,
  `next_probes[]`。`reason` 取值：`no_structural_edge`,
  `instance_boundary`, `cycle_or_all_seen`, `depth_limit`。
  summary：`frontier_count`, `truncated`, `max_depth`, `max_frontier`。
- **坑**: `note` 固定为 `"generic boundary frontier; no semantic
  classification"`——它**不做 FIFO 分类、不造边**。未知信号 exit 1、
  `ok:false`。`max-frontier` 是全局上限，触顶时 `summary.truncated:true`。
- **例**: `sv_query trace frontier top.x --filelist rtl.f --json`

#### `trace evidence`
- **解决**: 为信号找源码证据：所在 always 块、if 条件、assign、class /
  constraint 上下文及原文片段。
- **输入**: `trace evidence <signal> [--chain] [--batch ...]
  [--from-snapshot tag]`
- **result**: `signals[]`, `total_signals`, `failed_signals`；
  signal：`signal/index/resolved_signal/resolution/candidates/
  suggestions/error/evidence`。`evidence`：`signal/source_location/
  source_text/enclosing_always/enclosing_always_comb/enclosing_if/
  enclosing_assign/enclosing_class/enclosing_constraint/enclosing_chain[]/
  is_verified/credibility_score`。
- **坑**: `credibility_score` 是 0..1 启发式，不是证明。
  `is_verified:false` 时不要引用为事实。顶层可能另带 `evidence`
  （可选，取决于批量/单条模式）。
- **例**: `sv_query trace evidence top.u.s1 --filelist rtl.f --json`

#### `trace profile`
- **解决**: 信号画像：canonical id、aliases、位映射、类型、clock/reset、
  是否时序、pipeline stage、声明/驱动源码位置。波形关联前置。
- **输入**: `trace profile [signal] [--batch ...] [--batch-file ...]`
- **result**: `signals[]`, `total_signals`, `failed_signals`。
  signal：`signal/index/resolved_signal/resolution/aliases/width/
  is_signed/kind/module/type/bit/source/role/clock_domains[]/clocks[]/
  resets[]/sequential/driver_count/load_count/error`。
  `sequential`：`is_sequential/assign_types[]/stage/stage_known/
  stage_source/stage_unknown_reason/sample/sample_unknown_reason/always`。
- **坑**: `stage:null` + `stage_known:false` 是"无法判定"，不是 stage 0。
  `sample_unknown_reason` 会说明 combinational/multi_clock 等原因。
- **例**: `sv_query trace profile top.u.s1 --filelist rtl.f --json`

#### `trace lookup`
- **解决**: 把完整 RTL hier path 严格映射到 canonical graph id；支持
  `$root`、位父回退、aliases，**不做模糊后缀**。
- **输入**: `trace lookup --path <p> [--path ...] [--paths-file f]`
- **result**: `paths[]`, `total`, `found`, `failed`。
  path：`requested/found/canonical/resolution/matched_via/bit_suffix/
  aliases[]/suggestions[]/width/kind/module`。
  `resolution`: `exact|alias|bit_parent|ambiguous|not_found`。
- **坑**: 单条 `found:false` 不使整体 `ok:false`；看 `failed` 计数。
  `ambiguous` 时 `canonical:null`，不要自己选第一个。
- **例**: `sv_query trace lookup --path top.u.s1 --filelist rtl.f --json`

#### `trace manifest`
- **解决**: 批量 waveform manifest：每个 path → lookup 结果 + profile
  （type/bit/clock/reset/stage）。
- **输入**: `trace manifest --path <p> ... | --paths-file f`
- **result**: `entries[]`, `total`, `found`, `failed`。
  entry：`waveform_path/index/found/lookup/profile`（可选 `error`）。
- **坑**: `found` 只表示严格 lookup 成功；`profile.error` 仍可能非空。
  条目级失败不改变整体 `ok`，用 `failed` 统计。
- **例**: `sv_query trace manifest --paths-file waves.txt --filelist rtl.f --json`

---

### 2.3 验证（verify）

#### `verify consistency`
- **解决**: 图自洽检查：fanin/fanout 互反、bit parent/bit_range、
  connection port↔internal 三类。
- **输入**: `verify consistency [--checks reciprocity,bit,connection]
  [--signal s] [--max-nodes 200] [--full]`
- **result**: `verified`, `total_violations`, `unknown_checks[]`,
  `checks[]`。check：`check/status/checked/skipped/violations[]/
  truncated/mode/excluded/coverage/...`。`status` ∈ `pass|fail|unknown`。
- **坑**: `verified:true` 要求全部 check 通过且无 unknown；`unknown`
  表示元数据不足，不等于 pass。默认采样（`mode:"sample"`），
  `--full` 才全量；`truncated:true` 时结论只覆盖样本。
- **例**: `sv_query verify consistency --filelist rtl.f --json`

#### `verify claim`
- **已知边界**: `driver` 与 `path` 对同一声明也可能给出不同结论；例如顶层
  bitwise-NOT 后 `driver` 为 contradicted、`path` 为 verified。不要把
  `driver contradicted` 单独解释成“没有连接”。
- **解决**: 验证一条 claim（driver/path/connection/bit），输出
  `verified|contradicted|unknown`，带支持证据与反证。
- **输入**: `verify claim --claim '<json>' | --claim-file f`
  `[--from-snapshot tag]`
- **result**: `claim`, `status`, `reason`, `evidence[]`,
  `counterevidence[]`；仅当 `status:"unknown"` 时额外有
  `machine:{status,unknown_kind,unresolved_endpoint}`。
  `unknown_kind` ∈ `unresolved_endpoint|unverifiable`。
- **坑**: `unknown` 是"证据不足/端点不存在"，**不是 false**，也不代表
  claim 被推翻；`contradicted` 才是"有反证"。`verified`/`contradicted`
  不输出 `machine`。`reason` 是给人读的，机器分流请用
  `machine.unknown_kind`。
- **例**: `sv_query verify claim --claim '{"type":"path","from":"top.x","to":"top.y"}' --filelist rtl.f --json`

#### `verify structural`
- **解决**: 结构审查：sibling 实例端口集合对称性，输出 findings +
  evidence + 可交给 `graph subgraph` / `review render` 的子图 spec。
- **输入**: `verify structural [--checks symmetry] [--max-findings 100]`
- **result**: `findings[]`, `total`, `truncated`, `checks[]`。
  finding：`id/check/severity/confidence/message/seeds[]/expected/actual/
  evidence[]/subgraph`。check：`check/status/checked/findings`。
- **坑**: 这是**候选**审查，不是缺陷证明；`confidence` 低时需人工确认。
  `truncated:true` 表示还有 finding 未返回。当前 check 只有
  `symmetry.port_set`。
- **例**: `sv_query verify structural --filelist rtl.f --json`

---

### 2.4 约束 / 随机（constraint & random）

> 语义来源是 slang semantic AST（class/constraint/covergroup）。
> 这一组是**语义关系图**，与 `DRIVER` 图是独立域，不要混用。

#### `trace constraints`
- **解决**: 一个属性/变量受哪些 constraint block 约束；支持类型级与
  实例级 id。
- **输入**: `trace constraints <property>`
- **result**: `property`, `resolved`, `count`, `constraints[]`。
  constraint 对象（实际字段）：`block`, `vars[]`, `conditions[]`,
  `expr_count`, `defined_in`, `inherited`, `rand_vars[]`,
  `solve_before[{node,before[]}]`, `dist[]`。
- **坑**: `block` 是 block 名；不是 registry 里 `constraint_block.id`
  （见 U6）。`inherited:true` 表示来自祖先 class。`solve_before` /
  `dist` 已提取但并不表示求解顺序一定生效。property 不存在时 exit 1、
  `ok:false`，并给 `hint`/`suggestions`。
- **例**: `sv_query trace constraints pkt.addr --filelist tb.f --json`

#### `trace constraint-neighborhood`
- **解决**: 一次查询跨多个 constraint block 的随机变量关系图：
  BFS 邻域、共同 block、最短路径、重要性指标。
- **输入**: `trace constraint-neighborhood <property>
  [--max-depth 6] [--max-nodes 200]`
- **result**: `root`, `nodes[]`, `relations[]`, `paths`, `summary`。
  node：`id/depth/blocks[]/neighbors[]/path[]/block_count/degree`。
  relation：`source/target/blocks[]`。
  summary：`node_count/relation_count/direct_degree/reachable_count/
  max_depth/truncated/degree_centrality/importance_metrics`。
  `truncated=true` 表示 `--max-nodes` 预算命中，邻域不完整。
- **坑**: `degree_centrality` 与 `importance_metrics` 是启发式指标，
  不是统计显著性。`max_nodes` 触顶时结果不完整（summary 里没有单独
  truncated 字段，需对比 `max_nodes`，见 U5）。
- **例**: `sv_query trace constraint-neighborhood rnd.a --filelist tb.f --json`

#### `trace constraint-chain`
- **解决**: 两个随机变量之间的最短 constraint 链，按 constraint block
  共成员关系拼接（co-membership）。
- **输入**: `trace constraint-chain <source> <target>
  [--max-depth 6] [--max-nodes 200]`
- **result**: `found`, `source`, `target`, `rand`（两端的 rand 布尔），
  `hop_count`, `chain[]`, `segments[]`, `blocks[]`, `summary`, `note`；
  失败时 `found:false` + `reason`（`no_constraint_path` /
  `endpoint_not_random`）且可能省略 `chain/blocks/hop_count`。
  chain 元素：`{kind:"variable"|"constraint_block", id, from?, to?, via?}`；
  segment：`{from,to,blocks[],via}`，`via` ∈ `var|condition`。
  summary：`node_count/block_count/truncated/max_depth`。
- **坑**: `note` 固定为 `"constraint co-membership only; not a solver
  proof"`。**链存在不等于约束可满足**，也不代表 solver 会按此顺序求解。
  非 rand 端点显式 `found:false, reason:"endpoint_not_random"`；
  端点不存在则 exit 1、`ok:false`。
- **例**: `sv_query trace constraint-chain rnd.a rnd.d --filelist tb.f --json`

#### `trace tb-join`
- **解决**: TB 随机字段 → RTL snapshot 信号的**候选** join，按名字匹配，
  同时返回该字段的 constraint。
- **输入**: `trace tb-join <field> --from-snapshot <tag>`
  （`--from-snapshot` 必填；TB 用 `--file`/`--filelist`）
- **result**: `tb_field`, `leaf`, `constraints[]`, `join_status`,
  `rtl_candidates[]`, `note`。
  candidate：`signal/name/kind/module/file/line/reason`。
  `join_status` 例：`single_candidate`。
- **坑**: **name-based**；`single_candidate` 不是连接证明。必须再用
  driver/BFM/source 验证。`note` 已显式提醒。
- **例**: `sv_query trace tb-join tb_item.rcont -f tb.sv --from-snapshot rtl_v1 --json`

#### `trace covergroups`
- **解决**: 列出 covergroup 定义（可 `--class` 过滤），含 coverpoint、
  bins、crosses、clock、实例规则。
- **输入**: `trace covergroups [--class <c>]`
- **result**: `count`, `covergroups[]`, `complete`, `reason`。covergroup：
  `name/in_class/host_module/clock/coverpoints[]/crosses[]/
  instance_rule/file/line`；coverpoint 含 `name/signal/iff/bins/sampled/
  bin_details[]`。`reason` 为 `found/no_match_in_filter/no_covergroups_in_scope`。
- **坑**: 空结果 `count:0` 是正常的（该文件无 covergroup）。
  `in_class` 为空表示 module-scope 定义；`host_module` 为空表示 class
  scope 定义。按 `in_class` + `host_module` 一起判断归属。
- **例**: `sv_query trace covergroups --filelist tb.f --json`

#### `trace coverpoints`
- **解决**: 反向查询：某信号被哪些 covergroup/coverpoint 采样。
- **输入**: `trace coverpoints <signal>`
- **result**: `signal`, `count`, `matches[]`, 可选 `hint`。
  match：`covergroup/coverpoint/in_class/host_module/ref_name/select/
  instance`。
- **坑**: class coverpoint 需要**实例级路径**（如 `top.e.p.addr`）；
  只给类型级信号可能空结果并返回 `hint`。空结果不是错误。
- **例**: `sv_query trace coverpoints top.e.p.addr --filelist tb.f --json`

#### `trace covergroup`
- **解决**: 查一个 covergroup 的采样链（coverpoint → 图信号 → drivers），
  或 `--rand` 查采样属性 → constraint 链。
- **输入**: `trace covergroup <name> [--coverpoint cp] [--instance path]
  [--rand]`
- **result**: `mode`(`sampling|rand`), `covergroup`, `count`,
  `samples[]`；`--rand` 时给 `links[]`（为空时该键可能被省略）。
  sample：`coverpoint/signal_raw/sampled[]/drivers[]/missing[]`。
  link：`covergroup/coverpoint/property/constraints[]`。
- **坑**: `missing[]` 是未解析引用，必须报告而不是忽略。`links` 空时
  实际输出**省略该键**（与"可空用 null"的 v1 策略不一致，见 U4）。
- **例**: `sv_query trace covergroup cg_sel --filelist tb.f --json`

---

### 2.5 状态 / 快照（state & snapshot）

> 快照默认写到 `~/.svq/cache/snapshots`，可用 `SVQ_SNAPSHOT_DIR` 覆盖。
> 只写自有缓存目录，不碰项目 RTL。

#### `snapshot save`
- **解决**: 把当前解析结果存为带 tag 的快照，供后续 compare /
  `--from-snapshot` 复用。
- **输入**: `snapshot save <path> [--tag t] [--git] [--filelist f]`
- **result（direct）**: `ok`, `tag`, `path`, `files`, `node_count`,
  `edge_count`, `elaboration_errors`, `failed_files[]`。
- **坑**: elaboration error 会 raise；已解析到的错误随图存下。
  `failed_files` 非空时快照仍可能成功，必须读该字段。
- **例**: `sv_query snapshot save rtl/top.sv --tag v1 --filelist rtl.f --json`

#### `snapshot list`
- **解决**: 无 `tag` 时列全部快照；给 `tag` 时返回该快照详情。
- **输入**: `snapshot list [tag]`
- **result（**非标准信封**）**:
  - 无 tag：**顶层 JSON 数组**，元素 `tag/version/created_at/
    git_commit/files[]/node_count/edge_count`。
  - 有 tag：**顶层 JSON 对象**（同上字段），无 `ok`。
- **坑**: 这是 core 里最不一致的 JSON 形状：没有 `ok`、没有
  `result` 包装（见 U2）。空快照目录输出 `[]`。解析前先判断
  `Array.isArray` / `type == "list"`。
- **例**: `sv_query snapshot list --json`

#### `snapshot compare`
- **解决**: 比较两个快照；若两个参数都是已存在文件或 `.sv/.v/.svh`，
  则编译成图后做健康度/可达性 diff。`--signal` 看单信号可达性差异。
- **输入**: `snapshot compare <tag1|file1> <tag2|file2> [--signal s]
  [--top N] [--show-edges]`
- **result（**非标准信封**）**: `tag1`, `tag2`, `stable_core[]`,
  `health_score_old`, `health_score_new`, `health_delta`,
  `coupling_warning`, `added_nodes[]`, `removed_nodes[]`,
  `added_edges[]`, `removed_edges[]`, `identical`, `node_count_1`,
  `node_count_2`, `node_diff`；文件模式另有可达性差异字段。
- **坑**: 无 `ok`。`health_score` 是内部健康度模型，不是功能正确性。
  `--show-edges` 默认关闭。两个参数是 tag 还是文件由"文件是否存在 /
  后缀"判定，歧义输入会被当成 tag。
- **例**: `sv_query snapshot compare v1 v2 --json`

#### `snapshot delete`
- **解决**: 删除一个快照 tag。
- **输入**: `snapshot delete <tag> [--force]`
- **result（direct）**: `ok`, `tag`, `deleted`。
- **坑**: 不带 `--force` 会交互确认；非交互环境（stdin 关闭）会打印
  `Aborted.`、不删除、**不输出 JSON 且 exit 0**，agent 必须显式
  `--force`。删除不存在的 tag 返回 `ok:false`, `deleted:false`,
  `error:"snapshot not found"`（同样 exit 0，仍须看 `ok`）。
- **例**: `sv_query snapshot delete v1 --force --json`

---

### 2.6 定位 / 原语（locate & primitive）

#### `stats`
- **解决**: 图规模与分布：节点/边总数、按 kind 计数、模块列表、
  elaboration 错误。
- **输入**: `stats [--filelist f] [--fanout-rank] [--top N]`
- **result**: `total_nodes`, `total_edges`, `nodes`(kind→count),
  `edges`(kind→count), `modules[]`, `elaboration_errors[]`。
- **坑**: `elaboration_errors` 非空说明图不完整，后续结论要降级解读。
  这是判断"图能不能用"的第一道门。
- **例**: `sv_query stats --filelist rtl.f --json`

#### `search`
- **解决**: 在 `.sv/.v` 文件或目录里做文本/正则搜索，返回文件与行。
- **输入**: `search <keyword> --file <path-or-dir> [--regex] [--ignore-case]
  [--context N] [--max-results N]`
- **result（**非标准信封，无 `ok`**）**: `keyword`, `target`, `regex`,
  `case_insensitive`, `total_matches`, `file_count`,
  `files[]`(`file/match_count/lines[]/truncated`)；
  line：`line/text`。
- **坑**: 这是源码文本搜索，不是语义查询；结果可被注释/字符串误导。
  单文件 `truncated` 是每个文件的返回上限。
- **例**: `sv_query search "fifo_wdata" --file rtl/ --regex --json`

#### `graph nodes`
- **解决**: 枚举图节点，支持 kind/module/子串过滤；`--detail` 给表达式、
  操作数、条件等富字段。
- **输入**: `graph nodes [--kind K] [--module M] [--match S] [--detail]`
- **result**: `nodes[]`, `total`。基础 node：
  `id/name/kind/module`；`--detail` 加 `width/expression/operands[]/
  signals[]/function_name/condition/true_branch/false_branch`。
- **坑**: `command` 字段实际为 `"list_nodes"`（不是 `graph_nodes`）。
  `total` 是返回条数，不是全图节点数；全图统计用 `stats`。
- **例**: `sv_query graph nodes --kind SIGNAL --match fifo --detail --json`

#### `graph edges`
- **解决**: 枚举图边，支持 kind/src/dst 过滤。
- **输入**: `graph edges [--kind K] [--src S] [--dst S]`
- **result**: `edges[]`, `total`。edge：`src/dst/kind`。
- **坑**: `command` 为 `"list_edges"`。只有三种字段，没有表达式/条件；
  需要边证据用 `graph subgraph --evidence`。
- **例**: `sv_query graph edges --kind DRIVER --json`

#### `graph subgraph`
- **解决**: 从 seeds 出发的 k-hop 局部子图，带节点/边/深度预算，
  输出边界 stub 与截断标记。
- **输入**: `graph subgraph <seed>... [--depth 2] [--direction in|out|both]
  [--edge-kinds driver,connection] [--max-nodes 80] [--max-edges 160]
  [--evidence]`
- **result**: 顶层另有 `seeds[]`；`result`: `nodes[]`, `edges[]`,
  `boundary[]`, `truncated{nodes,edges,depth}`, `stats{visited,
  returned_nodes,returned_edges,max_depth}`。
  node：`id/kind/module/width_msb/width_lsb/width/precision/parent/
  bit_range/is_signed`（`--evidence` 加 `file/line`）。
  edge：`src/dst/kind/expression/condition/bit_slice/assign_type`
  （`--evidence` 加 `file/line`）。
- **坑**: `boundary[]` 不是节点数组而是 stub id 列表，表示预算/深度外
  还有连接。`truncated.depth:true` 很常见（默认 depth 2），别把局部图
  当完整邻域。
- **例**: `sv_query graph subgraph top.u.s1 --depth 2 --edge-kinds driver --json`

#### `filelist prune`
- **解决**: 按 top module 做 top-aware 的**保守** filelist 裁剪，输出候选；
  可选写一个新 filelist。
- **输入**: `filelist prune --filelist <f> --top <module> [--output <new.f>]`
- **result**: `top`, `total_files`, `selected_files[]`, `selected_count`,
  `dropped`, `reason`, `declarations`(module→files)，`--output` 时加
  `output`。
- **坑**: 这是**候选裁剪，不是语义证明**：package/interface/无声明文件/
  读失败文件都会保留。top 找不到时返回完整 filelist 并标
  `reason:"top_not_found"`，不是错误。`--output` 是 core 里唯一会写
  文件的参数（只写显式路径，不改源文件）——见 U7。
- **例**: `sv_query filelist prune --filelist full.f --top top --json`

---

## 3. Schema 契约规则

### 3.1 标准信封 `ok/command/result/errors`
- 标准形状（`src/cli/_registry.py` 的 `JSON_CONTRACT.top_level`）：
  `{ok:boolean, command:string, params:object, result:object, errors:array}`。
  `ok:false` 当任一分信号/子项有错误；`ok:true` 时 `errors` 为空。
- `command` 是 snake_case 的命令名，**不保证等于命令 key**：
  `drivers → trace_fanin`、`loads → trace_fanout`、`graph nodes →
  list_nodes`、`graph edges → list_edges`。消费时按 `command` 分派。
- `params` 是解析后的请求回显（含默认值），可用于审计调用。
- `errors[]` 元素可为字符串或 error_entry 对象。trace 类通常为
  `{signal,index,error,error_code,...}`，另有命令用
  `{error,path,hint}` 或纯字符串（见 U5）。
- **例外**：`instances/hierarchy/ports/params/connections/class/paths/
  search/snapshot *` 是 `envelope:"direct"`：payload 在顶层，没有
  `result` 包装，部分甚至没有 `ok`。跨命令写通用消费者时必须先探测形状。
  依据：`_registry.py` 的 `commands.*.envelope == "direct"` 与实际输出。

### 3.2 `verified/contradicted/unknown` 与 `found/not_found` 不是一回事
- `verify claim.status`：`verified`（有支持证据）/ `contradicted`
  （有反证）/ `unknown`（证据不足或端点无法解析）。
  `unknown` **不是** `false`，仍是正常返回（exit 0）。
- `found`：关系查询的布尔结论。`paths.found:false`、
  `lookup.path[].found:false`、`constraint-chain.found:false`
  表示"查询完成，但没有这条关系"，exit 0。
- `ok:false`：本次请求本身不可完成（端点不存在、参数非法、文件错误）。
  例：`paths` 端点不存在 → `ok:false` + `unknown[]`，exit 1；
  `drivers` 端点不存在 → `ok:false` + per-signal `resolution:not_found`，
  但 exit 0（batch 语义）。**所以必须同时检查 `ok` 和字段，不能只看 rc。**
- `resolution:not_found` 出现在 per-signal 结果里；`suggestions[]` 是
  纠错候选，不是命中结果。

### 3.3 `machine.unknown_kind`
- 仅 `verify claim` 且 `status:"unknown"` 时出现：
  `machine:{status:"unknown", unknown_kind:"unresolved_endpoint"|
  "unverifiable", unresolved_endpoint:boolean}`。
- `unresolved_endpoint`：端点解析失败（`not_found` 类）。
  `unverifiable`：端点存在但证据不足以判定（如 bit claim 只有父总线）。
- `verified` / `contradicted` **不输出** `machine`，不要假设它恒在。
  依据：`src/cli/core/semantic/verify.py`、
  `docs/validation/P136_UNKNOWN_FLAG_2026-11-09.md`。

### 3.4 显式边界 `proven:false`（P140）
- 该字段**不属于 core 命令输出**，属于外部显式 adapter：
  `examples/project_adaptations/<project>/trace_with_map.py` 读取用户
  `boundary_map.json`，只拼接 prefix/suffix，不建图边。
- 合同：只要路径跨过显式 boundary，就输出 `proven:false`；
  单 boundary 时加 `asserted_relation:true` 与
  `boundary_hops[{index,src,dst,boundary_kind,evidence,confidence}]`；
  多 boundary → `status:"ambiguous"` + `candidates[]`，不静默选一个；
  空 map → `status:"boundary"` + `frontier`，不伪造路径。
- `proven:false` 表示"这是用户断言的关系，不是工具证明的语义"。
  agent 不得把它升级为 `verified`。依据：
  `docs/validation/P140_GUIDED_BOUNDARY_2026-11-09.md`、
  `examples/project_adaptations/opentitan_fifo/trace_with_map.py`。

### 3.5 constraint chain 是 co-membership，不是 solver 证明
- `trace constraint-chain` 的边来自"两个变量出现在同一 constraint
  block"以及 block 内的 `if` 条件成员关系；`segments[].via` 只会是
  `var` 或 `condition`。
- `result.note` 固定声明 `"constraint co-membership only; not a solver
  proof"`。它**不**说明：约束可满足、求解顺序、dist 权重生效、
  求解器会选这条链。
- `trace constraints` 的 `solve_before` / `dist` 是结构事实，不是
  solver 行为证明。依据：`src/cli/core/semantic/constraints.py`、
  `sim/tests/regression/test_constraint_chain.py`。

### 3.6 不做项目特定自动推断
- core 不认识 OpenTitan FIFO、不认识项目命名约定、不按名字建边。
  遇到结构断点只输出 `trace frontier`（`reason` + `next_probes`）。
- 需要跨项目/自定义边界时，只能显式调用
  `examples/project_adaptations/` 的 boundary map，输出
  `src/dst/evidence/confidence`，并保持 `proven:false`。
- 依据：AGENTS 铁律 12、`docs/dev/PROJECT_ADAPTATION.md`、
  `docs/agent/GUIDED_TRACE.md`。

### 3.7 其他跨命令不变量
- `null != false`：`cycles_detected:null` 表示预算不足，不是"无环"；
  `stage:null` 表示无法判定，不是 stage 0。
- `precision` / `coarse_fallback` / `dynamic_index` / `function_call` /
  `runtime_system_call` 是显式降级标记，不是错误。
  `precision:unknown` 时不要把位级结论当精确结论。
- `truncated` 家族彼此独立：`truncated`（结果数上限）、
  `condition_truncated`（条件路径枚举上限）、
  `truncated_by_depth`（深度边界）、`verify_check.truncated`
  （样本上限）。见到任一为 true，结论只能覆盖已返回部分。
- 启发式字段：`risk_score/risk_model`、`credibility_score`、
  `degree_centrality/importance_metrics`、`health_score`、
  `confidence` 都不是证明，只用于排序/分流。

---

## 4. Schema ambiguities: resolved（P144）

Worker 原始盘点列出了 9 个三方不一致；现在都已在 registry/contract 或输出中给出明确决定。
没有未登记的“消费者必须猜”的项。

| # | 原歧义 | 现在的事实/合同 | 位置 |
|---|---|---|---|
| U1 | `trace constraint-chain` mode 漂移 | `_TRACE_KEYS` 已包含，`mode:"trace"` | `src/cli/_registry.py` |
| U2 | snapshot list/compare/search 无标准 envelope | 不强行改历史形状；`capabilities.commands[].envelope="direct"` 明确例外，`json_contract.envelope_policy` 给出规则 | `JSON_CONTRACT` |
| U3 | `connections` note 说支持模块 | note 改为“仅实例路径”；模块类型仍显式报错 | `src/cli/_registry.py` |
| U4 | 可选键省略 vs null | `nullable_policy`：已知空值用 null；不适用可选字段可省略，但必须由命令 schema 标注；缺失不等于 false/zero | `JSON_CONTRACT` |
| U5 | `errors[]` 形状不统一 | `errors_policy`：允许 string 或 `error_entry`；error_entry 必有 `error`，trace 额外字段固定 | `JSON_CONTRACT` |
| U6 | `trace constraints` 用 block，contract 用 id | 输出同时有 canonical `id` 和兼容 alias `block`；`constraint_block` 两者都登记 | `constraints.py` |
| U7 | core readonly 与写文件冲突 | `readonly` 定义为不改 RTL/项目文件；新增 `write_scope` (`none/cache/output`) 标记例外 | `LayerSpec` / `CommandSpec` |
| U8 | constraint-neighborhood 无 truncated | `summary.truncated` 已输出；预算命中为 true | `constraint.py` |
| U9 | 空 coverage 结果不可区分 | `complete:true` + `reason` (`found/no_covergroups_in_scope/no_match_in_filter/no_sampling_refs/no_links/no_samples`)；解析失败仍 `ok:false` | `covergroups.py` |

### 4.1 仍需注意的边界

- `envelope="direct"` 是显式例外，不是推荐新命令效仿的形态。
- `errors[]` 仍是 union；消费者必须按 `typeof` 分支，不能假设对象。
- `complete:true` 表示命令已完成，不等于证明覆盖点/covergroup 语义完整。
- `summary.truncated=true` 时不要声称邻域完整。

## 5. 来源（schema 事实的出处）

**注册表 / 契约（唯一真相源）**
- `src/cli/_registry.py` — `LAYERS`、`COMMANDS`、`mode_of()`、
  `JSON_CONTRACT`、`BIT_PRECISION`、`to_json()`（capabilities payload）。
- `docs/CLI_SURFACE.md` — 由 `tools/gen_cli_surface.py` 从注册表生成，
  用于核对 40 个 core 命令与别名。
- `src/cli/errors.py` — 稳定 `E_*` error code（如
  `E_SIGNAL_NOT_FOUND`、`E_SIGNAL_AMBIGUOUS`）。
- `src/cli/_output.py` — 失败信封与 `--json` 输出纪律。
- `docs/architecture/json_contract_2026-10-31.md` — envelope / signal /
  node 字段说明。

**命令实现（按工作流）**
- scope/inventory: `src/cli/core/semantic/scope.py`、`instances.py`、
  `ports.py`、`params.py`、`classes.py`、`paths.py`；
  `src/cli/core/locate/capabilities.py`。
- trace/causality: `src/cli/core/semantic/frontier.py`、`trace.py`、
  `trace_evidence.py`、`trace_profile.py`、`trace_lookup.py`、
  `trace_manifest.py`、`dataflow.py`、`controlflow.py`。
- verify: `src/cli/core/semantic/verify.py`、
  `condition_analysis.py`。
- constraint/random: `src/cli/core/semantic/constraints.py`、
  `covergroups.py`、`tb_join.py`。
- state: `src/cli/core/state/snapshot.py`、`diff.py`。
- locate: `src/cli/core/locate/graph.py`、`search.py`、
  `filelist_cmd.py`。

**行为与边界文档**
- `docs/agent/GUIDED_TRACE.md` — frontier 循环、`reason` 取值、
  "不分类 FIFO / 不造边"。
- `docs/validation/P136_UNKNOWN_FLAG_2026-11-09.md` —
  `machine.unknown_kind` 分类。
- `docs/validation/P140_GUIDED_BOUNDARY_2026-11-09.md` —
  `proven:false` 边界合同。
- `examples/project_adaptations/opentitan_fifo/trace_with_map.py` —
  boundary runner 的实际字段。
- `docs/dev/PROJECT_ADAPTATION.md`、AGENTS 铁律 12 — core 不自动推断
  项目语义。

**测试（字段行为的可执行证据）**
- `sim/tests/regression/test_constraint_chain.py` — chain 的 `via` /
  `reason` / 退出码。
- `sim/tests/regression/test_frontier.py` — frontier 的 `reason` /
  `summary` / 未知信号 exit 1。
- `sim/tests/regression/test_deep_cross_module.py` —
  `verify claim` 的 `verified` 与深层 `paths`。
- `sim/tests/regression/test_tb_join.py` — `--from-snapshot` 用法。

---

## 6. 本次核对实际跑过的命令

在仓库根目录、fixture 上执行（`python3 run_cli.py` 与安装后的
`sv_query` 等价）：

```bash
python3 run_cli.py capabilities --json
python3 run_cli.py scope calc_chain -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py instances --filelist sim/tests/fixtures/minimal_3module/filelist.f --json
python3 run_cli.py hierarchy --filelist sim/tests/fixtures/minimal_3module/filelist.f --json
python3 run_cli.py ports top_minimal --filelist sim/tests/fixtures/minimal_3module/filelist.f --json
python3 run_cli.py params top_minimal.sa1 --filelist sim/tests/fixtures/minimal_3module/filelist.f --json
python3 run_cli.py connections top_minimal.sa1 --filelist sim/tests/fixtures/minimal_3module/filelist.f --json
python3 run_cli.py class rnd_item --relations -f sim/tests/fixtures/constraint_neighborhood.sv --json
python3 run_cli.py drivers calc_chain.s2 -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py loads calc_chain.s1 -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py paths calc_chain.a calc_chain.y -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py dataflow analyze calc_chain.a calc_chain.y -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py controlflow analyze calc_chain.s3 -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py controlflow list-conditioned -f sim/tests/fixtures/golden_mini/if_demo.sv --json
python3 run_cli.py trace impact calc_chain.a -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py trace frontier top.x -f sim/tests/fixtures/arch_pair.sv --json
python3 run_cli.py trace evidence calc_chain.s1 -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py trace profile calc_chain.s1 -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py trace lookup --path calc_chain.s1 --path nope -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py trace manifest --path calc_chain.s1 -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py verify consistency -f sim/tests/fixtures/deep_cross_module.sv --json
python3 run_cli.py verify claim --claim '{"type":"path","from":"top.x","to":"top.y"}' -f sim/tests/fixtures/deep_cross_module.sv --json
python3 run_cli.py verify claim --claim '{"type":"path","from":"top.nope","to":"top.y"}' -f sim/tests/fixtures/deep_cross_module.sv --json
python3 run_cli.py verify structural -f sim/tests/fixtures/deep_cross_module.sv --json
python3 run_cli.py trace constraints rnd_item.a -f sim/tests/fixtures/constraint_neighborhood.sv --json
python3 run_cli.py trace constraint-neighborhood rnd_item.a -f sim/tests/fixtures/constraint_neighborhood.sv --json
python3 run_cli.py trace constraint-chain rnd_item.a rnd_item.d -f sim/tests/fixtures/constraint_neighborhood.sv --json
python3 run_cli.py trace constraint-chain rnd_item.a rnd_item.e -f sim/tests/fixtures/constraint_neighborhood.sv --json
python3 run_cli.py trace tb-join tb_item.rcont -f sim/tests/fixtures/tb_join_tb.sv --from-snapshot tb_join_snap --json
python3 run_cli.py trace covergroups -f sim/tests/fixtures/golden_mini/coverage_demo.sv --json
python3 run_cli.py trace coverpoints coverage_demo.sel -f sim/tests/fixtures/golden_mini/coverage_demo.sv --json
python3 run_cli.py trace covergroup cg_sel -f sim/tests/fixtures/golden_mini/coverage_demo.sv --json
SVQ_SNAPSHOT_DIR=/tmp/svq_snap python3 run_cli.py snapshot save sim/tests/fixtures/golden_mini/calc_chain.sv --tag inv_test --json
SVQ_SNAPSHOT_DIR=/tmp/svq_snap python3 run_cli.py snapshot list --json
SVQ_SNAPSHOT_DIR=/tmp/svq_snap python3 run_cli.py snapshot compare inv_test inv_test --json
SVQ_SNAPSHOT_DIR=/tmp/svq_snap python3 run_cli.py snapshot delete inv_test --force --json
python3 run_cli.py stats -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py search s1 -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py graph nodes -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py graph edges -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py graph subgraph calc_chain.s1 -f sim/tests/fixtures/golden_mini/calc_chain.sv --json
python3 run_cli.py filelist prune --filelist sim/tests/fixtures/minimal_3module/filelist.f --top top_minimal --json
```

> 说明：`sim/tests/fixtures/golden_mini/filelist.f` 内含其他机器的绝对路径，
> 因此多文件核对使用 `sim/tests/fixtures/minimal_3module/filelist.f`
> （其内容同样为绝对路径，但当前环境可解析）。
