# Iteration 193: 合并两套 filelist 加载器 (方案 A: 纯解析器)

**Metadata**:
- **Iteration #**: 193
- **Task Tree Level**: L2 (输入解析统一)
- **Parent Task**: iter_190/192 未决项 (方豆指示 "先合并 filelist")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 单一实现 + 两侧一致 + parity 不变量锁

## 🎯 本次目标

方豆指令: "先合并 filelist"。把 iter_190/192 记录的两套加载器 (tracer 侧
`SVCompiler.add_filelist` / CLI 侧 `cli._common._read_filelist`) 合并为一套实现。

## 📊 当前状态 / 预期结果

两套实现的差异 (实测, 见 `docs/architecture/filelist_loader_unification.md`):
相对路径基准不同 (filelist 目录 vs base_dir) **且嵌套 `-f` 基准也不同**
(tracer 按 cwd / CLI 按 filelist 目录) → 同一 filelist 两侧结果可不同。

## 🔬 实际结果

### 方案选择 (AGENTS 要求 ≥2 个)

A 抽纯解析器 (选定) / B CLI 复用 tracer 私有函数 (拒绝: 耦合方向错) /
C CLI 构造 SVCompiler (拒绝: 引入编译副作用)。详见 ADR。

### 实现

- 新增 `src/trace/core/filelist.py`: `FilelistSpec{files, include_dirs, defines,
  missing, filelists}` + `parse_filelist(path, base_dirs=..., env=..., already_loaded=...)`:
  - 语法: 文件行 / `+incdir+` (支持逗号分隔多目录) / `+define+` (**按顺序**影响后续
    `${VAR}`) / `+libext+`(忽略) / `-f`,`-F` (循环保护) / `${VAR}`、`$VAR`、`~` /
    空行与 `#`、`//` 注释;
  - 相对路径候选: **filelist 所在目录 → base_dirs**; **嵌套 `-f` 用同一套候选**
    (原两侧规则不同, 一并统一);
  - 缺失条目 / 坏行 → `spec.missing` + 告警 (延续 iter_190 "不静默");
  - filelist 不存在 → `FileNotFoundError("Filelist not found: ...")` (与 CLI 原行为一致)。
- `SVCompiler.add_filelist` → 薄封装: 应用 include_dirs + add_files + `spec.warn_missing()`;
  保留 `env`/`already_loaded`/`missing_entries` 参数签名 (API 兼容)。
- `cli._common._read_filelist` → 薄封装: 读文件 + `spec.warn_missing()`;
  保留"零文件只告警不硬失败" (真正编译入口是 tracer)。

实测 (合并后):
| 场景 | CLI 侧 | tracer 侧 |
|---|---|---|
| filelist 目录相对 (cwd=/) | 1 | 1 |
| 仓库根相对 (industrial_filelists) | 1 | 1 |

### 回归锁

- `sim/tests/unit/test_filelist_parity.py` (5 测试): **两侧文件集必须一致** —
  相对 filelist 目录 / 相对 cwd / 含 `+incdir+`+`+define+`+嵌套 / 缺失条目 /
  filelist 不存在 (两侧都抛)。这就是"不可能再出现第二套实现"的不变量。
- 既有 `test_filelist_resolution.py` (4 测试) 继续通过。

自伤记录: parity 测试第一版让 CLI 侧传 `base_dir=tmp_path` 而 tracer 侧固定用 cwd
→ 断言失败。诊断: 生产里两侧的"第二基准"其实都是 **cwd** (CLI 由调用方传 cwd/项目根)
→ 测试改为 `monkeypatch.chdir(tmp_path)` 后对比真实语义 (**不是**改断言迁就实现)。

## 💡 关键发现 / 关键技术 / 决策

1. **合并的前提是"先把差异测量清楚"**: iter_190 发现分歧、iter_192 用多候选让结果
   一致、iter_193 才合并 —— 中间那步 (measure → align → unify) 让合并风险可控。
2. **纯解析器 + 结构化结果** 是这类合并的正确抽象: 解析 (语法/路径/展开) 与
   应用 (编译 vs 读文件) 分离, 两侧差异只体现在"应用"侧。
3. **parity 测试比单元测试更重要**: 单测各自通过 ≠ 两侧一致; 只有跨消费方对比
   才锁得住"单一实现"。

## 📢 待方豆决定 (其余未决项)

push (领先 21 个 commit) / `--filelist` 全缺失是否报错 / 13 个 SVG skip /
`check_regression.py` 阈值 / `reclaim_memory()` / 上游 trap issue。

## 📎 关联

- 新增: `src/trace/core/filelist.py`、`sim/tests/unit/test_filelist_parity.py`
- ADR: `docs/architecture/filelist_loader_unification.md`
- 改动: `src/trace/core/compiler.py::add_filelist`、`src/cli/_common.py::_read_filelist`
- 前置: `iter_190_except_pass_cleanup.md`、`iter_192_filelist_resolution_bases.md`
