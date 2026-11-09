# 已知限制

> 更新: 2026-11-09 (P126.3 文档刷新 — 新增 §3.8~3.13 真实项目边界)
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
全设计图命令已于 2026-11-03 退役；请使用 `graph nodes/edges` 或 `scope`/`hierarchy`。
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

> **F1/F2 已修（iter_290）**：下面 3 类反例已消除；剩余的是"粗但不假"的粒度问题
> （F3 slice 展开 / F4 合成位桥，见文末）。

**曾存在的 3 类反例（iter_290 已修，保留原始证据供回归参照）**：

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

**修复结果（iter_290 / PLAN P5.1+P5.2）**：

| 反例 | 修复前 | 修复后 |
|---|---|---|
| 切片 LHS | `fanin(y[5])={a, 4'b0}` | `{a}`（4'b0 被位过滤掉） |
| 多驱动 | `fanin(y[4])={a, 1'b1}` | `{a}` |
| 死胡同位 | `fanin(y)={s[3]}` | `{s[3], a, b}`（补父总线） |
| 切片外悬空位 | `{u_sub.y}`（跨位污染） | `{}`（该位确实无驱动） |

回归守卫：`sim/tests/regression/test_bit_precision.py`（19 个：精确 6 + 防污染 5 +
防断链 4 + 粗粒度契约 4）。**注意**：load 方向仍是总线粒度（表达式驱动只有总线边），
不在本次修复范围。

**根因位置（历史）**：
- `src/trace/core/query/signal.py::_trace_missing_node`（缺位回退不带位索引 → 无法过滤切片父）
- `src/trace/core/query/signal.py::_maybe_lift_to_parent_bus`（`not drivers` 门槛挡住死胡同位）
- `src/trace/core/graph_builder.py::_expand_bus_conn_bit_bridges`（只在**两侧都有位节点**时建位桥）

**测试缺口**：位相关测试 27 个（3 个文件）+ A2 若干，但断言多为"节点存在 / 边存在 /
`len(drivers)>=1`"；`test_accuracy_a1_a2.py:97` 明确接受总线粒度结果。
**没有**任何测试断言"按位对应关系"或"不得出现跨位源"。所以：
当前测试不足以支撑"位精确"的对外表述。

**剩余项**：
1. 表达式位映射的**未覆盖算子**：比较/逻辑/归约/变量移位（所有位都可能影响）
   —— 仍返回总线（已文档化）
2. 有符号字面量/signed 信号的**扩展方向已建模**（P9）；`integer/int/byte/shortint/longint/time`
   位宽已修正（P10）。其算术逐位（进位链）仍无 per-bit 节点 → 位查询回落总线
3. 动态 part-select（`bus[base +: 8]`）不展开；变量移位不做逐位（运行期决定）
4. packed struct/union 聚合宽度/signedness、成员位段、成员位级查询桥已建模（P11/P12：
   `fanin(p.a[1])` → `p[5]`）；但更深层成员节点（`o.inner.a`）不会自动创建
5. `SVQ_BIT_BRIDGE=full` 在超大设计（新增位节点 > 30000）会部分展开（显式 warning）；
   默认 `one` 模式不做纯总线合成

