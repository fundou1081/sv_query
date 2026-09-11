# 方案: adapter 层拆解 (base.py 死层 + SemanticAdapter 分域) — 待方豆讨论

> **创建**: 2026-09-08 GMT+8 (iter_173)
> **状态**: ✅ **已执行完毕 (iter_174~177, Step 0-10 全绿)** — 结果见下方"执行结果"节; 方豆拍板: 移出代替删除。
> **A 路线第三项** (前两项: iter_171 文档清理 / iter_172 缓存目录)

---

## 1. 诊断事实 (全部实测, 非估算)

### 1.1 两套 adapter 并存

| 文件 | 行数 | 运行时状态 | 引用面 |
|---|---|---|---|
| `core/base.py` | **2,341** | ❌ **src/ 从未实例化** (`grep 'PyslangAdapter(' src/` = 0) | 8 处 **仅类型注解** (`adapter: PyslangAdapter`) + 1 处 `ASTWalker` + 4 个回归测试**直接实例化** |
| `core/semantic_adapter.py` | **3,049** | ✅ 唯一运行时 adapter (`SemanticAdapter`) | 12+ 模块, 42 个外部调用的方法 |

- `base.py` 内容: `ASTWalker` (L19) + `PyslangAdapter` (L83, 2067 行) +
  `DriverCollector` / `LoadCollector` / `ConnectionCollector` (L2150/2223/2261, 三个 walker)。
- **既有先例**: 2026-07-15 的 V2 清理已删 `core/pyslang_adapter.py` (158 行死代码),
  并留下守卫测试 `test_no_pyslang_adapter_legacy.py` — 但 `base.py` 这一层被漏掉了,
  且当年的注释称它"primary" (现已不是)。
- 另有 33 个 SemanticAdapter 方法**零外部调用** (其中 `get_drivers` / `get_loads` /
  `get_interfaces` / `get_definition` / `get_parent_module` / `get_top_level_subroutines` /
  `get_modport_info` / `iter_modules` / `visit_module` 等是明显死 API)。

### 1.2 SemanticAdapter 的体量分布

- 单类 77 方法 / 3,049 行;42 个方法被外部调用 (共 ~150 处调用点)。
- **7 个 ≥100 行条目 = 1,239 行 = 40%**:

| 行数 | 位置 | 方法 |
|---|---|---|
| **474** | L2285 | `_extract_signals_from_expr` (表达式信号抽取 — 且被 **13 处外部调用**) |
| 145 | L177 | `get_modules` |
| 143 | L1902 | `get_interface_modport_signals` |
| 132 | L1296 | `get_assignments` |
| 128 | L345 | `get_module_instances_recursive` |
| 112 | L1073 | `get_instance_connection` |
| 105 | L2146 | `_collect_drivers_from_stmt` |

- 内部状态 (搬迁时必须保持生命周期): `_fixed_names` (id-keyed 防 Unicode bug)、
  `_genvar_context` / `_primitive_genvar_context` (id-keyed)、`_spec_members`
  (参数化特化缓存)、`_root` / `_compiler` / `_target_module`。

### 1.3 消费方 (方法数 / 调用次数)

`driver_extractor` 13/21 · `connection_extractor` 10/19 · `function_extractor` 10/18 ·
`load_extractor` 8/15 · `clock_domain_extractor` 8/11 · `bit_select_handler` 9/10 ·
`class_graph_builder` 3/9 · `unified_tracer` 5/6 · `graph_builder` 4/6 ·
`wire_init_extractor` 5/6 · `applications/bus/sv_extractor` 4/6 · `covergroup_analyzer` 2/5 ·
CLI (`arch` / `visualize` / `trace`)。

> 结论: **"拆 semantic_adapter" 不是一件事, 是两件** — (P-A) 先清 2,341 行死层,
> (P-B) 再分域 3,049 行活代码。二者必须分开决策、分开验收。

---

## 2. 方案对比

### P-A: `base.py` legacy 层怎么处置

| 方案 | 内容 | 利 | 弊 |
|---|---|---|---|
| **A1 (推荐)** | 删除 `base.py` 全部 (含 3 个 Collector), 8 处注解改 `SemanticAdapter`; 4 个 legacy 测试**先做等价覆盖核对**再迁移/删除 | 一次性 -2,341 行源 + 可能 -1,546 行测试; 消灭双 adapter 认知负担; 与 V2 清理同向 | 需先验证 4 个 legacy 测试覆盖的功能在 semantic 路径有等价测试 (否则先补测) |
| A2 | 只删 `PyslangAdapter`, 保留 `ASTWalker`/Collector | 改动更小 | 半死层继续存在, 认知成本照旧 |
| A3 | 保留 + 标 `@deprecated` + 文档 | 零风险 | 债继续涨, 下次还得做 |

**4 个 legacy 测试** (共 1,546 行, 全部直接 `PyslangAdapter(FP(...))`):

