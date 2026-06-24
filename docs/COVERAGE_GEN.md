# sv_query Coverage Generator

> [Phase 2 2026-06-24] Given a target signal, auto-generate a SystemVerilog covergroup.
> Integrates sv_query metadata (risk score, fan_in/fan_out) with pyslang elaboration
> (real widths including `$clog2` derived + package typedef).

---

## 1. Motivation

**Problem**: 验证工程师想覆盖 RTL 一个信号时, 需要手工写 covergroup 包含:
1. **Sample 条件** — `covergroup cg @(posedge clk iff !rst_n)` 何时采样
2. **Bin 定义** — data 信号范围分 / control 信号离散分
3. **Cross 关系** — 主信号和相关 control 信号的交叉覆盖

这需要:
- 读 RTL 知道信号宽度 (含 parameter / `$clog2` / typedef)
- 读 RTL 知道时钟/复位 + 信号稳定条件 (VLD/ready 配对)
- 知道 related control 信号 (mode/valid/enable) 才能写 cross

**Solution**: `svq coverage generate` 用 sv_query + pyslang 自动给.

---

## 2. CLI Usage

### 2.1 基本用法

```bash
# 单文件 + 单信号
svq coverage generate -f sim/openTitan_validation.sv -s state_q \
    -r mode_i -r valid_i

# 多文件 + filelist (工业 RISC-V / SoC)
svq coverage generate -f top.sv --filelist=project.f \
    -s data_o -r enable_i -I /path/inc1,/path/inc2

# 写到 .sv 文件 (不只 stdout)
svq coverage generate -f top.sv -s data_o -o cg_data_o.sv

# Golden image diff (去掉元信息)
svq coverage generate -f top.sv -s data_o --no-header
```

### 2.2 Flags

| Flag | 说明 | Default |
|------|------|---------|
| `-f FILE` / `--file` | SystemVerilog 源文件 (单文件) | None |
| `--filelist FILE` | 多文件 filelist (.f/.fl) | None |
| `-s SIGNAL` / `--signal` | **Required**: 目标信号名 (e.g. `top.data_o`) | - |
| `-r SIG` / `--related` | Cross 相关信号 (可多次) | None |
| `-I DIRS` / `--include` | Include 路径 (逗号分隔) | None |
| `--module NAME` | 多 module 文件里指定 module | None |
| `--no-strict` / `--strict` | sv_query 错误处理 (推荐 `--no-strict`) | `--no-strict` |
| `-o FILE` / `--output` | 写到 .sv 文件 (默认 stdout) | None |
| `--no-header` | 去掉元信息 header (golden image diff 用) | False |

---

## 3. 生成的 covergroup 结构

```systemverilog
// ======================================================================
// Auto-generated covergroup for: <SIGNAL>
//   class:     <DATA | CONTROL>
//   width:     <N bits  (RTL: [hi:lo])>
//   risk:      <SCORE> (<LEVEL>)
//   generator: tools/coverage_gen_demo.py (Phase 1 POC)
// ======================================================================
covergroup cg_<SIGNAL> @(<SAMPLE_EVENT>);
  option.per_instance = 1;
  option.comment = "<SIGNAL> (<CLASS>, <N>-bit, risk=<SCORE>)";

  // ---- Primary coverpoint ----
  cp_<SIGNAL>: coverpoint <SIGNAL> {
    // <DATA bins: range partition> | <CONTROL bins: 1-of-N / enum>
  }

  // ---- Cross coverpoints ----
  cp_<REL>_for_<SIGNAL>: coverpoint <REL> { ... }
  cx_<SIGNAL>_x_<REL>: cross cp_<SIGNAL>, cp_<REL>_for_<SIGNAL>;

  // ---- Sample event: <SAMPLE_EVENT> ----
  //   <CAVEAT describing when signal is stable>
endgroup: cg_<SIGNAL>
```

### 3.1 DATA vs CONTROL 策略

| 维度 | Data 信号 | Control 信号 |
|------|----------|--------------|
| 主 bin | 范围分 (zero/low/mid/high/max) | 离散 (1-of-N) 或 enum 名 |
| 注释 | "sample whenever valid" | "consider gating on enable/valid" |
| Cross 候选 | 找所有 control (mode/valid) | 找其他 control (不 cross data) |
| Bins 模板 | 8/16/32-bit 各自模板 | width ≤ 4-bit, enum, 1-bit |