> **F3 已修（iter_291）**：切片赋值按位展开（逐位节点 + 偏移映射），
> `y[5]`（`y[7:4]=a[3:0]`）现在精确回答 `a[1]`；`y=a[7:4]` → `y[2]` 回答 `a[6]`。
> 代价：verilog-axi 节点 +172（13,629 → 13,801，+1.3%）、边 +275；上限 20,000 个新节点。
>
> **F5 已修（iter_292）**：load 方向同样精确 —— `fanout(a[1])` → `y[5]`、
> `fanout(d[1])` → `q[3]`；位节点无负载时回退父总线（与 fanin F2 对称）。
>
> **P11 已落地（iter_299）**：packed struct/union 聚合宽度/signedness（含嵌套、端口/net）
> 与成员布局（`p.a` 4 位、父 p、位段 [7:4]；union 成员重叠 offset=0）。
>
> **P12 已落地（iter_300）**：packed 成员位级查询桥——`p.a[1]` ↔ `p[5]`，
> fanin/fanout 双向贯通；未被引用的成员节点自动补齐。缓存 1.4。
>
> **P10 已落地（iter_298）**：整数类型宽度修正——`integer` 从假 `(1,0)` 改为
> `(31,0)` signed，`byte/shortint/int/longint/time` 各归其位；懒建节点回填声明宽度；
> 缓存 1.2。integer 的逐位算术仍无 per-bit 节点（位查询回落总线）。
>
> **P9 已落地（iter_297）**：`TraceNode.is_signed` 入图（端口/net/变量/generate），
> 有符号字面量 `4'shF` 符号扩展为 1、有符号信号加宽高位映射到符号位；
> 拼接内字面量自决定（不扩展）。缓存版本 1.1，图基线因新增字段有意重生成。
>
> **P8 已落地（iter_296）**：常量位分解——`y=4'hA` 的 `fanin(y[1])` 返回 `1'b1`；
> 拼接字面量段 `{a,4'b10}` 逐位；`a & 4'hF` 高位零扩展后不再误导依赖。
> 无符号零扩展/32 位无宽度常量已覆盖；有符号字面量仍粗粒度（见剩余项 2）。
>
> **P7 已落地（iter_295）**：直接拷贝 `assign y=a` 在 `one` 模式下也位精确
> （源位节点存在时）；多驱动 `y=a; y[3]=1'b1` 两个驱动都返回；
> 纯拼接 `{a,b}` / `{a[3:0],b}` 按表达式顺序切段。
>
> **P6 已落地（iter_294）**：表达式按运算符逐位映射（查询层，图不变）——
> 位运算同索引、加/减/乘前缀/后缀、常量移位偏移、切片低位对齐；
> `fanin(y)` 从 `{s[3], a, b}` 变为 `{s[3], a[3], b[3]}`（位节点存在时）。
> 比较/逻辑/变量移位/纯拼接仍总线粒度（见剩余项 1）。
>
> **F4 已落地（iter_293，方豆拍板"要 f4"）**：bus↔bus 位桥合成。
> 默认 `SVQ_BIT_BRIDGE=one`（只补"一侧已有位节点"的连接，不改 iter_126 契约）；
> `=full` 时纯总线连接也按同索引合成位节点（verilog-axi 图 14.2k→31.5k 节点，
> 构建时间不变、gzip 0.4→0.7MB）。表达式/算术赋值两种模式都不展开。

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

### 3.7 信号追踪能力评审（2026-10-27）—— **P0 静默错误已登记**

完整盘点与 P0~P3 backlog: [architecture/trace_capability_review_2026-10-27.md](architecture/trace_capability_review_2026-10-27.md)。

**P0（已修，iter_302 / P13.1）**: 图缓存 key 未包含 `SVQ_BIT_BRIDGE` 模式 —— 先 `one`
建图后切 `full` 会命中旧图（实测 5 vs 37 节点）。现在 key 带 `-bb{one|full}`，
切换模式自动重建；同模式仍命中。

**P1/P2**: 粗粒度回退已显式标记（✅ iter_303 / P13.2：结果节点 `precision: bit|bus|constant`，
signal 级 `precision` + `coarse_fallback`）；`capabilities.bit_precision` 契约与 trace 输出 `is_signed`/`parent`/`bit_range`
已补（✅ iter_304 / P13.3）；深层成员已可建/可查（✅ iter_305 / P13.4：
`fanin(o.inner.a[1])` → `o[9]`）；三元/case 分支在源位节点存在时按位
（✅ iter_306 / P13.5）；多驱动/条件分支标记（`driver_count`/`multi_driver`/
`conditional_drivers`）与**静态索引 memory 位精度**（`mem[1][3]`）已补
（✅ iter_307 / P13.6）。动态 memory 索引**显式标注** `precision=unknown` +
`dynamic_index=true`，并沿数据流**递归传播**：含 depth=1、动态写污染整个数组
（✅ iter_308/P14.1 + iter_310/P16）、**条件/时钟/复位/控制依赖**（if/case、计算条件、
动态 clock/reset；✅ iter_311/P17）。参数/常量索引不误报（同 module 作用域解析）。

---

## 🆕 3.8~3.13 — 2026-11-09 刷新新增（P118~P125 期间的边界）

> 本节由 P126.3 文档刷新新增。全部来自 2026-11-07~11-09 的真实项目验证
> （OpenTitan UART / I2C、independent intake），**不是**推演。

### 3.8 Snapshot 的边证据：新 snapshot 有，**旧 snapshot 没有**

**事实**：`SignalGraph.to_dict()` 现在保存每条边的 `expression` / `bit_slice` /
`source_location {file, line_start, line_end, column}`；`from_dict()` 会恢复它们。

