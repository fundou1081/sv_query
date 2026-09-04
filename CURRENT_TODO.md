# CURRENT_TODO — 当前正在做的事

> **唯一入口**: 本文件是"此刻在做什么"的**唯一稳定追踪点**。
> **位置固定**: 根目录 `CURRENT_TODO.md`, 路径永不变更。
> **更新时机**: 每次开始任务 / 完成 sub-task / 被打断切换任务时, 立即更新。
> **最后更新**: 2026-09-03 GMT+8 (门级原语 leaf cell 建模进行中, iter_112)

---

## 📍 分工 (避免和其他文件重复)

| 文件 | 职责 | 时间尺度 |
|---|---|---|
| **CURRENT_TODO.md** (本文件) | **此刻**在做的 1 个任务 + 它的 sub-task 勾选 | 小时 ~ 天 |
| `docs/ARCHITECTURE_TODOLIST.md` | 架构改造 7 项的长期追踪 (ROI / 工作量 / 状态变更日志) | 周 ~ 月 |
| `docs/TODO.md` | 版本级功能待办 (V6.8 / V6.9 / V7.0 ...) | 月 ~ 季 |
| `docs/task_tree/` | 任务迭代记录 (每次迭代一个文件, 详见 AGENTS.md) | 每次迭代 |

**规则**: 本文件**只写当前**。任务做完 → 归档到 `docs/task_tree/` + 更新对应长期 todolist → 从本文件移走。

---

## 🔥 当前任务

**门级原语 (Gate Primitive) 提取支持 — leaf cell 建模** (✅ 完成, iter_112)
> KoggeStone 摸底缺口: xor16.S[0..15] 全无 DRIVER + and/xor 触发 connection 无限递归
> (`and0.and0...` ×21)。方案 A: 原语建模为 leaf cell。
> [iter_112](docs/task_tree/iterations/iter_112_gate_primitive_support.md) / [任务文件](docs/task_tree/tasks/L2_gate_primitive_support.md)

| sub-task | 状态 |
|---|---|
| 1. adapter 层过滤 PrimitiveInstance (native/recursive 同步, parity 不破) | ✅ |
| 2. DriverExtractor: 原语输出 DRIVER 边 (输入端子→输出, 位选宿主作用域解析) | ✅ |
| 3. ConnectionExtractor: 不展开原语 + get_path 防自环兜底 | ✅ |
| 4. 测试: unit test_gate_primitive (8) + truth test_gate_primitive_truth (6, golden_dataflow_40 = 真实 xor16.v) | ✅ 14 passed |
| 5. 回归: **2869 passed / 0 failed / 7 skipped** (基线 2849 无损) + KoggeStone xor16.S/xor16_1.S 全部可达驱动 | ✅ |
| 6. 文档: iter_112 + iter_111 补记 + overview (rows 30-33) + 本表 | ✅ |

**当前**: ✅ **CLA 嵌套 generate 实例缺口修复完成** (iter_113, 方豆 "修这个新发现的generate")
> [iter_113](docs/task_tree/iterations/iter_113_cla_nested_generate_fix.md) /
> [任务文件](docs/task_tree/tasks/L2_cla_nested_generate_fix.md)
> 双根因: ① graph_builder.walk 不下钻 generate (driver paths 无 generate 实例 —
> cordic 同受其害, "rotator DRIVER 100" 实为 connection 端口自环) → walk 用
> child.hierarchicalPath 下钻; ② connection inst_module_name 在 inst==type 时回落
> parent → 自环递归 (iter_112 原语同根因型) → type token 权威, 去 '!= inst_name' 守卫。
> 验证: 合成复现两命名风格 recursive=0 + 内部 DRIVER 全提取; 真实 CLA
> (golden_dataflow_41, inst==type 真身) generators[0..3] 内部逻辑可达。

| sub-task | 状态 |
|---|---|
| 1. 诊断: 双根因定位 (walk 不下钻 + inst_module_name 回落) | ✅ |
| 2. 修根因: walk hp 下钻 + connection type token 权威 | ✅ |
| 3. 测试: unit test_nested_generate_instance (4) + truth test_cla_generate_truth (6, 真实 CLA fixture) | ✅ 10 passed |
| 4. 回归: 受影响 47 passed 零回归; 全量结果见 commit | ✅ |

