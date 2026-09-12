# Iteration 194: 空 filelist 明确报错 + `reclaim_memory` 改为 opt-in

**Metadata**:
- **Iteration #**: 194
- **Task Tree Level**: L2 (输入契约 / 工具默认值)
- **Parent Task**: iter_190~193 未决项 (方豆 "继续" — 按已有证据做小决策项)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 两项落地 + 验证

## 🎯 本次目标

iter_190~193 记录的两个小决策项, 证据已充分, 本轮落地:
1. `--filelist` 一个文件都解析不出来时, 过去**只告警** → 命令继续跑并输出**空图**
   (rc=0), 用户以为成功 (静默失败的一种); 是否升级为错误。
2. `tools/benchmark/run_benchmark.py::reclaim_memory()` (4GB "reclaim inactive
   pages" 技巧) 在 iter_185 修掉真因后已无必要, 但每次跑多花 ~3s。

## 🔬 实际结果

### 1. 空 filelist → `CompilationError` (两个消费方都报)

- `SVCompiler.add_filelist`: `spec.files` 为空 → `CompilationError("filelist ... 没有
  解析到任何源文件 (N 个条目缺失/不可解析) — 请检查路径与基准目录")`;
- `cli._common._read_filelist`: 同样报错 (它过去只告警)。**前提**: iter_193 已把两侧
  解析规则统一 → "空"是真的空, 不再出现"CLI 侧空 / tracer 侧有"的假空。

链路验证: `sv_query visualize graph --filelist /tmp/fl_allmissing.f` (内容 x.sv/y.sv
均不存在) → 修复前 rc=0 + 空图; 修复后 **rc=1 + 一行明确错误** (无 traceback, 走
iter_191 的统一格式化)。正常 filelist 仍 rc=0。

### 2. `reclaim_memory()` 默认关闭, 保留为 `--reclaim`

- 默认不再执行 (省 ~3s/次); `--reclaim` 显式开启;
- 理由写进 `--help` 与代码注释: 该技巧当年是为掩盖 SourceManager 生命周期 bug 的
  症状 (iter_185 已修, 同一输入 3 次 stdev=0.0), 内存紧张的机器仍可显式打开。

### 3. 自伤与纠正 (如实记录)

把 CLI 侧"空即报错"加上后, **`test_naplespu_4_level_chained_include` 失败**:
该测试用的 filelist 里写的是**仓库根相对**路径, 而调用方传给 `_read_filelist` 的
`base_dir` 恰好是 **filelist 自己的目录** → 候选基准只剩一个 (filelist 目录) →
误判"条目不存在" → 新错误触发, rc=1。

诊断 (看错误里的候选基准列表) → 根因是**候选集合两边不等价** (tracer 侧第二基准
固定 cwd; CLI 侧取决于调用方) → 修复: CLI 侧候选 = `[base_dir, cwd]` (去重),
保证与 tracer 侧一致。修完 31 个相关测试全绿。

教训: **收紧契约 (从告警升级为错误) 之前, 必须先确认"触发条件两边等价"** ——
否则会把"解析能力差异"误报成"输入无效"。

## 💡 关键发现 / 关键技术 / 决策

1. **"告警"与"错误"的界线**: 告警适合"部分降级但结果仍可用"; 一旦**结果为空**
   (没有任何输入生效), 就必须是错误 —— 否则用户拿到空产物却看到 rc=0。
2. **统一解析是实现"能报错"的前提**: iter_192 时我**不能**让 CLI 侧空即报错
   (当时两侧规则不同, CLI 侧可能是假空); iter_193 合并后才敢加这条错误。
   先测量 → 对齐 → 统一 → 收紧契约, 顺序不能颠倒。
3. **默认值也是决策**: `reclaim_memory` 保留了(以防 OOM)但改为 opt-in —— 不删代码
   (移出代替删除) 只改默认, 兼顾"默认快"与"极端环境仍可用"。

## 📢 剩余未决项

push (领先 22 个 commit) / 13 个 SVG 语义 skip / `check_regression.py` 阈值 /
上游 pyslang trap issue。

## 📎 关联

- 代码: `src/trace/core/compiler.py::add_filelist`、`src/cli/_common.py::_read_filelist`、
  `tools/benchmark/run_benchmark.py`
- 测试: 既有 `test_filelist_parity.py` / `test_filelist_resolution.py` /
  `test_cli_hostile_input.py` 全绿 (49 passed)
- 前置: `iter_192_filelist_resolution_bases.md`、`iter_193_filelist_loader_merge.md`