| snapshot | 边级证据 | 来源 |
|---|---|---|
| P119 之后重建的 | ✅ 有 `expression` / `bit_slice` / `source_location` | `src/trace/core/graph/models.py` |
| P119 **之前**生成的 | ❌ **没有**（旧格式仍可反序列化，但字段缺失） | 兼容性保留，不回填 |

**可观察后果**：拿旧 snapshot 跑 `intent=evidence`，模型拿到的仍然只是**节点声明行**
（`uart_core.sv:43`），会像 OpenTitan T3 那样把声明行当成赋值行 → **高置信答错**。
证据：[edge evidence 记录](validation/EDGE_EVIDENCE_2026-11-09.md) §1。

**怎么办**：改过边证据相关行为后**重建 snapshot**，别复用旧的。

### 3.9 Snapshot **不含源码文本**；CLI evidence 的 fallback **只给位置**

**事实**：snapshot 存的是图（节点/边/位置），**不存 `.sv` 源码**。

| 路径 | 能给什么 | 不能给什么 |
|---|---|---|
| `trace evidence --from-snapshot` | 边的 `file` / `line` / `expression` / `condition` | **源码原文**（不伪造 `source_text`） |
| tool 侧 `intent=evidence` | `edge_evidence[]`：src/dst/file/line/expression/condition/`source_line` | `source_line` 需 `SVQ_SOURCE_ROOT` 下能按 basename 唯一命中 |

**可观察后果**：CLI 的 snapshot 路径**只给位置**，不给源码行；agent 侧要拿到
`source_line` 必须能访问源码树（`SVQ_SOURCE_ROOT`）。没有源码树时，
snapshot 路径的 evidence 精度**低于** live 路径。

### 3.10 Path 语义：是 **canonical path**，没有"最短路径"这个意图

**事实**（P122）：`intent=path` / `intent=deep_path` 都走 canonical：

```text
CLI:  svq paths <src> <dst> --canonical --directed
      输出 canonical_policy=max_nodes_then_lexicographic + candidate_count
tool: intent=path / intent=deep_path  →  path_kind=canonical
```

**canonical 的定义**：在候选结构变体里选**节点数最多**的那条（tie-break 字典序），
**不是**最短路径。

**可观察后果**：
- **不存在**"给用户一条最短路"的意图。深度优先/最长优先才是当前语义。
- 用户拿到的 path 长度**不会**是最短路；OpenTitan T2 曾出现 13-hop vs 18-hop 的
  歧义，修法就是 pin canonical 而不是选最短。
- `--canonical` 与 `--all` 互斥；`candidate_count` 让 agent 能知道有几个候选。

证据：[canonical path 记录](validation/CANONICAL_PATH_2026-11-09.md)。

### 3.11 OpenTitan UART/I2C 的**依赖闭包仍是手工整理**的

**事实**：两个 block 的 filelist 都是**人工**整理出来的，`.core` 的依赖是 superset。

| block | 文件数 | 状态 |
|---|---|---|
| `hw/ip/uart` | 60 | **4 轮手工依赖整理**才可 elaborate（首次 0 errors 是 4 轮后的结果） |
| `hw/ip/i2c` | 67 | 复用 UART 规则，**首次即 elaborate**；但仍是手写 filelist |

`.core` 不能直接用：`filelist prune` 会保留 include-only `.svh`，需手工删。

**可观察后果**：
- 换 HEAD / 换 block 时**不能**假设 filelist 直接可用 —— UART 用了 4 轮。
- 依赖闭包**没有**自动化；`.core` → 可 elaborate filelist 仍需人工判断。
- 这是当前真实项目验证最大的**可复现性缺口**。

证据：[UART pilot](validation/OPENTITAN_PILOT_2026-11-09.md) §P2、
[I2C pilot](validation/OPENTITAN_I2C_2026-11-09.md) §P4。

### 3.12 Snapshot 工具**没有** MIG / connections / instances

**事实**：snapshot 只存 `SignalGraph`。

| 能力 | live | `--from-snapshot` |
|---|---|---|
| `drivers` / `loads` / `trace fanin/fanout` / `paths` | ✅ | ✅ |
| `connections` / `instances` / `hierarchy` | ✅ | ❌ **不支持**（需 live MIG） |
| evidence 源码原文 | ✅ | ❌（见 §3.9） |

`paths` 之所以可用，是因为 `PathResolver` 只依赖 `SignalGraph`，不依赖 MIG 虚拟跳转。

**可观察后果**：agent 用 snapshot 模式拿不到实例/连接信息，
必须回落到 live build（付一次 full build 成本）。**不能**伪装支持。

证据：[snapshot 记录](validation/SNAPSHOT_2026-11-07.md) §3。