**iter_114 完成** (truth target 模式升级): cordic/genfor truth 盲区修复 — generate 实例内部逻辑真断言 (cordic rotator x_1/y_1/z_1×15 驱动 / genfor rot 实例作用域), 旧 'DRIVER>50' 实为 connection 端口自环。见 [iter_114](docs/task_tree/iterations/iter_114_truth_target_mode_upgrade.md)

**iter_115 完成** (gate 端子方向 G-1): 输出端子判定 = slang Assignment 包裹 (多输出 buf/双向 tran 不再错); buf o2←a / tran t⇄a / UDP 逐端子; unit +5。见 [iter_115](docs/task_tree/iterations/iter_115_gate_terminal_direction.md)
**iter_116 完成** (7 skip 处置): serv 解锁 (filelist+serv_top 747KB SVG), neorv32 (VHDL)/zipcpu (wrapper 重构) 移除, d1 lookupName mutex 收编 (直排 -c 每 case subprocess; 真根因 = 同进程累计查询必崩非 pytest). skip 7→0。见 [iter_116](docs/task_tree/iterations/iter_116_skip_cleanup.md)


**当前**: ✅ **索引段加倍假节点修复完成** (iter_117, 方豆 "开工, 修复这个问题")
> [iter_117](docs/task_tree/iterations/iter_117_index_segment_doubling_fix.md) — get_path 父路径含索引段时 gen_block 置 None; aes 84→0 / dblclockfft 63→0; unit +3, 74 批次零回归
> aes U_SUB.ROM[4].ROM[4] (84) / dblclockfft GENSTAGES[0].GENSTAGES[0] (63/模块):
> 索引段在已含索引父路径下二次拼接。
> [tasks/L2_index_segment_doubling_fix.md](docs/task_tree/tasks/L2_index_segment_doubling_fix.md)

| sub-task | 状态 |
|---|---|
| 1. 诊断: 两形态最小复现, 定位 driver walk / connection 谁二次拼接 | ⬜ |
| 2. 修根因 | ⬜ |
| 3. 测试: unit 两形态 + 真实验证 aes/dblclockfft recursive→0 | ⬜ |
| 4. 回归 + iter_117 文档 + overview + 提交 | ⬜ |

**当前**: ✅ **极端场景验证完成** (iter_118, 方豆 "构造极端场景确认正确性")
> 9 类极端场景断言 (深嵌套 gen/门级/多驱动/反馈/0 层/深 fanin):
> **修 1 缺口**: generate assign RHS 位选丢 genvar 索引 (S8 x[i]=x[i-1] RHS 落总线
> → fanin 死端; case27 acc[i] 同病, iter_035 起潜伏) — _fold_sel ctx 求值修.
> 新 unit +3; case27 per-index 改善.
> [iter_118](docs/task_tree/iterations/iter_118_extreme_verify_rhs_index.md)

**当前**: ✅ **generate 实例连接 key 碰撞修复完成** (iter_120, "继续" 深挖 iter_119 观察)
> [iter_120](docs/task_tree/iterations/iter_120_gen_conn_key_collision.md) — 双根因:
> ① legacy get_generate_instances 嵌套丢 root (iter_117 后冗余 → 移除);
> ② module_to_path key 无父路径多实例碰撞 → 逐实例 paths_by_info.
> minimal 0→4 连接 / 4 层 4 条全对; 101 批次零回归; unit 13→14.
> [iter_119](docs/task_tree/iterations/iter_119_conn_rangeselect_naming.md) — semantic RangeSelect left/right+selectionKind 求值, S2 占位 2→0, 切片 [hi:lo] 命名; unit +3. 观察: slang 合并相同 generate entry 的枚举边角 (G2[0] 归属) 待后续探查.
> S2 四级嵌套 `.a(a[i*4+:4])` 占位 `u_m2.a[?]` — semantic RangeSelect 无
> .selector (left/right 在 expr), _eval_select_index 不支持 Multiply.
> [tasks/L2_conn_rangeselect_naming.md](docs/task_tree/tasks/L2_conn_rangeselect_naming.md)