### 3.2 Sample 条件保守推断 (5 种启发式)

| 启发式 | 触发条件 | 推断结果 |
|--------|----------|----------|
| VLD-style | 名字含 `valid/vld/req/ack/ready/grant/done` | 找 related 里的 `valid/ready/enable` 配对 → `iff <配对>` |
| Input port | 顶层 input port | `@(posedge clk)` (无 `iff`) + 注释 "stable every cycle" |
| Data reg | 内部 `_q/_d` reg + DATA | 找 related 里的 `valid/enable` → `iff <配对>` |
| Control/FSM | control 信号 (含 enum typedef) | `@(posedge clk iff !rst)` + 注释 "always stable" |
| 推断不到 | (其他情况) | `@(posedge clk)` (无 `iff`) + 警告 "may be too eager" |

**关键原则**: **不瞎猜 `iff`** — 推断失败时空着, 让验证工程师手填, 注释解释.

---

## 4. Width 解析 (pyslang API)

**Why pyslang?** sv_query 的 `risk analyze --json` 把所有 width 简化成 1-bit. 但 pyslang API
(`inst.body.find(name).type`) 给 **elaborate 后的真实 type 字符串**, 包括:

| Type 例子 | 解析 |
|-----------|------|
| `logic` | 1-bit |
| `logic[15:0]` | 16-bit `[15:0]` |
| `logic[4:0]` (来自 `localparam X = $clog2(32)`) | **5-bit** |
| `logic[3:0][31:0]` (2D 嵌套) | 4-bit (外层) |
| `logic[7:0]$[0:3]` (unpacked array) | 8-bit (packed dim) |
| `types_pkg::word_t` (typedef) | lookup → `logic[31:0]` → 32-bit |
| `enum{...}types_pkg::state_t` | max value → `ceil(log2(N))` |
| `struct packed{...}` (typedef) | sum field bits |
| `union packed{...}` (typedef) | max field bits |
| `module_name.type_name` (module-scope typedef) | lookup → underlying |

**测试覆盖**: `sim/tests/unit/test_pyslang_type_extraction.py` 68 个 cases (含 3 工业项目).

---

## 5. 能力矩阵 (Phase 1 完整版)

### ✅ 支持

| 维度 | 详情 |
|------|------|
| 源文件 | 单文件 / 多文件 filelist / `+incdir+` 路径 |
| Include | 链式 `\`include` (4 层) — pyslang 自身处理 |
| 工业项目 | PicoRV32, OpenTitan prim_max_tree, NaplesPU logger |
| 多 module | `--module=NAME` 限定 |
| RTL 错误 | `--no-strict` graceful degradation |
| 1-bit scalar | `logic / bit / reg` |
| 1D vector | literal / parameter / arithmetic width |
| 派生参数 | `$clog2(N)` |
| 2D packed | `logic[N:M][K:L]` (取外层) |
| Unpacked array | `logic[N:M]$[0:X]` (取 packed dim) |
| Package typedef | logic / enum / packed struct / packed union |
| Module-scope typedef | `module_name.type_name` |
| Nested typedef | typedef → typedef 链 |
| Sample 条件 | 5 种启发式 + 保守 fallback |
| Bin | DATA 范围分 / CONTROL 离散 / enum 名 |
| Cross | 主信号 × related control |

### ❌ 已知限制 (Phase 2 候选)

