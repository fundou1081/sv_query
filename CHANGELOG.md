# 更新日志 (Changelog)

> 完整历史 changelog. README 短版只展示"为什么用 sv_query" + 5 分钟上手.
> 详细 release notes 看这里.

## 2026-07-19/20/21 (V6: 教学型可视化 + 源码溯源)

### V6.0: `visualize teach` 子命令 (commit `8c099f2`)
- 4 个 use case A/B/C/D 全实现:
  - A: 速懂陌生模块 (HTML 概览页 — ports + FSM + pipeline + coverage)
  - B: 查 1 条信号路径 (--focus SIGNAL + --depth N)
  - C: 看控制关系 (--focus + --show-drives)
  - D: 看覆盖缺口 (--show-coverage)

### V6.1: 4 bug 修复 (commit `0c67f97`)
- golden self-eval 发现 4 个问题, 修复 3 个 (coverage counter / width display / show-drives 语义)
- VIZ_UNDERSTANDING_CRITERIA.md 评分卡片: 评分 5/10 → 7/10

### V6.2 + V6.2.1: `--show-source` 源码溯源 (commits `1afbb9e`, `7904e8f`, `b85509c`, `ccb5969`)

**问题**: 用户问"这条信号在哪里定义的?" 传统 viz 不告诉源码在哪.

**V6.2 (1afbb9e)**: 给 `teach` 加 `--show-source`
  - 每个节点 label 加上 `<file>:<line>` 后缀
  - DOT 输出带 `tooltip=` + `URL=file.sv#line` 属性 (浏览器可点击跳转)
  - 限制: 只对 port 节点生效, 内部 SIGNAL 节点 file/line 多为空

**V6.2.1 (7904e8f)**: 在 `UnifiedTracer.build_graph()` 末尾加 `_backfill_source_locations()` pass
  - 遍历 `module.body` 中所有 PortSymbol / NetSymbol / VariableSymbol
  - 通过 `semantic_adapter.get_source_location(sym)` 拿真实 file/line (走 syntax.sourceRange + SourceManager)
  - 在 graph 节点上 fill-in file/line
  - **结果 (ventus Scheduler.v)**:
    - V6.2: 72/283 (25%) 节点有 location
    - V6.2.1: 278/283 (98%) 节点有 location (5 个剩余是 `4'b1` 这样的 CONST literals, 本就没源)
  - **结果 (darkriscv)**: 26/172 (15%) → 142/172 (82%)

**V6.2.1 (b85509c + ccb5969)**: `--show-source` 扩展到 `graph` 和 `dataflow` viz
  - `cli/_viz_common.py`: 新增 `SHOW_SOURCE_OPTION` + `format_source_annotation()` + `render_source_tooltip_and_url()`
  - `signal_graph_viewer.py` + `dataflow_viz.py`: 接受 `show_source` 参数, 在 label 后缀 + tooltip + URL 三个地方都启用

**现在所有 3 个常用 viz 命令 (teach/graph/dataflow) 都能**:
  - DOT label 显示 `name\nkind\nfile:line`
  - DOT tooltip 显示完整 `file:line`
  - DOT URL 让浏览器跳转到 `code -g file:line` 编辑器位置
  - 浏览器 SVG viewer 直接点击节点跳源码

**测试**: 5 backfill tests + 4 teach source tests + 3 graph source tests = 12 个新 tests 全过

## 2026-07-17/18 (Phase B Refactor)

### visualize 命令重构 (Phase B 2026-07-17)

- **Phase 1A** (commit `e759e87`): 提取共享 viz CLI plumbing
  - 新建 `src/cli/_viz_common.py`:
    - `FILE_OPTION`, `FILELIST_OPTION`, `INCLUDE_OPTION`, `STRICT_OPTION` —共享 typer option 常量 (单点修改, 5 子命令同步生效)
    - `build_viz_tracer(file, filelist, include, strict, ...)` —统一 tracer build + 错误处理 (替换 5 份重复 ~12 行 try/except)
    - `get_viz_sources(tracer, file, filelist)` —统一 SVA/Covergroup 提取器取源码逻辑
  - 5 viz 子命令 (`graph`/`dataflow`/`pipeline`/`chain`/`module`) 都改为共享 imports.