| sub-task | 状态 |
|---|---|
| 1. 诊断: S2 复现 + S1 为何 OK (fold 差异) | ⬜ |
| 2. 修 RangeSelect 求值 + 乘除 | ⬜ |
| 3. unit + 回归 | ⬜ |
| 4. iter_119 文档 + 提交 | ⬜ |

**当前**: 等待方豆指示 (iter_122 #8 ✅ / #7 专项尝试已回退, 阻塞记录)
> #8 covergroup cross 匿名名合成 ✅ (iter_122, covergroup 28 passed)
> #7 inline-with 专项 (iter_123 探索) 已回退: 语义过程体是 Statement 包装
> (BlockStatement 不可迭代), 全语法扫经 UnifiedTracer adapter.root 后 syntax
> 可达性不一致 (疑似 tracer 重建/缓存路径差异) — 需 UnifiedTracer 把
> compiler/syntax 传入 ClassGraphBuilder 的专项改造 + statement 包装 attr 下钻.
> 复现 CONSTRAINT-inline (/tmp/adv_verify.py)。见 iter_122 文档.
> [iter_121](docs/task_tree/iterations/iter_121_sva_adversarial_fix.md) — 6 缺口全修
> (formal 参数替换/sequence 展开/local var/函数/generate 内断言/option 污染);
> 对抗 6 场景全绿, unit +8, SVA 83 零回归。
> **下一个**: iter_122 — backlog 7-8 (constraint randomize-with inline 约束节点 /
> covergroup cross name 空串)
> 修 backlog 对抗发现 1-6 (formal 参数替换 / sequence 展开 / local var / 函数 /
> generate 内 assert / option 污染)。次要 7-8 (constraint inline / covergroup cross)
> 排 iter_122。复现: /tmp/adv_verify.py

| sub-task | 状态 |
|---|---|
| 1-4: SVA 语义 (参数/序列/局部/函数) | ⬜ |
| 5-6: generate-sva + option 污染 | ⬜ |
| 测试 + 回归 + iter_121 文档 | ⬜ |

**对抗验证发现 (方豆 "constraint covergroup sva 对抗")** — 待修 backlog, 建议按序处理:

**SVA 提取器 (SVAExtractor) — 4 个语义缺口** (全有最小复现):
1. **formal 参数未替换**: `property p_arg(x,y); ... endproperty; assert property(p_arg(a,b))` —
   signals 提取成形式参 x/y + 序列名 s_arg, 实际信号 a/b 丢失
2. **sequence 引用不展开**: property 引用 sequence (多时钟/局部变量 case) —
   sequence 内信号 (a,b) 不进 signals (只列 s_seq 名); 多时钟 case clk2 在列 clk 不在
3. **局部变量当信号**: `(a, tmp = b)` 的 local var tmp 被列进 signals
4. **用户函数当信号**: $countones({b, f(data)}) 里自定义函数 f 被列进 signals

**SVA 结构性缺口**:
5. **generate-for 内 assert property 0 提取** (per-entry 断言全丢)
6. **covergroup 的 option/type_option 被 SVA 当 property** (interface 内 cg → prop_names
   含 top.u_bus.option/type_option — 跨域污染)

**constraint / covergroup 次要**:
7. constraint `randomize() with {}` inline 约束不产 CONSTRAINT 节点 (全家桶 8 类正常:
   inside/dist/if/imp/foreach/solve/unique/soft 全在)
8. covergroup cross 的 name 为空串 (coverpoint/bins 正常; generate 内 cg 按迭代重复但无索引)

无崩溃/占位/加倍 — 属提取"内容正确性"缺口。复现: /tmp/adv_verify.py + /tmp/adv_probe.py

**backlog (新发现, 待修)**: **connection 侧 RangeSelect 连接命名恒 '?'** —
S2 四级嵌套 `.a(a[i*4+:4])` 出占位 `u_m2.a[?]`; 根因方向: _conn_expr_to_signal
RangeSelect 取 expr.selector (semantic RangeSelect 无 .selector, left/right 在
expr 上) → '?' 恒; _eval_select_index 不支持 Multiply. 最小复现 S2 已备
(/tmp/extreme_scan.py), 建议下个修.

**backlog (新发现, 建议下一个修)**: **索引段加倍假节点** (iter_116 摸底 target 重扫发现, 多项目真实复现):
- aes Top_PipelinedCipher: **84** 个 — `U_SUB.ROM[4].ROM[4]` (实例下 InstanceArray 段重复)
- dblclockfft fftmain/ifftmain: **63** 个/模块 — `p3.STAGES.FOR.GENSTAGES[0].GENSTAGES[0].genmpy` (实例下嵌套 generate 段重复)
- 对照: genfor (顶层 gen) / CLA (实例下单层 gen) 正常 → 触发 = 索引段在**已含索引的父路径**下被二次拼接 (connection/driver 路径构建). cordic 同型需重验.
- r22sdf (FFT 1760 节点) / zipcpu-cordic / windowfn / abs_mpy 等 target 重扫 **clean** — 摸底结论升级: 仅 aes/dblclockfft 受此影响.

**backlog (未启动)**: 1. gate 遗留改进 G-2 (drive strength/delay 进图) + G-3 (UDP table 可视化) — tasks/L2_gate_primitive_support.md (G-1 ✅ iter_115); 2. cvfpu 全量覆盖 (vendor common_cells + PACE override) — 家族已由 fpnew 覆盖, 低优先



## ✅ 最近完成 (保留 3 条汇总, 逐项细节看 git log + docs/task_tree/iterations/)

| 完成时间 | 任务 | 产出 |
|---|---|---|
| **2026-09-02** | **测试资产扩充 + 缺陷修复收尾 (iter_086~108)** | truth 层 32→130 测试 (T1-T12 扩充 + A-F 修复断言); 缺陷 A-F (expression 字节切片 / net-decl 位宽 / LHS concat zip / ternary 常量 / part-select 宽度 / generate-if always) + ELK dangling + #23/#24 generate 单块 wire 全修; integration 419+0 历史首次全绿; 全量 2843 passed. 迭代记录 iter_086~108 |
| **2026-09-02** | **Truth 层扩充 T1-T12** | 12 文件 + 5 fixture, 集合相等断言; assign/clock-reset/case/位选/concat/function-task/parameter/alias/class/generate-if-case/SVG 布局/查询精确集. [iter_100 汇总](docs/task_tree/iterations/iter_100_t1_t12_wrapup.md) |
| **2026-09-02** | **B 组复查 + cli 3 失败修复** | iter_082 误分类纠正 (darkriscv SVG 断言 + 删 --no-strict); models.py width=None 序列化根因; unit+cli 1484 passed. [iter_086](docs/task_tree/iterations/iter_086_group_b_recheck_real_project_viz.md) / [iter_087](docs/task_tree/iterations/iter_087_cli_3_failures_fix.md) |

---

## 📋 下一个候选 (未启动, 不要自己开工 — 先问方豆)

- **工业算法模块开源项目调研** (进行中, 不在本任务内推进): 典型工业算法模块
  (CORDIC / 加法器族 / 乘法器族 / DSP 算法) 开源 RTL 摸底已 clone 至 `~/my_dv_proj/openrtl/`,
  REPOS.md 统一登记; 摸底缺口 → 逐个修复 (CORDIC iter_109~111, gate primitive 本任务)。
  剩余: fpnew/hardware/cvfpu 扫尾。
- ~~#7 — 迁 pyslang 11.0 native API~~ ✅ **已完成** (2026-08-29, iter_053-059)。
  遗留: CVA6/coralNPU/vortex 3 项目 strict 编译受阻 (pyslang↔项目语义不兼容),
  见 ARCHITECTURE_TODOLIST §#7。

---

## 📝 维护说明

1. **同时只有 1 个"当前任务"** — 多任务并行是错觉, 会导致两边都做不完
2. **切换任务前**, 把当前任务移到"已启动但暂停", 写清楚下一步是什么
3. **任务完成后**: 写 `docs/task_tree/iterations/iter_NNN_*.md` → 更新长期 todolist → 移到"最近完成"
4. **阻塞时必须写明**: 阻塞在什么、需要谁决策、有哪些选项和代价
5. **本文件必须和实际工作同步更新** — 文档更新和实际工作同等重要。
   任务开始前设为当前任务, 进行中逐项勾选, 完成后立即清出。
   完成判定 = **代码 ✅ + 测试 ✅ + 文档 ✅**, 只写完代码不算完成。
   详见 `AGENTS.md` → "📓 开发日志与迭代记录 → 任务前后必须更新文档"