| 测试 | 行数 | semantic 路径可能等价物 |
|---|---|---|
| `test_class_method.py` | 311 | `test_class_oop_truth.py` (29 测试) / `test_class_parameterized.py` (11) |
| `test_constraint_deep_parsing.py` | 765 | `test_class_oop_truth.py::TestConstraintTracing` + covergroup/constraint 系列 |
| `test_constraint_derivative.py` | 283 | 同上 |
| `test_interface.py` | 187 | iter_129 interface 桥测试 + integration interface 用例 |

> 等价性必须**逐条核对** (断言级), 不能按文件名猜 — 这是 Step 1 的交付物。

### P-B: `SemanticAdapter` 怎么分域

| 方案 | 内容 | 利 | 弊 |
|---|---|---|---|
| **B1 (推荐起步)** | Mixin 组合: `SemanticAdapter` 保留 facade (`__init__` + 状态 + 属性), 方法体按 6 域搬到 `core/semantic/` 包内 mixin 类; **77 个方法名/签名全部不变** | 调用方**零改动**; id-keyed 状态天然同实例; 每步可单独 commit/回滚 | 边界靠纪律 (mixin 仍共享 self); 单文件变小但仍多文件协作 |
| B2 | 独立类 + 显式依赖 (`AdapterContext` 注入) | 边界最清晰, 依赖显式 | 42 个外部调用面 + id-keyed 缓存搬迁风险中高; 工作量大 |
| B3 | 纯机械搬运 (模块函数 + facade 转发) | 改动最小 | `self` 透传噪音大; 巨函数问题不解 |

**两案不冲突**: B1 做完后 API 面已被"冻结测试"锁住, 若将来要更强边界, 可无痛演进 B2。

### P-C (独立小项): 474 行 `_extract_signals_from_expr`

无第二方案 — 必须拆 (AGENTS §5 函数简洁: 阈值 ~50 行)。做法: 拆成
`_expr_walk` 框架 + 4~6 个纯函数 (各自可单测), **行为不变**; 由 13 个外部调用点的
测试 + 新增边界单测共同保护。

---

## 3. 分步路线 (每步 = 1 commit + 全绿 + 可回滚)

| Step | 内容 | 验证 gate | 预估 |
|---|---|---|---|
| **0** | **先建 API 面冻结测试** `test_semantic_adapter_api_surface.py`: 断言 77 方法名集合 + `inspect.signature` + facade 关键属性 | 自身 + 全量 (基线锁定) | 0.5h |
| **1** | P-A 前置: 4 个 legacy 测试 ↔ semantic 等价覆盖矩阵 (逐断言核对), 输出缺口清单 | 纯分析 + 跑对照测试 | 1-2h |
| **2** | (决策 D1) 删 `base.py` + 注解改 `SemanticAdapter` + 测试迁移/删除 + 守卫测试扩展 (防重现) | 全量 + truth 19 + opensource 子集 | 2-3h |
| **3** | P-C: 拆 `_extract_signals_from_expr` (474 → 框架 + 纯函数) | 表达式/驱动/truth golden | 2h |
| **4** | mixin 域 1: source/location/`clean_name`/Unicode 修复 | unit naming/source + cli SVG golden | 1h |
| **5** | mixin 域 2: classes/constraints/特化 (含 `get_class_members`/`_scan_class_specializations`) | class truth + 参数化 + covergroup 全族 | 1h |
| **6** | mixin 域 3: ports/interfaces/modport | interface/port 用例 + opensource axi/serv | 1h |
| **7** | mixin 域 4: connections (`get_instance_connection`/`_conn_expr_to_signal`/`_eval_select_index`) | 连接/fanin 用例 + truth assign_chain | 1h |
| **8** | mixin 域 5: exprs/assignments/drivers | 表达式/驱动 + golden_dataflow | 1h |
| **9** | mixin 域 6: module/instance 导航 + generate 下钻 | arch/case27/generate truth + cli/test_arch | 1h |
| **10** | 死 API 清理 (33 零调用中确认可删者) + 文档 (ARCHITECTURE/INDEX/overview) | 全量 + check_docs | 1h |

**命名约定**: 新包 `src/trace/core/semantic/` (facade `adapter.py` + `mixins_*.py`),
对外 **import 路径不变** (`from trace.core.semantic_adapter import SemanticAdapter` 保留为再导出)。

---

## 4. 回归测试计划 (哪个改动用哪些测试保证)

### 4.1 基线 (冻结, iter_172 实测)

| 套件 | 基线 | 命令 |
|---|---|---|
| unit | 1,112 passed | `pytest sim/tests/unit -q -m "not opensource"` |
| unit + regression | **2,059 passed** | `pytest sim/tests/unit sim/tests/regression -q -m "not opensource"` |
| cli + integration | **739 passed / 0 failed** | `pytest sim/tests/cli sim/tests/integration -q -m "not opensource"` |
| truth 金标准 | 19 文件 (case27/class/covergroup/位选/generate/cordic…) | `pytest sim/tests/test_*truth*.py -q` |
| opensource (真实项目) | **缓存修复后已可跑** (待实测冻结数字) | `pytest sim/tests -q -m opensource` |

