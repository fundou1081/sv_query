# Iteration 239: 1b — 快照目录迁出项目 + 只读行为证明测试

**Metadata**:
- **Iteration #**: 239
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_cli_layering.md` (P2 剩余)
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "开始 1b")
- **Outcome**: ✅ 成功 (默认位置迁出项目; 只读行为有测试兜底; 旧快照归档不删)

## 🎯 本次目标 (1b = P2 剩余)

1. `snapshot` 默认目录迁 `$SVQ_CACHE_DIR` —— 不再往项目目录写
2. **只读证明测试** —— 把"CLI 不改文件"从静态检查升级为**行为证明**
3. 治理仓库根累积的 **5035 个快照 / 137MB**

## 📦 改动

### 1. 快照目录解析 (单一真相源)

```python
resolve_snapshot_dir(explicit=None)   # 显式 > $SVQ_SNAPSHOT_DIR > <cache_dir>/snapshots
```
- `<cache_dir>` 复用既有 `resolve_cache_dir()`：`$SVQ_CACHE_DIR` > `$XDG_CACHE_HOME/svq` > `~/.svq/cache`
- `SnapshotManager(base_dir=None)` → 默认走上面的解析（6 个调用点全部自动受益）
- **不做 silent fallback**: 旧位置 `.svq/snapshots` 不会被自动读取；`snapshot list` 在"新位置为空但旧位置有货"时打一行**提示**（含 `SVQ_SNAPSHOT_DIR=.svq/snapshots` 的用法），只提示不读取

### 2. 受限环境的可操作报错

被沙箱拒写 `~/.svq/` 时（本次实测遇到），报错从裸 `Errno` 变成：
```
sv_query: error: 快照目录不可写: /Users/…/.svq/cache/snapshots ([Errno 1] Operation not permitted…).
  用 SVQ_SNAPSHOT_DIR=<可写目录> 覆盖 (如 SVQ_SNAPSHOT_DIR=$PWD/.svq-snapshots)
```
（一行 + rc=1，非 traceback；`run()` 本就捕获 `OSError`）

### 3. 只读**行为**证明测试 (`test_cli_readonly_guarantee.py`, 3 passed)

在临时项目目录里跑 **16 条只读命令**（stats/search/graph×3/instances/hierarchy/instance/connections/params/ports/paths/drivers/loads/capabilities×2），
比对目录树**逐文件 sha256 指纹**：必须**无新增、无删除、无修改**。

顺带锁定 iter_239 的效果:
- `snapshot save` 落在 `SVQ_SNAPSHOT_DIR`，**不在项目里创建 `.svq/`**
- 带显式输出的命令（如 `-o`）写到指定路径，而不是 cwd

> 与 `check_cli_layers.py` 的 **R3**（静态：CLI 内禁止写调用）形成**双保险**：
> 静态检查防"写了"，行为证明防"间接写/新增文件"。

### 4. 测试隔离 (避免污染用户 home)

改了 4 个测试文件，让它们把 `SVQ_SNAPSHOT_DIR` 指到各自的临时目录：
`test_trace_snapshot.py` / `test_snapshot_compare_flags.py`（子进程也带 env）/ `test_cli_layering.py` / `test_cli_semantic_queries.py`。
新增 `test_cache_dir_config.py` 的 **5 条**快照目录解析测试（默认/ env / 跟随 cache / 显式优先 / 不可写报错可操作）。

### 5. 旧快照治理：**归档不删**

仓库根 `.svq/snapshots/` → `.svq/legacy-2026-09-09-snapshots/`（`mv`，5035 个文件 / 137MB 原样保留）。
内容分布: `show`/`top`/`compat`/`pretty` 各 ~1250（**测试残留 4998 个**）+ ~37 个像样的（`2026061x`/`b4`/`v2`/`test-issue17`）。
`.svq/` 仍在 `.gitignore` 内 → 不影响 git；用户想删随时 `rm -rf .svq/legacy-2026-09-09-snapshots`。

**迁移旧快照**（一条命令，文档已给）:
```bash
SVQ_SNAPSHOT_DIR=.svq/legacy-2026-09-09-snapshots svq snapshot list
```

## 📊 验证

| 项 | 结果 |
|---|---|
| 新测试 `test_cli_readonly_guarantee.py` | **3 passed**（16 条命令目录树指纹不变） |
| `test_cache_dir_config.py` | 11 → **16 passed**（+5 快照目录解析） |
| 快照相关既有测试 | `test_trace_snapshot` / `test_snapshot_compare_flags` / `integration/test_snapshot` 全绿 |
| 全量 canonical | 见提交记录（预期 ≥3380, 0 退化） |
| 跑完后面板检查 | 仓库根**不再产生新快照**（`.svq/` 只剩归档目录） |

## 💡 关键发现 / 决策

1. **沙箱拒写 `~/.svq` 反而暴露了真实需求**: 新默认位置在**项目外**，受限环境（CI/沙箱/只读 home）
   必须有可操作的错误 + 覆盖开关。这正是"先按真实环境跑一遍"的价值。
2. **静态检查 + 行为证明是两件事**: R3 能防"我写了 `write_text`"，但防不了"某个库在 cwd 里建目录"
   （比如老的默认快照位置就是这样）。目录树指纹测试把这类**间接写入**也钉死了。
3. **归档不删**：5035 个文件里 4998 个是测试垃圾，但删之前不该由我判断"哪些没价值"——
   重命名目录（零删除）+ 给出迁移/清理命令，把决定权交回方豆。
4. **测试必须自己指定写入位置**: 默认值一改，测试就会往用户 home 写 —— 这本身就是"测试污染环境"
   的老问题（此前是往项目根写）。所有涉及落盘的测试现在都显式隔离。

## 📎 产物

- 修改: `src/trace/core/snapshot_manager.py`（resolver + 可操作报错）/ `src/cli/core/state/snapshot.py`（旧位置提示）/
  `src/cli/_registry.py`（note）/ 4 个测试文件（隔离）
- 新增: `sim/tests/unit/test_cli_readonly_guarantee.py`
- 数据治理: `.svq/snapshots/` → `.svq/legacy-2026-09-09-snapshots/`（归档，137MB）
- 文档: 本记录 + `CURRENT_TODO.md` + `overview.md` + `INDEX.md`
