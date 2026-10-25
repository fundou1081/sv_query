# 已知限制

> 更新: 2026-08-26 23:00 GMT+8 (case27 架构决策生效)
> 测试状态: 见 [INDEX.md 当前基线](INDEX.md#-当前基线-单一真相源--计数只写在这里)
>
> **架构决策**: `docs/architecture/case27_signal_graph_completeness_decision.md` (D1-D5 锁定, 含 v11-only)

### 5. pyslang 版本兼容代码 (~1.5h 清理, iter_034)

D5 锁定: 以后仅支持 v11 API, 不再考虑 v9/v10 兼容.

**当前 compat shim**: `src/trace/core/_pyslang_compat.py` (8327 bytes)
- `_detect_version()` — 版本探测 (v11 不需要)
- `_KIND_ALIASES` — kind 名字 v10/v11 映射
- `is_syntax_list` / `iter_syntax_list` — v11 已拆 plain list, 可能不需要
- 5 个调用点 (uvm_testbench_extractor / expression_tree / semantic_adapter / subroutine_expander / base)
- 4 个 hasattr probes (mig_validator / semantic_adapter x2 / graph_builder)
- 6 处 `[Stage 6] v10/v11 兼容` 注释

**iter_034 计划**: 全部清理, 直接用 `pyslang.ast.*` (v11 only API)

---

## 当前已知限制

### 1. generate-if/else 限制 (pyslang 已知)

当 `generate if (PARAM)` 控制哪个 always 块运行时，pyslang 的 `get_always_blocks()` 可能不枚举 else 分支。

**影响**: picorv32 `alu_shr`, `alu_add_sub`, `alu_eq`, `alu_lts`, `alu_ltu` 等信号没有 leaf driver。

**文档**: V6.4 `test_known_limitations.py`

### 2. ElementSelect 解析 (pyslang 已知)

`arr[N]` 被 pyslang `_get_signal` 解析为两个独立信号，位索引丢失。

### 3. pyslang 内存不足问题 — **归因已更正 (iter_185)**

> ⚠️ 2026-09-08 iter_185: "内存不足导致 elaboration 静默失败" 的归因**已被证伪** —
> 真因是 `SVCompiler` 的 `SourceManager` 生命周期 bug (buffer 提前释放 → 符号名悬垂
> `string_view`), 已修复。修复后同一输入 3 次完全一致 (stdev = 0.0)。
> 内存压力仍然会让 pyslang 变慢/失败, 但不再产生乱码名与结果漂移。

**文档**: `docs/PYSLANG_MEMORY_ISSUE.md` (已按真因改写),
`docs/task_tree/iterations/iter_185_slang_sourcemanager_lifetime.md`

### 3.1 `-f` / `--file` 传 filelist → 原生 SIGTRAP (用法不一致, 不是上游缺陷)

> **方豆判定 (2026-09-09)**: 这是**用法不一致**问题 —— **不向上游 pyslang 报 issue**,
> 记录清楚并**避免这样使用**即可 (见 [DISCIPLINE.md §4](dev/DISCIPLINE.md))。

**正确用法**: `-f` / `--file` 只接受 SystemVerilog **源码**; filelist 一律用 `--filelist`。

```bash
sv_query visualize module -f project.f          # ❌ 禁止 (用法错)
sv_query visualize module --filelist project.f --target top   # ✅
sv_query stats -f design.sv                     # ✅ 单文件源码
```

**为什么会崩 (机制)**: filelist 的内容 (如 `/path/to/mod.sv`) 被当源码解析 →
slang 走 script 模式 → 根节点成了**表达式** (`DivideExpression`, 因为路径里有 `/`) →
`pyslang` 的 `Compilation.addSyntaxTree()` **直接 SIGTRAP** (exit 133, 无输出、
无 Python 异常可捕获, `faulthandler` 也拿不到栈)。

**本项目已加的守卫 (机械保障)**: `src/trace/core/compiler.py::_reject_non_design_unit`
在 `addSyntaxTree` 之前检查根节点类型, 表达式根 → 抛可行动的 `CompilationError`
(提示"请用 `--filelist`")。合法输入 (根节点 `CompilationUnit` /
`ModuleDeclaration` / `ClassDeclaration` / 空文件 / 仅 `define`) 不受影响。

回归测试: `sim/tests/unit/test_compiler_non_design_unit_guard.py` (守卫失效时测试进程
会以 exit 133 死掉, 信号明确)。

### 3.2 `MissingTimeScale` 诊断不触发 → `diagnose timescale` 形同虚设 (iter_234 发现)

`svq diagnose timescale` (原 `fix timescale`) 的判定依赖编译器报 `MissingTimeScale`,
但**实测当前 pyslang + 我们的编译配置下该诊断不触发**:

```
# 构造: 缺 `timescale 的模块 (含 #5 延迟)
svq diagnose timescale --filelist p.f   →  ✅ No MissingTimeScale errors found. Nothing to fix.
```

推断: 该诊断可能只在特定选项/上下文下出现 (e.g. 命令行 `--timescale` 未给 + 需要时间语义的构造),
而我们没有开启对应条件 → **命令对任何输入都返回"无需修复"**。

**旁证**: 仓库里原有两个 `--apply` 端到端测试**早已被注释** (注释写着"如果 pyslang 不报 MissingTimeScale…"),
说明这条路径从未被真正验证过。

**当前处置 (iter_234)**: 不掩盖 —— 写入逻辑抽成 `tools/fix_timescale.py::apply_timescale_to_files()` 直接单测
(写入 + `.bak` + idempotent 已验证); 命令本身的"触发条件"问题**待单独诊断** (新任务, 需查 pyslang 选项)。

### 3.3 查询作用域与跨模块遍历 (iter_240)

`loads` / `drivers` / `fanin` / `fanout` 的跨模块能力**按查询作用域开关**:

| 查询形式 | 行为 |
|---|---|
| 全局 (`module=None`, 即不给 `--module`) | **跨模块**: 端口↔内部信号映射成为遍历的一步 (每跳 1 层深度) |
| 限定 (`--module M`) | **不跨模块**: 只答 M 内 (保护"在 M 里看"的语义与 golden 断言) |

**已知不足 (登记, 未修)**:

| # | 问题 | 状态 |
|---|---|---|
| 1 | `--from-snapshot` 模式没有 MIG (快照只存图) | ✅ **已修 (iter_278 实测)**: 单一命名空间后, 跨模块端口边**就在图里**, 快照查询与 live 逐条一致 (`loads`/`impact` 实测相同结果) |
| 2 | `distance` 字段恒为 1 | ✅ **已修 (iter_278)**: `trace_common.attach_distances()` 在响应组装阶段按 BFS 最短跳数填真实 distance (不 mutate 图节点) |
| 3 | **两套路径实现**: `paths` (无向) 与 `dataflow analyze` (有向但不跨模块) | ✅ **已修 (iter_268)** —— 见下方 |

**已修 (iter_268)**: 两套路径实现的分歧，根因由 [POC iter_267](poc/2026-10-23_native_connectivity.md) 定位:

| 根因 | 修法 |
|---|---|
| `PathResolver.find_path` 把 dst 规范化成"模块定义命名空间"的影子节点 | 端点不再改写 —— 返回路径**必须以用户请求的 dst 结尾** (POC 实测修前 65~78/120 个采样对端点漂移) |
| `dataflow` 的 `_resolve_cross_module` 把图里**已存在**的实例端口改写成影子节点 (孤立节点) | 图里已有的 id 一律原样返回；只有不在图里的名字才走旧映射 |
| `dataflow` 因此对一切跨模块查询报不可达 | 修后 `top_minimal.valid_i → top_minimal.sa1.valid_i` 等跨模块对可达 (实测 3/3) |
| 无向/有向语义混在一个入口 | `PathResolver` 增加 `directed` 模式；CLI 增加 `paths --directed`，与 `dataflow analyze` 走同一张有向图 |

**验收**: `sim/tests/unit/test_path_directed_parity.py` 锁定三条不变式 ——
① `paths --directed` 与 `dataflow analyze` 对同一对信号结论一致 (6 对)
② 逆流查询有向不可达、无向可达 (语义差异显式)
③ 任何返回路径的最后一项必须等于请求的 dst

**遗留**: 影子节点仍留在图里 (占 30~38%)，只用于"按模块定义名查询"；
`--from-snapshot` 无 MIG 与 `distance` 恒为 1 两条未动。

**已修 (iter_241)**: 原第 3 条 `LoadTracer` 无跨模块支持 —— 实测比登记更严重:
`module=None` 时它自己拼 `f"{module}.{signal}"` 得到 `"None.sig"`, 连**单模块**查询都
静默返回空且 `root` 是伪造 id。根因是**存在第二份遍历实现** (`GraphTraversal` 子类);
已改为 `SignalTracer.trace_fanout` 的薄适配层并删除死基类, `trace_loads` 与
`trace_fanout` 现由测试锁定为逐节点一致 (`sim/tests/unit/test_load_tracer_adapter.py`)。

### 3.4 `trace impact` 的风险分是**未标定的启发式** (iter_266)

**可观察后果** — 同一个设计，风险分的绝对值没有物理含义，只有**同一份图内的相对排序**有意义：

| 场景 | 实测输出 |
|---|---|
| `trace impact calc_chain.a -f calc_chain.sv` | 8 条路径全部 `HIGH`（32~34 分） |
| 其中任一路径 | 分数构成 = 路径长度 2×5 + 扇出 1×2 + **无 SVA/无 covergroup +20** + 条件 +10 |
| 换一个"有 SVA 有 coverage"的信号 | 同样路径长度/扇出下，分数直接少 20 → 可能从 HIGH 掉到 MEDIUM |

**结论**：等级主要由"有没有断言/覆盖率"驱动（这部分是**真实数据**，来自
`SVAExtractor` / `CovergroupExtractor`），其余权重（长度 ×5、扇出 ×2、名字含
`clk|rst` +20、有条件 +10）是**手工设定、从未用真实项目标定**。

**因此**：
- ❌ 不要把它当"改动风险有多大"的度量，也不要跨设计比较分数
- ✅ 可以在**一次运行内**用它排序（"先看哪条路径"）
- 输出里已加 `result.risk_model = "heuristic_v1 (未标定; 仅用于相对排序)"` 做显式标注

**要修的前提**：拿真实项目 + 已知 bug 位置做标定（哪些信号改动真的引发问题），
否则调权重只是换一组同样未经验证的魔数。

### 3.5 generate 块内的局部信号作用域 —— **已修 (iter_274)**

**原缺陷 (iter_273 实测)**：同一个 generate 循环里每轮各有一个同名局部信号时，它们会合并成
**一个**节点 `top.local_wire`，并产生跨轮假边（`din[0..3]` 全部驱动它，它又驱动全部 4 个实例端口）。

**修法（方案 A：作用域限定）**：

| 位置 | 改动 |
|---|---|
| `semantic/exprs_drivers.py` | `get_assignments` 进入 GenerateBlock(Array) 时，把块路径（如 `G[0]`）+ 块内局部声明名并入 ctx |
| `extractors/_common.py::get_signal` | 名字命中"块内局部"时返回带块路径的名字（`G[0].local_wire`） |
| `semantic/exprs_drivers.py` | 新增 `get_generate_locals_index()`：`{块路径 → 块内声明名}`（供连接侧复用） |
| `connection_extractor.py` | 实例端口连到块内局部信号时，父侧 id 用**完整块路径**（不再剥掉 generate 段） |

**验证**：`sim/tests/unit/test_generate_local_scope.py` 从 xfail 转正 ——
`top.G[i].local_wire` 四个独立节点、`din[i] → G[i].local_wire → G[i].u_leaf.a` 无跨轮边。
`test_genvar_for.py` 同步断言每轮各自的 `top.g[i].w`。


### 3.6 位级 drive/load 精度 —— **部分精确**（iter_289 审计）

**能精确的形态**（有测试/实测）：

| 形态 | 例子 | 实测 |
|---|---|---|
| 显式位赋值 | `assign y[3] = a[7];` | `fanin(y[3]) = {a[7]}` ✅ |
| 寄存器位 | `q[3] <= d[1];` | `fanin(q[3]) = {d[1]}` ✅ |
| struct 成员位 | `y = p.addr[3];` | `fanin(y) = {p.addr[3]}` ✅ |
| generate per-entry 位 | `G[i].u.a(a[i]) → y[i]` | 各 entry 独立 ✅ |
| 两侧都有位节点的跨模块位 | 子模块内部有 per-bit 逻辑 | 位对位贯通 ✅（iter_137/143 的既测场景） |

**不能精确的形态**（总线/切片粒度，属既定契约）：纯总线直连、拼接、动态索引、
叶子端口边界（`iter_126`/`iter_132` 的"粒度停"）。

**但存在 3 类会**误导 agent**的反例（不是"粒度粗"，是答案里出现不成立的源/漏源）**：

1. **切片 LHS 的跨位污染**（`assign y[7:4]=a; assign y[3:0]=4'h0;`）：

   ```
   fanin(top.y[5]) = [top.a, 4'b0]    ← 4'b0 只驱动 bit[3:0]，与 y[5] 无关
   fanin(top.y[2]) = [top.a, 4'b0]    ← top.a 只驱动 bit[7:4]，与 y[2] 无关
   ```
   根因：`y[7:4]`/`y[3:0]` 是 **slice 节点**（未展开成 per-bit），缺位回退到父总线后
   `BIT_SELECT` 聚合把两个切片的驱动合并。

2. **多驱动的跨位污染**（`assign y=a; assign y[3]=1'b1;`）：

   ```
   fanin(top.y[4]) = [top.a, 1'b1]    ← 1'b1 只驱动 bit[3]
   fanout(top.a[3]) = [top.y]         ← 无法区分 a[3] 与 a[4]
   ```
   根因同上：`top.y[3]` 的 `BIT_SELECT` 聚合边在父总线提升时被无条件采用。

3. **位节点断链**（表达式结果取位）：

   ```
   assign s = a & b; assign y = s[3];   → fanin(top.y) = [top.s[3]]  ← 缺 a/b
   assign z = w[3]; (w 由子模块总线驱动) → fanin(top.z) = [top.w[3]] ← 缺 w 的上游
   ```
   根因：`s[3]`/`w[3]` 只有 `BIT_SELECT` 出边、没有 incoming 驱动；提升到父总线
   要求 `not drivers`（iter_128 的防污染条件），而此路径下已经 append 了该位节点，
   于是**停在死胡同**，不返回父总线的真实驱动。

**根因位置**：
- `src/trace/core/query/signal.py::_trace_missing_node`（缺位回退不带位索引 → 无法过滤切片父）
- `src/trace/core/query/signal.py::_maybe_lift_to_parent_bus`（`not drivers` 门槛挡住死胡同位）
- `src/trace/core/graph_builder.py::_expand_bus_conn_bit_bridges`（只在**两侧都有位节点**时建位桥）

**测试缺口**：位相关测试 27 个（3 个文件）+ A2 若干，但断言多为"节点存在 / 边存在 /
`len(drivers)>=1`"；`test_accuracy_a1_a2.py:97` 明确接受总线粒度结果。
**没有**任何测试断言"按位对应关系"或"不得出现跨位源"。所以：
当前测试不足以支撑"位精确"的对外表述。

**建议修法（按性价比）**：
1. F1（正确性，小）：缺位回退带位索引 `X[n]`，遍历父总线的 `BIT_SELECT` 子节点时
   只取 `parent_bit_start <= n <= parent_bit_end` 的那些 → 消除反例 1/2 的污染
2. F2（完整性，小-中）：位节点"无 incoming 驱动且父总线有驱动"时，补一次父总线追溯
   （带 seen 保护，防 iter_128 的兄弟位污染）→ 反例 3 不再断链
3. F3（精度，中）：slice 节点按位展开（`y[7:4]` → 4 个位节点 + 偏移映射），
   让切片 LHS/链路也能位对位（D/S 类从"切片粒度"升级为"位精度"）
4. F4（设计决策）：bus↔无位节点侧合成位桥（iter_126 曾明确"不造假节点"），需方豆拍板

### 4. 测试已知失败 (55 个，全部为 pre-existing)

| 模块 | 数量 | 原因 |
|------|------|------|
| test_fix_timescale | 6 | MissingTimeScale 检测差异 |
| test_fix_report | 2 | 报告格式变化 |
| test_deadlock_cli | 1 | naplespu filelist 不存在 |
| test_dataflow_else_if | 36 | 条件表达式比较差异 |
| test_dataflow_else_if_typo | 4 | 同上 |
| test_dataflow_golden | 3 | golden 比较差异 |
| test_ventus_all_viz | 5 | arch/trace/PNG 波动 |

**所有 55 个均为既存问题，与 V6.5-V6.7 改动无关。**

---

## 已修复限制

| 限制 | 修复版本 |
|------|---------|
| Binary operator 分解无法检测 op | V6.5 (DriverSource→SignalSource) |
| expression/bit_slice 用纯字符串存储 | V6.5 (SignalSource 结构化) |
| 可视化 6 个渲染器分散 | V6.7 (VizData 统一管线) |
| DriverInfo 不含位精确信息 | V6.6 (source: SignalSource) |
| pipeline 图 5 种变体混乱 | V6.6/V6.7 (deprecated load_dot) |
| NodeKind/EdgeKind 混乱 | V6.6 (命名空间分区) |
| interface 设计构建崩溃（成员桥 `TraceNode` 漏 `width`） | iter_285 (P2.1) |
| `fanout(<bit>)` 位节点不存在时返回空集（与 fanin 总线下沉不对称） | iter_285 (P2.1) |

---

## ⚠️ 2026-08-26 case27 架构决策生效

### 接受为设计选择 (不再修)

| 项 | 原因 | 决策文档 |
|---|---|---|
| **case27 Gap 1** — `acc[i]` 显示模板 label `[i]` 而非 `[0..4]` | Semantic API 不展开 genvar 替换 | D2 |
| **case27 Gap 2** — generate-block 内 `prod[0..3]` 4 个 `*` op 节点缺失 | Semantic API 不 walk generate-block body | D2 |
| **generate-block 整体展平** | 可视化彻底展平到 module 顶层 | D3 |

### 仍待修 (核心约束: 信号图信息完整)

| 项 | 优先级 | 决策 |
|---|---|---|
| **case27 Gap 3** — module 顶层 `sum_out` ternary `?:` op 节点缺失 | ⭐⭐⭐⭐⭐ | iter_033 必做 |
| **"信号图信息完整" 定义** (A/B/C/D) | ⏳ 待用户选 | 待 Feishu 回复 |

---

## 📞 相关引用

- 决策文件: `docs/architecture/case27_signal_graph_completeness_decision.md`
- iter_032 (前置已知问题): `docs/task_tree/iterations/iter_032_case27_semantic_gaps.md`
- iter_033 (待开工): `docs/task_tree/iterations/iter_033_*.md` (创建中)