**规则**: 重构期间测试计数**只增不减**; 任何 golden 需重新生成 = 行为变化 →
**停下报告**, 不自行重生成 (AGENTS §2 反面)。

### 4.2 区域 → 测试映射 (每个 mixin 域的 gate)

| 搬迁域 | 主 gate (快) | 深 gate |
|---|---|---|
| source/location/clean_name | `unit/test_*naming*`、`unit/test_source_*` | cli golden SVG 布局用例 |
| classes/constraints/特化 | `test_class_oop_truth.py`、`test_class_parameterized.py`、`regression/test_covergroup*.py` | `regression/test_constraint*.py`、covergroup 查询 API 用例 |
| ports/interfaces/modport | `regression/test_interface.py`、port/alias truth | opensource: serv / verilog-axi |
| connections | `unit/test_trace_include_flags.py`、`regression/test_connection*` | truth `assign_chain` / `bit_select` |
| exprs/assignments/drivers | `unit/test_expression*`、`unit/test_driver*` | truth `assign/concat/case/ternary` + golden_dataflow (32+ 图 byte-identical) |
| module/instance 导航 + generate | `cli/test_arch.py`、`unit/test_module_*` | truth `case27_1to1` / `cla_generate` / `cordic_pipeline` |
| (Step 2) 删 base.py | 上述全部 | 全量 + truth 19 + opensource 子集 |

### 4.3 每步执行顺序 (固定)

1. 目标域快 gate (秒~十秒级)
2. `unit + regression` (≈2 min)
3. `cli + integration` (≈4 min)
4. API 面冻结测试 (Step 0 产物) — 必须**完全一致**
5. `python3 tools/check_docs.py` (文档卫生三项 0)
6. 计数比对: 2059 / 739 / truth 全绿 — 不达基线即回滚本步

---

## 5. 风险与缓解

| 风险 | 缓解 |
|---|---|
| id()-keyed 状态 (`_fixed_names` / `_genvar_context` / `_spec_members`) 生命周期变化 | B1 mixin 同实例共享 → 天然安全; 禁止"改为模块级缓存"这类顺手优化 |
| 42 个外部调用点 (150 处) 被意外改名/改签名 | Step 0 API 冻结测试 + **零改名**策略 (每步只搬函数体) |
| 474 行巨函数拆出行为差异 | 先写输入输出等价用例再拆; 依赖 13 个调用点的既有测试 |
| 4 个 legacy 测试含**唯一**覆盖 | Step 1 逐断言矩阵; 无等价的先补 semantic 测试再删 |
| `_extract_signals_from_expr` 被外部直接调用 (13 处, 含私有名) | 保持名字与签名; 长期可加公开别名 (本次不动 API) |

---

## 6. 待方豆拍板 (决策点)

| # | 决策 | 我的建议 |
|---|---|---|
| **D1** | P-A `base.py` (2,341 行死层) 是否本次删除? | **删** (A1) — 需先做 Step 1 等价矩阵; 若你不接受动 4 个 legacy 测试, 退 A3 并单列 backlog |
| **D2** | P-B 拆分用 B1 (mixin, 零调用方改动) 还是 B2 (显式依赖) | **B1 起步** (可演进 B2) |
| **D3** | 474 行巨函数本次是否一并拆? | **一并拆** (Step 3, 独立 commit) |
| **D4** | opensource/真实项目套件纳入哪些 gate? | Step 2 + 收尾各跑一次; 中途步只跑快 gate (控时) |

**工作量**: Step 0-10 合计约 **2 天量级** (含每步验证); 若只做 D1+D3+B1 主干 (Step 0/1/2/3 + 4~9) 约 1.5 天。

---

## ✅ 执行结果 (iter_174~177, 全部完成)

| Step | 结果 | 提交 |
|---|---|---|
| 0 | API 面冻结测试 (65 方法 + 签名 + property) | cdba3ca |
| 1 | legacy 等价矩阵 (4 文件逐条核对 → 零覆盖损失) | cdba3ca |
| 2 | `base.py` 2,341 行 → `legacy/base_pyslang_adapter.py` (移出非删除) | cdba3ca |
| 3 | 474 行巨函数 → 70 行分派器 + 16 处理器 (+修 latent UnboundLocalError) | 70ed162 |
| 4-9 | 六域 mixin: facade 3,036 → **123 行**; 62 方法进 `core/semantic/` | 3ccbfc2 |
| 10 | 移出 5 个零调用方法 → `legacy/dead_semantic_adapter_methods.py`; 文档漂移修正 | (本迭代) |

**最终基线 (与拆分前一致, 无行为变化)**: unit+regression+truth **2,243 passed** /
cli+integration **739 passed / 0 failed** / API 面冻结一致 (60 方法, 5 个零调用方法
已按流程收缩并记录) / `check_docs.py` ✅。

