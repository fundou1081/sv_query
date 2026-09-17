# Iteration 231: CLI 分层 P1 — 规范入口 drivers/loads + 别名机制 + 补 3 条 JSON + 抓出 builtin 遮蔽事故

**Metadata**:
- **Iteration #**: 231
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_cli_layering.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 成功 (P1a 完成; 全量 3317 → 3317+ 无退化; 额外抓出 1 个 pre-existing 真 bug)

## 🎯 本次目标

方豆拍板 **方案 (a)**: 语义 core 的规范入口用**顶层关系名** (`svq drivers` / `svq loads`),
老名 (`trace fanin` / `trace fanout`) 保留为兼容别名。

P1a 范围 (目录大搬迁 P1b 留下一轮, 避免一次动 26 个文件):
1. 别名机制 + `drivers`/`loads` 顶层注册
2. core 契约补齐: `search` / `snapshot save` / `snapshot delete` 的 `--json`
3. 检查器支持别名 (R1) + 新增 R7
4. 回归测试锁定新表面

## 🔬 实际结果

### 1. 规范入口 + 别名 (同一实现, 非双份)

- `trace.py`: `fanin`/`fanout` 去掉装饰器 → 文件尾显式双注册
  (`trace_app.command("fanin")(fanin)`), 顶层由 `main.py` 注册
  (`app.command("drivers")(_fanin_cmd)`)
- **关键**: 别名与规范名是**同一个函数对象** → 输出必然一致 (实测 `drivers ≡ trace fanin`、
  `loads ≡ trace fanout` 的 JSON 完全相同)
- docstring 改成"规范入口在前 + 老名标注为兼容别名"; 顶层 `help=` 单独写 (agent 看到的是关系名)
- 注册表新增 `ALIASES` / `canonical()` / `aliases_of()`, capabilities 与生成物输出别名

### 2. 补 3 条 core `--json`

| 命令 | 输出契约 |
|---|---|
| `search --json` | `{keyword,target,regex,case_insensitive,total_matches,file_count,files[{file,match_count,lines[{line,text}],truncated}]}` |
| `snapshot save --json` | `{ok,tag,path,files,node_count,edge_count,elaboration_errors,failed_files[]}` |
| `snapshot delete --json` | `{ok,tag,deleted}` (+ 取消时 `cancelled:true`; 不存在时 `ok:false` + rc=1) |

`search` 的**文本模式逐字保持不变** (老测试/老用户依赖), `--json` 时跳过文本打印。

### 3. ⚠️ 抓出一个 pre-existing 真 bug: 模块级 `def list(...)` 遮蔽 builtin

**发现路径**: 写完 `snapshot save --json` 后, 命令打印了 **4956 行快照表** + JSON。
我一开始怀疑是检查器/别名的问题, 用插桩 (`traceback.print_stack`) 拿到调用栈:

```
File "src/cli/commands/snapshot.py", line 137, in save
    "failed_files": list(failed_files or []),     ← 我新加的这行
File "src/cli/commands/snapshot.py", line 171, in list   ← 竟然进了 list 命令!
```

**根因**: `snapshot.py` 模块级定义了 `def list(...)` (快照 list 命令) → **遮蔽 builtin `list`**,
于是同模块里所有 `list(...)` 调用都变成"执行 list 命令" (返回 `None` + 打印全部快照表)。

**影响面 (实测量化)**:

| 位置 | 症状 |
|---|---|
| `snapshot.py:67` `list(sources.keys())` (**pre-existing**) | `snapshot save --filelist` 的 `files` 元数据**永远是空** (`None` → `[]`); 实测污染 stdout **55,577 行** |
| `snapshot.py:137` (我本迭代新加) | `snapshot save --json` 打印整张快照表 |

**修复 (根因层)**: 命令函数改名 `list_cmd` + 显式 `@snapshot_app.command("list")`
(命令名不变) → builtin `list` 恢复; 顺带把 JSON 分支写成 `[str(f) for f in (failed_files or [])]`。
**验证**: `snapshot save --filelist --json` → `files: 1` (修复前 `None`) ✓

