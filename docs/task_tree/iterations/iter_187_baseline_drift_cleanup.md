# Iteration 187: baseline 漂移清算 + 输入构建统一 + 漂移守卫

**Metadata**:
- **Iteration #**: 187
- **Task Tree Level**: L2 (benchmark 设施正确性)
- **Parent Task**: iter_185/186 续 (方豆 "继续" — 回审为掩盖真 bug 而加的补偿措施)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 3 个 baseline 重生成 (全确定性) + 2 个新工具 + 漂移守卫测试

## 🎯 本次目标

iter_185 修掉了真因 (`SourceManager` 生命周期), iter_186 扫了同族代码隐患。
本次做**补偿措施回审**: 过去为"结果不稳定"而加的放宽断言 / 重试 / 手工输入 /
内存技巧, 在真因修复后还有没有必要? 逐条实测, 该收的收, 该改注释的改注释。

## 📊 当前状态 / 预期结果

预期: 主要是"更新注释 + 收紧 pr5 断言"。
实际: 挖出**结构性缺陷** — 三个 baseline 全部与当前行为不符, 且**不可复现**
(输入是 /tmp 手工文件), 于是 "regression check" 这个门在给用户报假结论。

## 🔬 实际结果

### 1. baseline 全线漂移 (证据)

`regen_baselines.py --check` 实测:

| baseline | 采集时间 | baseline 值 | 当前实测 | 判定 |
|---|---|---|---|---|
| `picorv32.json` | 2026-08-29 | nodes 708 / edges 1,280 / IM 2 | **438 / 1,096 / 0** | ❌ 漂移 |
| `verilog_axi.json` | 2026-08-29 | nodes 8,221 / edges 9,457 / IM 51 | **715 / 1,034 / 6** | ❌ 漂移 |
| `pulp_axi_xbar.json` | 2026-06-15 | nodes 4,071 / IM 59 | target `axi_xbar_dp_ram` | ❌ **不可复现** (模块已不在语料) |
| `pr5_wrap.json` | — | — | 4,946 / 5,808 / 516 | 新增 |

**根因**: 三个 baseline 都采集于 **iter_145 (`top_modules=[target]`) 之前** ——
那时 pyslang 会 pre-elaborate filelist 里所有 free-floating 模块, 节点数/IM 被
虚高; 加上长期未重测。影响: `check_regression.py` 对用户报**假 regression**
(节点"跌 73%"), 而 `test_baseline_l2_values_reasonable` 只检查**文件自己**
(`600 <= nodes <= 800`), 于是过时 baseline 一路绿灯 — 典型的"断言看错了对象"。

### 2. 输入构建散落 (可复现性缺陷)

- 测试自带 `_ensure_filelist()`, 手写命令用 `/tmp/pulp_axi_xbar_pr2.f`;
- baseline 的 `metadata.project_input` 指向 `/tmp` 文件 → 重启即失, 无法重放;
- 后果: baseline 无法复现, 也没人发现它已过时。

修复: 新增 `tools/benchmark/inputs.py` = **唯一输入构建点**
(`ensure_axi_filelist` / `ensure_pr5_wrap_filelist` / `ensure_verilog_axi_filelist`
/ `picorv32_file`), 从 `~/my_dv_proj/openrtl/` 现场生成; 源缺失返回 None
(调用方 skip, 不伪造)。`test_benchmark_pr5.py` 改为调用它 (删掉本地重复逻辑)。

### 3. 新增 `tools/benchmark/regen_baselines.py`

- `python3 tools/benchmark/regen_baselines.py` — 重生成全部可复现 baseline
  (默认 `--runs 3` 带 flakiness 阶段);
- `--check` — 只对比不写, **rc=2 表示检出漂移** (可进 CI);
- 重生成结果 (flakiness 阶段 `node_stdev` 全 **0.0**):

| baseline | L1 | nodes | edges | IM |
|---|---|---|---|---|
| `picorv32.json` | 0 | **438** | 1,096 | 0 |
| `verilog_axi.json` | 6 | **715** | 1,034 | 6 |
| `pr5_wrap.json` (新) | 2 | **4,946** | 5,808 | 516 |

### 4. 断言收紧 (不留假下限) + 漂移守卫

| 测试 | 原来 | 现在 |
|---|---|---|
| `test_picorv32_l2_node_count_above_400` | `nodes >= 400` | `nodes == baseline` (**等值**, 改名 `..._matches_baseline`) |
| `test_baseline_l2_values_reasonable` | 只看文件的 `600<=nodes<=800` / `2<=IM<=10` | **活体 == baseline** 三项全比 (`..._matches_current_behavior`) |
| `test_baseline_flakiness_stable` | `ratio >= 0.9` ("内存回收后") | `ratio == 1.0` **且 `node_stdev == 0.0`** |

### 5. 连带修好被 baseline 漂移坑到的测试 (值得记)

重生成 baseline 后, `test_benchmark_regression.py` 立刻 **2 failed**
(`test_node_drop_50_pct_fails` / `test_im_drop_50_pct_fails`) — 因为这些测试
**硬编码了旧 baseline 的数值** ("baseline 708 → 变体 354"、"IM 2 → 1"):

