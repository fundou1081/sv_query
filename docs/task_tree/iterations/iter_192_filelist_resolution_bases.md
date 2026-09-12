# Iteration 192: filelist 相对路径双基准解析 — 消除两套加载器的分歧

**Metadata**:
- **Iteration #**: 192
- **Task Tree Level**: L2 (输入解析一致性)
- **Parent Task**: iter_190/191 边界正确性续 (方豆 "继续")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 分歧消除 + 两种约定都钉进测试 (为将来统一做安全网)

## 🎯 本次目标

iter_190 记录了一个未决项: 项目里有**两套** filelist 加载器, 相对路径规则不同 →
同一份 filelist 两侧结果可能不一致, 且 CLI 侧会对**实际存在**的文件误报
"条目不存在" (iter_190 新加的告警变成噪声)。本轮先把它**测量清楚并修掉误报**,
同时把两种约定写成测试 (这样将来真要统一加载器时有安全网)。

## 📊 当前状态 / 预期结果

| 加载器 | 相对路径基准 |
|---|---|
| `src/trace/core/compiler.py::add_filelist` (编译入口) | **filelist 所在目录** |
| `src/cli/_common.py::_read_filelist` (CLI 辅助, 供 SVA/coverage 等) | **base_dir (cwd / 项目根)** |

实测 (`cwd=/` 而 filelist 在 `/tmp/flprobe/fl_rel.f`, 内容 `sub/m.sv`):

```
CLI 侧:   0 个文件   ← 且打出 "条目不存在" 告警 (文件其实存在!)
tracer 侧: 1 个文件
```

更麻烦的是**仓库内两种约定都存在**: `sim/tests/pyslang_type_fixtures/
industrial_filelists/light/sync_fifo.f` 里写的是 `sim/tests/integration/...`
(仓库根相对) —— 只按 filelist 目录解析同样会 0 个文件。

## 🔬 实际结果

### 修复: CLI 侧按两个候选基准依次尝试

```python
candidates = [ (filelist_path.parent / line).resolve(),   # ① tracer 侧约定
               (base_dir / line).resolve() ]              # ② cwd/项目根约定
full = next((c for c in candidates if c.exists() and c.is_file()), None)
if full is None:
    logger.warning("filelist 条目不存在, 跳过: %s (候选基准: %s)", line, ...)
```

- 都不中才告警, 且告警里**列出候选基准** (可行动);
- 不是"静默 fallback": 解析规则是显式的两个候选, 失败仍明确告警 (AGENTS 允许
  的是"隐式掩盖", 这里既不隐式也不掩盖)。

实测 (修复后):

| 场景 | 修复前 | 修复后 |
|---|---|---|
| filelist 目录相对 (`sub/m.sv`, cwd=/) | CLI 0 / tracer 1 | **CLI 1 / tracer 1** |
| 仓库根相对 (`sim/tests/...`, cwd=仓库) | CLI 0 | **CLI 1** |

### 回归锁 `sim/tests/unit/test_filelist_resolution.py` (4 测试)

① filelist 目录相对 → 能加载; ② base_dir 相对 → 能加载;
③ 两个基准都不中 → 不计入 + 明确告警 (caplog 断言); ④ filelist 本身不存在 →
`FileNotFoundError: Filelist not found` (不是静默空结果)。

自伤记录: 第 1 版测试里用 `rec.message % rec.args` 格式化断言日志 → `TypeError`
(自己写错), 改用 `rec.getMessage()` 修正。

## 💡 关键发现 / 关键技术 / 决策

1. **"两种约定并存"是现实**: 不能靠"选一个正确答案"解决, 只能**多候选解析**
   (filelist 目录优先, 再 base_dir), 并把失败原因(候选基准)告诉用户。
2. **告警也可能是噪声**: iter_190 加的"条目不存在"告警本身正确, 但因为解析基准
   不对而误报 → **告警的可信度取决于它依赖的解析逻辑**。修完解析, 告警才有价值。
3. **两套加载器仍未统一**: 本轮只让**结果一致**(CLI 侧是 tracer 侧的超集),
   代码仍有两份实现 → 统一登记为待决项 (见下)。

## 📢 待方豆决定

| # | 事 | 建议 | 代价 |
|---|---|---|---|
| 1 | 两套 filelist 加载器是否合并为一套 | 建议以 tracer 侧 (`SVCompiler.add_filelist`) 为唯一实现, CLI 侧改为调用它 (本轮的安全网测试已就位) | 中 |
| 2 | `--filelist` 条目全部缺失仍 rc=0 (只有 warning) | 是否升级为错误 | 小 |

## 📎 关联

- 代码: `src/cli/_common.py::_read_filelist_recursive`
- 测试: `sim/tests/unit/test_filelist_resolution.py`
- 前置: `iter_190_except_pass_cleanup.md` (告警来源)、`iter_191_cli_error_formatting.md`