| 限制 | 状态 |
|------|------|
| Typed package `pkg::type_t` (ascon 那种) | ✅ **支持** (Phase 2 #5) — 包括 3 层 typedef 链 + `import pkg::*` 模式 |
| 144-file NaplesPU 完整跑 | ❌ 需更完整 filelist + 工业 include |
| 跨 module signal (子模块 instance) | ✅ **支持** (Phase 2 #4) — `u_middle.u_sub.data_o` 形式 |
| Nested packed struct 字段 deep names | ✅ **支持** (Phase 2 #6) — 每字段 `bins name = signal[hi:lo]` |
| CI 集成 | ✅ **支持** (Phase 2 #7) — `.github/workflows/coverage-gen.yml` |

---

## 6. 内部实现 (供开发者)

```
src/cli/commands/coverage.py::generate  (CLI 入口)
  → tools/coverage_gen_demo.py::generate_covergroup  (核心逻辑)
    ├─ read_all_sources(file, filelist) → (sources, paths, include_dirs)
    ├─ query_risk_json(...) → signal metadata
    ├─ parse_width_from_pyslang(...) → (width, hi, lo)  [真实 width 解析]
    │  └─ _parse_logic_type_str (type 字符串 → width)
    │  └─ _resolve_typedef (typedef → underlying)
    ├─ parse_clock_reset(paths) → (clk, rst)
    ├─ parse_enums(paths) → enum 字典
    ├─ infer_sample_condition (5 种启发式)
    ├─ gen_bins_data / gen_bins_control (bin 生成)
    └─ 组装 covergroup 文本
```

### 6.1 关键 API 路径

```python
from cli._common import _build_tracer  # 复用 sv_query tracer
tracer = _build_tracer(file, filelist, include_dirs, strict=False)
tracer.build_graph()
root = tracer._compiler.get_root()

for inst in root.topInstances:           # top-level instances
    body = inst.body
    for p in body.portList:               # ports
        type_str = str(p.type)              # 'logic[31:0]' or 'types_pkg::word_t'
    sym = body.find('signal_name')          # internal signals
    type_str = str(sym.type)
```

---

## 7. 测试覆盖

```
sim/tests/unit/test_pyslang_type_extraction.py    68 cases (type 解析)
sim/tests/cli/test_coverage_gen_demo.py            9 cases (CLI)
sim/tests/cli/test_coverage_gen_demo_golden.py     5 cases (3 工业 project)
sim/tests/golden/coverage_gen_demo/*.golden        3 baselines
─────────────────────────────────────────────────
total                                            82 new cases
```

**跑测试**:
```bash
python -m pytest sim/tests/unit/test_pyslang_type_extraction.py \
                 sim/tests/cli/test_coverage_gen_demo.py \
                 sim/tests/cli/test_coverage_gen_demo_golden.py -v
```

---

## 8. 真实例子

### 8.1 工业项目 (NaplesPU logger, 4 层链式 include)

```bash
svq coverage generate \
    -f /Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv \
    --filelist=/tmp/naples_real.f \
    -s events_counter \
    -I /Users/fundou/my_dv_proj/NaplesPU/NaplesPU/src/include
```

输出 (省略 warning):
```systemverilog
covergroup cg_events_counter @(posedge clk iff !rst_n);
  option.per_instance = 1;
  option.comment = "events_counter (DATA, 32-bit, risk=68.3)";

  cp_events_counter: coverpoint events_counter {
    bins zero  = {32'h0};
    bins byte  = {[32'h1:32'hFF]};
    bins word  = {[32'h100:32'hFFFF]};
    bins dword = {[32'h10000:32'hFFFFFF]};
    bins max   = {32'hFFFF_FFFF};
  }
  // ---- Sample event: @(posedge clk iff !rst_n) ----
  //   Data reg — no valid/enable gating found; sample every cycle (may be too eager)
endgroup: cg_events_counter
```

### 8.2 OpenTitan $clog2 派生参数

```bash
svq coverage generate \
    -f /Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_max_tree.sv \
    -s max_idx_o
```

```systemverilog
covergroup cg_max_idx_o @(posedge clk_i iff !rst_ni);
  cp_max_idx_o: coverpoint max_idx_o {
    bins zero  = {0};
    bins low   = {[1:15]};
    bins high  = {[16:30]};
    bins max   = {31};
  }
  // width=5 来自 $clog2(32) 派生 — 之前 regex 拿不到
endgroup: cg_max_idx_o
```

---

## 9. 关键设计决策 (历史)

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-06-23 | 不瞎猜 sample `iff` | VLD 信号无法确认 stable 条件时空着 + 警告 |
| 2026-06-23 | 复用 sv_query `_read_filelist` | 不重新发明轮子, 跟其他 CLI 行为一致 |
| 2026-06-24 | 修 sv_query `risk.py` 加 `--include` flag | 修 sv_query 自身 gap (其他 CLI 已有这 flag) |
| 2026-06-24 | 走 pyslang API 拿 width | regex 拿不到 `$clog2` / typedef, pyslang 100% 准确 |
| 2026-06-24 | 加 typedef lookup | package typedef → underlying type, 解 90% 工业 case |
| 2026-06-24 | 默认 `--no-strict` | 工业多文件项目常见 UnknownModule, 友好降级 |
| 2026-06-24 | 加 hierarchical signal lookup | 跨 module: `u_middle.u_sub.data_o` 形式 (Phase 2 #4) |
| 2026-06-24 | **发现 typed package 已支持** | `pkg::type_t` + 3 层 typedef 链 + `import pkg::*` 都能解析 (Phase 2 #5) — 之前说"工具边界"是误判 |
| 2026-06-24 | 加 packed struct field bins | 每字段生成 `bins name = signal[hi:lo]`, union 跳过 (避免重叠) (Phase 2 #6) |

---

## 10. 已知问题 / 未来工作

- typed package `pkg::type_t` (e.g. OpenTitan ascon) — 需要扩展 `_resolve_typedef` 跨 module typedef lookup
- 跨 module signal — 现在只搜 `topInstance.body`, 需要支持 `inst.body.find('sub_instance.signal')`
- nested packed struct deep fields — 现在只 sum total width, 需要展开 coverpoint 字段名
- CI 集成 — `sim/tests/cli/test_coverage_gen_demo_golden.py` 已经验证了 golden pattern, 可接入 GitHub Actions

## 11. CI 集成 (Phase 2 #7)

### Workflow: `.github/workflows/coverage-gen.yml`

**设计**: 跟现有 `benchmark.yml` 风格一致, 不动 `tests.yml` (已跑全 `sim/tests/`).

**4 个 Job**:

| Job | 作用 | 依赖 |
|-----|------|------|
| `test` | 单元 + CLI 测试 (Phase 2 #1-6), 覆盖度门禁 | — |
| `golden-regression` | 3 工业项目 golden baseline 回归检查 | test |
| `lint` | ruff lint (warning 级别, 跟 tests.yml 一致) | — |
| `ci-summary` | 汇总状态 (block PR if test/golden fail) | test, golden-regression |

### 触发条件
- push to `main` / `develop`
- pull_request to `main` / `develop`
- manual `workflow_dispatch`

### Fail-under Gate
- `tools/coverage_gen_demo.py` 覆盖率 ≥ 25% (起步阈值, 后续提升)
- 当前 baseline: 26.38% (114/114 tests pass)

### 工业项目 Golden
- picorv32 (`/tmp/picorv32/picorv32.v`) — `mem_addr` golden
- OpenTitan (`/tmp/opentitan/hw/ip/prim/rtl/prim_max_tree.sv`) — `max_idx_o` golden
- NaplesPU (`/tmp/NaplesPU/NaplesPU/src/sc/logger/npu_core_logger.sv`) — `events_counter` golden

### Lint
- 预先存在 23 个 ruff warnings (N817 CamelCase + F541 f-string 无 placeholder)
- **不 block CI** (跟 `tests.yml` 一致), 只 report 出来

### Artifacts (上传保留 30 天)
- `coverage-gen-coverage-3.12`: coverage.xml (覆盖度报告)
- `golden-regression-failure`: golden diff (失败时)

### 本地复现 CI
```bash
# 1. 跑 unit + CLI tests
python -m pytest \
    sim/tests/unit/test_pyslang_type_extraction.py \
    sim/tests/cli/test_coverage_generate.py \
    sim/tests/cli/test_coverage_gen_demo.py \
    -v --tb=short

# 2. 跑 golden regression (需要工业项目)
python -m pytest \
    sim/tests/cli/test_coverage_gen_demo_golden.py \
    -v --tb=long

# 3. 覆盖度门禁
python -m pytest \
    sim/tests/unit/test_pyslang_type_extraction.py \
    sim/tests/cli/test_coverage_generate.py \
    sim/tests/cli/test_coverage_gen_demo.py \
    --cov=coverage_gen_demo \
    --cov-report=term-missing \
    --cov-fail-under=25

# 4. Lint (warning 级别)
ruff check tools/coverage_gen_demo.py || echo "(lint issues)"
```