### 3.13 任务语料是**自撰**的，不是用户研究

**事实**：现有 task corpus（38 个 instance，6 个任务文件）**我们自己 authored/frozen**：

- ground truth 大多由 `sv_query` CLI **反向**产生；
- 任务选择反映**我们知道怎么问**的内容；
- 唯一一次 tool 与 source 不一致时，**修正的是 task 而不是 tool**；
- 没有用户日志、issue、DV failure 的真实分布。

independent intake（P124/P125）是从 OpenTitan DV testplan/checklist 提取的 3 个任务，
ground truth 由 worker 先从 spec/source 人工确认、再 CLI 交叉验证 —— 比自撰强，但
**仍然是 task-author 与 tool 作者同一团队**。

**因此不能宣称**：

```text
用户最需要 discovery
用户不需要 fault localization
真实任务 50% 是 direct neighbors
```

**只能宣称**：

```text
我们的 benchmark 目前 50% 是 direct neighbors；
real-project 和 verify 样本不足；
discovery 只有 2 个，且模式单一。
```

**其他已知边界**（independent intake 实测）：只有 UART/I2C 两个 block；
fault localization / patch 类任务 = 0；不是外部 fault set。

证据：[任务分布](validation/TASK_DISTRIBUTION_2026-11-09.md) §3、
[intake 结果](validation/OPENTITAN_INTAKE_RESULTS_2026-11-09.md) §5。

### 3.14 covergroup elaboration 局限（pyslang builtin shadow）

**事实**：pyslang 对 covergroup body 内 `start`/`stop` 等内建名遮蔽，导致
`InvalidCoverageExpr` / `VoidAssignment` / `InvalidBinsTarget`。
sv_query **不绕过** Semantic AST 严格性，也不返回 partial coverage；
`trace covergroups` 失败时输出 `coverage_limitation` + 源码位置 +
`agent_action`，要求 agent 自己读 source。

**边界**：

- coverage 定义仍不可提取；
- 没有 bins 命中/仿真结果；
- 没有 TB-inclusive snapshot；
- 等 pyslang 修复后再打开 coverage 语义。

证据：[COVERAGE_LIMITATION_2026-11-09.md](validation/COVERAGE_LIMITATION_2026-11-09.md)。

### 3.15 FIFO/SRAM 跨边界查询断链

**事实**：FIFO 是时序存储，默认结构路径不跨 FIFO。P135 增加
`EdgeKind.FIFO` + `--through-fifo` 显式跨边界；父总线 fanin 会聚合 bit driver。

因此跨 FIFO 必须显式选择，默认 `paths` 仍返回 not_found；这不是静默降级。
详见：[P135_FIFO_CONNECTIVITY_2026-11-09.md](validation/P135_FIFO_CONNECTIVITY_2026-11-09.md)。


| 限制 | 修复版本 |
|------|---------|
| Binary operator 分解无法检测 op | V6.5 (DriverSource→SignalSource) |
| expression/bit_slice 用纯字符串存储 | V6.5 (SignalSource 结构化) |
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

### 2026-11-09 新增 §3.8~3.13 的证据文档

| 限制 | 证据 |
|---|---|
| §3.8 边证据 / 旧 snapshot | [validation/EDGE_EVIDENCE_2026-11-09.md](validation/EDGE_EVIDENCE_2026-11-09.md) |
| §3.9 snapshot 无源码 | [validation/EDGE_EVIDENCE_2026-11-09.md](validation/EDGE_EVIDENCE_2026-11-09.md) §6.1 |
| §3.10 canonical path | [validation/CANONICAL_PATH_2026-11-09.md](validation/CANONICAL_PATH_2026-11-09.md) |
| §3.11 依赖闭包手工 | [validation/OPENTITAN_PILOT_2026-11-09.md](validation/OPENTITAN_PILOT_2026-11-09.md) §P2、[validation/OPENTITAN_I2C_2026-11-09.md](validation/OPENTITAN_I2C_2026-11-09.md) §P4 |
| §3.12 snapshot 无 MIG | [validation/SNAPSHOT_2026-11-07.md](validation/SNAPSHOT_2026-11-07.md) §3 |
| §3.13 语料自撰 | [validation/TASK_DISTRIBUTION_2026-11-09.md](validation/TASK_DISTRIBUTION_2026-11-09.md)、[validation/OPENTITAN_INTAKE_RESULTS_2026-11-09.md](validation/OPENTITAN_INTAKE_RESULTS_2026-11-09.md) |
