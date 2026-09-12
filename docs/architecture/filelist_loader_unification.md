# 架构决策: filelist 加载器合并为一套实现

| 字段 | 内容 |
|---|---|
| **时间** | 2026-09-08 GMT+8 (iter_193) |
| **状态** | ✅ 已执行 |
| **触发** | 方豆指示 "先合并 filelist" |

## 遇到的问题

项目里存在**两套** filelist 加载器, 规则不同 → 同一份 filelist 两侧结果不一致:

| 加载器 | 用途 | 相对路径基准 | 嵌套 `-f` 基准 |
|---|---|---|---|
| `src/trace/core/compiler.py::SVCompiler.add_filelist` | 真正编译入口 | filelist 所在目录 | **cwd** |
| `src/cli/_common.py::_read_filelist` | CLI 辅助 (供 SVA/coverage 等要 sources 的命令) | base_dir (cwd/项目根) | filelist 所在目录 |

实测症状 (iter_190 发现): `cwd=/` 而 filelist 在 `/tmp/flprobe/fl_rel.f` (内容 `sub/m.sv`)
→ CLI 侧 0 个文件 + **对实际存在的文件误报"条目不存在"**; tracer 侧 1 个文件。
且仓库内**两种约定并存**: `sim/tests/pyslang_type_fixtures/industrial_filelists/light/sync_fifo.f`
用仓库根相对路径 → 只按 filelist 目录解析同样 0 个文件。
(iter_192 先用"多候选解析"让**结果**一致, 代码仍是两份。)

## 考虑的方案

| 方案 | 做法 | 利 | 弊 |
|---|---|---|---|
| **A (选定)** | 抽出**纯解析器** `src/trace/core/filelist.py::parse_filelist()` → 结构化 `FilelistSpec{files, include_dirs, defines, missing, filelists}`; 两个消费方变薄封装 | 单一实现; 结构化数据 (AGENTS §6); 两侧天然零分歧; 解析器可单测 | 需精确保持既有语义 (有全量 + parity 测试兜底) |
| B | CLI 侧调用 tracer 的解析函数 | 改动小 | 耦合方向错 (CLI → core 私有); `+incdir+`/`+define+` 语义差异仍需分支 |
| C | CLI 侧构造 `SVCompiler` 加载 | 复用彻底 | 引入编译副作用与开销 (CLI 只想读文件内容) → 拒绝 |

## 决策结果

采用 **方案 A**:

- 新增 `trace/core/filelist.py` (唯一解析实现):
  - 语法: 文件行 / `+incdir+` / `+define+` (按顺序影响后续 `${VAR}`) / `+libext+`(忽略) /
    `-f`,`-F` 嵌套 (循环保护) / `${VAR}`、`$VAR`、`~` 展开 / 空行与 `#`、`//` 注释;
  - 相对路径候选 = **filelist 所在目录 → base_dirs** (嵌套 `-f` 同一套候选);
  - 缺失条目/坏行记入 `spec.missing` 并告警 (不静默, 延续 iter_190);
  - filelist 本身不存在 → `FileNotFoundError("Filelist not found: ...")`。
- `SVCompiler.add_filelist` → 应用 `include_dirs` + `add_files(files)` + 汇总告警。
- `cli._common._read_filelist` → 读文件成 sources dict + 汇总告警 (保留"零文件只告警"语义,
  因为真正编译入口是 tracer)。

## 利弊权衡

- **接受**: 解析器要支持两个消费方的并集语义, 略多于各自所需 (如 CLI 不需要 `defines`);
- **换取**: 规则只有一处, 不可能再出现"两侧不同"; 新增 parity 测试
  (`sim/tests/unit/test_filelist_parity.py`) 把"两侧文件集一致"变成不变量;
- **放弃**: 方案 B 的最小改动量 (但会留下两份语义); 方案 C 的彻底复用 (但引入副作用);
- **验证**: 全量 canonical 套件 + 文件集一致性测试 (相对 filelist / 相对 cwd /
  含 incdir+define+嵌套 / 缺失条目 / filelist 不存在 五种场景)。