- **Phase 2** (commit `9b89240`): 4 个 DOT helper 移到 analyzer
  - 从 `cli/commands/visualize.py` 移到 `src/trace/core/graph/analyzer/_dot_common.py`:
    - `escape_dot_label(s)` — DOT label 特殊字符转义
    - `format_node_label_chain(node_id, top)` — chain 模式多行 label
    - `sanitize_dot_id_inner(s)` — chain 模式 sanitizer
    - `render_with_engine(dot_text, output_path, engine='dot', fmt='png')` — graphviz engine 调用封装

- **代码减少**: `visualize.py` 1750 → 1682 LOC (**-68 LOC, -3.9%**).
  - 5 viz 子命令间重复 boilerplate 从 ~85 行降到 ~0 行.
- **测试**: 80/80 active viz tests 通过. 2 个 pre-existing golden diff 失败与本次 refactor 无关.

### Pipeline visualization 加强 (V4 2026-07-17)

- **Commit `b793a62`**: 每个 fold group 现在是 `subgraph cluster_stage_X_Y` (蓝色虚线 + 浅蓝填充)
  - 修复 user feedback: "看起来还是不够清楚"
  - `openofdm_tx`: 10 cluster 替代原本散落的 28 个 REG 节点
- **跨 stage DRIVER 边**: 一条粗蓝色 `#226699` 箭头连接相邻 cluster, 标签 `flow_S0_to_S1` 等
- **state_reg → stage 关系边**: 橙色虚线带 `affects SN` 标签显示 state machine 影响哪个 stage
- **检测的能力**: openofdm 2 个 state regs → affects S5/S6/S9; scheduler 1 个 → affects S2

### Pipeline defaults 调整 (`a6a50dc`)

- `max_regs_per_fold`: 1 → **3** (每个 fold 现在显示 3 个 REG 节点)
- `target_folds`: 5 → **10** (fold_every 从 18 变为 10, 更细粒度折叠)
- `max_control_nodes` 默认: 8 → **12** (更多 AXI 控制信号可见)
- 新增 `cluster_state_regs`: 橙色 `#cc8844` 节点簇, 显示 state machine registers (FSM context 首个可见)

### CONDITION edges 可视化 (`a22c641`)

- 修复 user feedback: 条件信号 (if/case/ternary 的条件) 之前用 dim 虚线, 看不清
- 改为橙色 (`#ff9900`) 节点 + 橙色虚边带 `COND` label
- 实测 4 个开源项目: ventus 13 条 COND 边, openofdm 2 条, opentitan 2 条, darkriscv 2 条

## 2026-07-02

### 安装流程修复

- 修复 `pip install -e .` 报 `tool.setuptools must not contain {'package_dir'} properties` 错误
- 用 `[tool.setuptools.packages.find]` 替代手写 `packages + package_dir`
- 加 `src/__init__.py` + `src/cli/_entry.py` 让 `sv_query` console script 工作
- 修复 `import trace` 跟 Python stdlib `trace` 冲突 (用 sys.path.insert 绕开)
- README 安装步骤 3 段式 (最简/完整/graphviz)

## 2026-06

### arch 命令 (2026-06-25)

- `arch` 一键生成项目架构图: 模块层级 + 跨模块端口连线
- 5 种输出格式: `summary`/`dot`/`mermaid`/`html`/`svg`
- v2 features: `--cluster-by-type`, `--max-nodes`, `--with-ports`
- 5 个开源项目实测: CoralNPU 28 inst / CVA6 31 ports / Vortex / SERV / darkriscv

### Coverage gap 检测 (2026-06-23)