- 新 baseline nodes=438, 变体 354 只跌 19% → 检测器按设计 PASS → 测试假失败;
- 新 baseline IM=0, "IM 跌到 1" 其实是**涨** → 同样测不出。

修法 (不是改断言糊过去): 新增 `_make_scaled_variant()` — 变体值由 baseline
**按比例派生** (只依赖阈值语义, 不依赖当时数值); "IM 下跌" 场景改用
`verilog_axi.json` (IM=6, 因为 picorv32 IM=0 时该场景退化)。12 passed。

## 💡 关键发现 / 关键技术 / 决策

1. **baseline 是"活的契约", 不是历史文件**: 它必须与当前行为一致, 否则
   regression 门会给假结论。守卫方式 = **活体 == baseline** 的测试 (而非范围断言),
   加 `regen_baselines.py --check` (rc=2) 用于 CI。
2. **范围断言容易"看错对象"**: `600 <= nodes <= 800` 检查的是文件而不是行为,
   所以过时 baseline 也能绿灯。改成等值比较后, 漂移立刻可见。
3. **测试里硬编码数值 = 下一个漂移源**: 比例派生 (factor) 比绝对值稳健 —
   这是本次连带修复的教训。
4. **"补偿措施回审"值得作为常规动作**: 真因修完后, 旧的放宽/重试/技巧都要
   重新评估 (本次: pr5 重试注释更正为"环境兜底"; baseline 重生成; README 的
   "内存压力导致 partial AST" 更正为 iter_185 的真因)。

## 📢 待方豆决定 (未擅自动手)

| # | 事 | 证据 → 建议 | 代价 |
|---|---|---|---|
| 1 | `check_regression.py` 阈值 (L1/L4 50% / flakiness 0.7) | 实测修复后 stdev=0.0 / ratio=1.0, 阈值**偏松** → 建议收紧 (L1/L4 30%, flakiness 1.0); **会改变用户 CI 判定**, 故等拍板 (本次只改了注释说明) | 小 |
| 2 | `run_benchmark.py::reclaim_memory()` (4GB 技巧) | iter_185 后非必要 (每次 +3s) → 建议移除 | 小 |
| 3 | `pulp_axi_xbar.json` (不可复现) | 已保留 (移出代替删除原则) + README 标注历史快照; 是否移到 `baselines/outdated/` 待定 | 小 |
| 4 | 是否 push (本地领先 15 个 commit) | 等指令 | — |

## 🔎 顺带发现 (未修, 单独立项): Ventus viz 验证套件已失效

跑 `-m opensource` 时发现 `sim/tests/usage/test_ventus_all_viz_validation.py`
**14 failed** (opensource 集内唯一失败文件; canonical `-m "not opensource"` 看不到它)。
诊断 (与本次改动无关, 是既有问题):

1. **`--dot` 语义在 V100 变了**: `src/cli/commands/visualize.py:192` 起
   `--svg/--dot/-d` 是同一选项且**输出 SVG** ("was DOT before V100; --dot kept as
   deprecated alias"), 而测试仍断言 `.dot` 文件里是 DOT 文本 (`digraph` / `rankdir=LR`
   / `Segment`) → 实测报 `'Segment' not found in '<?xml version="1.0" ?><svg ...'`。
2. **artifact 依赖不全**: 测试读 `/tmp/sched_d1.dot`、`/tmp/r15*.dot`、
   `/tmp/sched_timing.png` 等, 但同文件的 `_ensure_sched_dots()` **不生成**这些
   (只生成 sched_pipeline*/sched_fanout/trace_fanin_d/sched_chain*) → 14 个失败里
   一批是 `FileNotFoundError`。
3. **该文件违反 AGENTS 核心纪律 1**: `_ensure_sched_dots()` 与多个测试用
   `--no-strict`, 且**忽略子进程 returncode** (silent) — 这既是被禁写法, 也正是
   第 2 点症状被隐藏的原因。

**建议 (待方豆拍板)**: 单开一个 task: ① 断言改 `--svg` 语义 (或改用仍写 DOT 的
`--dot`-only 路径 `visualize.py:1569`); ② 补齐 `_ensure_sched_dots()` 的 artifact
(含 PNG 用 `--png`); ③ 去掉 `--no-strict` 并检查 returncode (失败要可见);
④ PNG 类断言需要 graphviz, 缺环境时 skip 而非 fail。

## 📎 关联

- 新增: `tools/benchmark/inputs.py`、`tools/benchmark/regen_baselines.py`、
  `tools/benchmark/baselines/pr5_wrap.json`
- 重生成: `tools/benchmark/baselines/{picorv32,verilog_axi}.json`
- 测试: `sim/tests/integration/test_benchmark_picorv32.py`、
  `sim/tests/integration/test_benchmark_regression.py`、
  `sim/tests/usage/test_benchmark_pr5.py`
- 文档: `tools/benchmark/README.md`、`tools/benchmark/check_regression.py` 文档串
- 真因: `iter_185_slang_sourcemanager_lifetime.md` / `iter_186_ownership_hazard_sweep.md`