**机械保障**: 检查器新增 **R7** —— CLI 模块级不得定义与 builtin 同名的函数/类
(全仓复扫: 仅此 1 处, 已修; 新增测试 `TestNoBuiltinShadowing` 锁死)。

### 4. 回归测试 (新增 `sim/tests/unit/test_cli_layering.py`, 17 passed)

| 类 | 锁什么 |
|---|---|
| `TestRegistryMatchesCli` | 每个 CLI 叶子必须是规范名或已声明别名 (防偷偷平铺加命令); 别名指向已登记命令; `drivers`/`loads` 在顶层可用 |
| `TestAliasEquivalence` | `drivers ≡ trace fanin` / `loads ≡ trace fanout` (JSON 完全一致); 老名仍出现在 `trace --help` |
| `TestCapabilities` | schema/layer 存在; exp 默认不出现、`--include-exp` 后 ≥20 个; view 默认包含; `--recommended` 是子集; core 声明 readonly/stable/schema=1 |
| `TestNoBuiltinShadowing` | 全 CLI 无 builtin 遮蔽 (R7 的测试版) |
| `TestNewJsonContracts` | search JSON + 文本模式不变; snapshot save/delete JSON; **`--filelist` 的 `files` 元数据 = 1** (锁 pre-existing bug); delete 不存在 tag 时 `ok:false` + rc≠0 |

## 💡 关键发现 / 决策

1. **别名必须"同一函数对象", 不能复制实现** —— 复制签名 = 两份真相 (改一处漏一处)。
   注册两次 (`app.command("drivers")(fn)` + `trace_app.command("fanin")(fn)`) 才能保证永不漂移。
2. **"检查器报绿"不等于"代码正确"**: 我的新代码把一个 pre-existing 的 builtin 遮蔽踩爆了,
   而当时的检查器是绿的 (R1~R6 都不覆盖这类错误) → 这就是加 **R7** 的理由。
   与 iter_190 / iter_227 / iter_230 同一条经验: **发现一类问题就补一条机械规则**。
3. **调试手段要升级得快**: 从"猜是别名/检查器" → "逐条读输出" → "插桩打印调用栈",
   最后一步 30 秒就定位了真因。**怀疑自己写的代码, 别先怀疑框架**。
4. **pre-existing bug 常以"另一个症状"暴露**: 我触发的是单文件路径, 却顺带发现
   filelist 路径早就坏了 (`files` 永远空 + 5.5 万行污染)。

## 📊 验证

| 项 | 结果 |
|---|---|
| 新增测试 | `test_cli_layering.py` **17 passed** |
| 全量 canonical | 见下方 (提交前跑) |
| `check_cli_layers.py` | rc=0 (R1~R7; 0 新增 / 3 已知 R3 mutation 待 P2 / 60 INFO) |
| `gen_cli_surface.py --check` | ✅ 一致 (别名单独成节) |
| 冒烟 | `drivers`/`loads`/`trace fanin`/`search --json`/`snapshot save|delete --json` 全部 rc=0 |

## 📎 产物

- 代码: `src/cli/_registry.py`(ALIASES/canonical) / `commands/trace.py`(双注册) /
  `commands/snapshot.py`(list→list_cmd 根因修复 + save/delete JSON) /
  `commands/search.py`(JSON) / `main.py`(顶层 drivers/loads)
- 工具: `tools/check_cli_layers.py` (+R7) / `tools/gen_cli_surface.py` (别名列) / `docs/CLI_SURFACE.md`
- 测试: `sim/tests/unit/test_cli_layering.py`
- 遗留: P1b 目录分层 (26 文件搬 `core/view/exp/dev`) / P2 移出写文件命令 + snapshot 目录迁缓存
  (顺带治理: 仓库根 `.svq/snapshots/` 已积累 **4955** 个快照 / 136 MB, 应随 P2 迁走)