- `coverage gap` 自动检测 covergroup ↔ constraint 一致性缺口
- 支持 `--class` 过滤、`--json` 输出、`--fail-on-gap` CI 集成
- 修 CovergroupAnalyzer cross.items NAME vs SIGNAL 错位 bug

### 协议检测 (Phase A)

- `protocol detect` 自动识别 AXI4 / TL-UL / AHB / APB / Wishbone / Stream
- 4 项置信度融合 (name + structural + pattern + handshake)
- `--protocol TL-UL` 单协议模式避免多协议竞争误识别

### Dataflow / Pipeline 可视化

- `visualize dataflow` 自动分类 clock/reset/control/data
- `visualize pipeline` 自动检测 pipeline registers, 按 stage 分组
- 7 stages for uart 子项目

### fix 修复子系统

- `fix timescale` 自动补 `` `timescale ``
- `fix report` 按错误类别分组
- `fix imports` 找 UndeclaredIdentifier 来源
- `fix widths` 用 pyslang.clog2 解析 typedef 真实位宽

### SV Preprocessor

- 跨文件 `\`MACRO` 展开, 解决 NaplesPU 12 个 TooFewArguments
- NaplesPU 完整跑通 (125 文件, strict pass with stubs)
- 配套 [docs/NAPLESPU_HOWTO.md](docs/NAPLESPU_HOWTO.md)

### OpenTitan TL-UL 适配

- TileLink Uncached Lightweight 协议检测
- TOP_PKG stub + filelist 排序方案
- 配套 [docs/OPENTITAN_HOWTO.md](docs/OPENTITAN_HOWTO.md)

### 多文件 filelist 支持

- Verilator 风格: `+incdir+`, `-F`, `${VAR}` 完整支持
- CVA6 工业级 RISC-V CPU 解析 (macro_decoder 等模块)
- CLI 新选项: `--include`, `--filelist` 处理大型项目

### 4 维能力闭环 (L1-L4, 2026-06-13 ~ 2026-06-15)

7 PR 阶段 (Commits `0ddd63d` ~ `bba4491`):

- **L1** (PR1): `visualize module` 抽取 target module 的 sub-instance hierarchy
- **L2** (PR2): 跨模块 trace, wrapper port passthrough + port_to_internal 映射
- **L3** (PR3): `SignalTracer` 复用 `ModuleInstanceGraph` (MIG) fallback
- **L4** (PR4): `visualize module` 加 cluster + instance-to-instance 边
- **端到端 benchmark** (PR5): `tools/benchmark/run_benchmark.py`
- **CI 集成** (PR6): `.github/workflows/benchmark.yml` + regression check
- **picorv32 第二个项目** (PR7): `--files` 单文件模式 + baselines

### Coverage Generator 工具 (Phase 1+2)

- `tools/coverage_gen_demo.py` 自动从 RTL 信号生成 SystemVerilog covergroup
- 6/7 Phase 2 任务完成: CLI 集成, 跨 module signal, typed package, nested packed struct
- **Coverage Gen CI** (Phase 2 #7): `.github/workflows/coverage-gen.yml` 4 job 专门验证
- **SV 编译验证** (Phase 3 #C): `tools/coverage_gen_sv_compile.py` 用 pyslang 实际编译, 修 2 个真 bug (bins 关键字 + wrapper clk/rst 命名)

### pyslang 10 + 11 双版本完整支持 (2026-06-04)

- 1501/1501 全过在 pyslang 10.0.0 和 11.0.0
- v11 拆了 submodule + 改了 4 个语义点
- 详见 [docs/PYSLANG_COMPAT.md](docs/PYSLANG_COMPAT.md)

### Evidence 召回扩展 (2026-06-04)

- cdc / verify / risk / dataflow / controlflow 都支持 `--evidence` flag
- JSON 返回完整 evidence 字段含 credibility_score
- 详见 [docs/EVIDENCE_FEATURE.md](docs/EVIDENCE_FEATURE.md)

## 早期版本

完整历史看 [docs/DOC_IMPL_GAP.md#更新日志](docs/DOC_IMPL_GAP.md#更新日志)
