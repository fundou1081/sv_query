# Iteration 234: CLI 分层 P2 — `fix*` 拆分 (CLI 只读) + 写入能力移出 + 抓出第 5 个真 bug

**Metadata**:
- **Iteration #**: 234
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_cli_layering.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "做 p2 p3")
- **Outcome**: ✅ 成功 (CLI 写操作清零 → R3 检查器**零基线**; 全量 3334+ passed / 0 failed)

## 🎯 本次目标

落地方豆的硬约束 **"sv_query 不改 RTL"**: 把会写文件的命令移出 CLI, 只留只读诊断;
`fix <x>` 改名为规范入口 `diagnose <x>` (老名保留兼容别名)。

## 📦 改动

### 1. `fix*` 三文件 → `core/diagnose/` 四文件 (一个命令一个文件)

| 新文件 | 内容 | 写文件? |
|---|---|---|
| `core/diagnose/report.py` | `diagnose report` (按错误码给修复方向) + `FIX_RECOMMENDATIONS` | ❌ 只读 |
| `core/diagnose/timescale.py` | `diagnose timescale` (列出缺 timescale 的文件) | ❌ 只读 (**`--apply` 已移除**) |
| `core/diagnose/imports.py` | `diagnose imports` (找 UndeclaredIdentifier 的定义来源) | ❌ 只读 (**`--write` 已移除**) |
| `core/diagnose/widths.py` | `diagnose widths` (syntax tree + `$clog2` 解析真实位宽) | ❌ 只读 |

- 命令名: 规范 `diagnose <x>` (顶层组), 老名 `fix <x>` 保留为**兼容别名组** (同一函数对象, 无第二份实现)
- 写入能力落点: `tools/fix_timescale.py --apply` (已存在, 带 `.bak`) / **新增 `tools/fix_imports.py --write`**
- `src/cli/commands/fix.py` 已删 (`git rm`); `commands/` 目录现在**只剩 `__init__.py`** (P1b 的分层收尾)

### 2. 机械保障升级: R3 **零基线**

`check_cli_layers.py` 的 R3 (禁止隐式改文件) 原有 3 条已知基线 (`fix.py`×2 原地改 RTL + `fix_imports.py` 写 filelist)。
本轮全部消除 → **KNOWN 列表清空**: 现在 CLI 内**任何**写文件都会立即让检查器失败。
(同时 `diagnose timescale` 补了 `--json`, 满足 core 契约。)

### 3. 安全加固: `tools/fix_imports.py` 拒绝原地覆盖

早期 CLI 的 `--write` 没有"目标 ≠ 原 filelist"的守卫 (先读原文件再写到目标 → 若相同就是原地覆盖)。
新工具显式拒绝: `--write` == 原 filelist → **rc=2 + 明确报错**, 并有测试锁定。

## ❌ 第 5 个真 bug: `tools/fix_timescale.py` **长期无法运行** (本轮的测试首次暴露)

新测试 `test_tools_fix_timescale_apply_writes_and_backs_up` 第一次运行时, 工具报:

```
File ".../src/cli/_common.py", line 24, in <module>
    from trace.core.compiler import CompilationError
ModuleNotFoundError: No module named 'trace.core'; 'trace' is not a package
```

**根因**: 工具的路径引导写法是

```python
if str(_sv_query_root / "src") not in sys.path:      # ← guard 是错的
    sys.path.insert(0, str(_sv_query_root / "src"))
```

`src` 已经由 editable install 的 `.pth` 放在 `sys.path` 里, 但**排在 stdlib 之后** →
guard 判定"已在 path"于是**跳过插入** → `import trace` 命中 **stdlib 的 `trace.py`**。
实测 `sys.path` 顺序: `['tools', 'circt/...', '<repo>', 'python311.zip', 'python3.11', ..., '/…/sv_query/src']`
—— stdlib 在 `src` 之前。

**修法 (根因)**: 新增 `tools/_bootstrap.py` 作为**仓库内脚本的统一引导**:

```python
def ensure_src_first() -> None:
    s = str(SRC_DIR)
    while s in sys.path:        # 先移除已有条目 (可能与 stdlib 顺序错位)
        sys.path.remove(s)
    sys.path.insert(0, s)       # 无条件插到最前
```

`tools/fix_timescale.py` 与 `tools/fix_imports.py` 都改用它。
教训: **`if X not in sys.path` 这种 guard 在"顺序也重要"的场景下是错的** ——
"在 path 里" ≠ "在 stdlib 之前"。

## ⚠️ 附带发现: `MissingTimeScale` 在当前 pyslang 配置下**根本不触发**

为写端到端测试, 我构造了缺 `timescale` 的文件 (含 `#5` 延迟) → 编译器**一个诊断都不报**:

```
sv_query diagnose timescale --filelist /tmp/ts_probe2/p.f
→ ✅ No MissingTimeScale errors found. Nothing to fix.
```

也就是说 `diagnose timescale` (以及原来的 `fix timescale`) 对**任何**输入都返回"无需修复"。
原仓库里那两个 `--apply` 端到端测试**早就被注释掉**了 (注释写着"如果 pyslang 不报 MissingTimeScale…"),
即这个能力从未被真正验证过。

**本轮处理 (不掩盖)**:
1. 写入逻辑抽成 `apply_timescale_to_files(files_to_fix, timescale, backup)` → **直接单测** (写入 + `.bak` + idempotent), 不再依赖编译器是否报该诊断
2. 该问题**登记到 `docs/KNOWN_LIMITATIONS.md`** (命令形同虚设, 待查 pyslang 触发条件) 并在此记录
3. 不在本轮顺手"修"它 —— 触发条件是上游/配置问题, 需要单独诊断 (属新任务)

## 📊 验证

| 项 | 结果 |
|---|---|
| `check_cli_layers.py` | rc=0, **R3 零基线** (0 已知 / 0 新增) |
| 定向测试 | `test_fix_timescale/imports/widths/report` + `test_cli_layering` = **55 passed** |
| CLI 表面 | 65 规范命令 + **6 别名** (`drivers`/`loads` + 4 个 `fix *`); `CLI_SURFACE.md` 已重生成 |
| 全量 canonical | 见提交记录 (预期 ≥3334, 0 退化) |

## 💡 关键发现 / 决策

1. **"移出能力"必须同时移出测试**: 3 个测试直接测的是被移除的 CLI 能力 → 改为 (a) 断言 CLI **拒绝**该选项 (契约),
   (b) 到 `tools/` 里测真实写入路径。**不是删测试, 是换被测对象**。
2. **一次改动暴露两个 pre-existing bug** (工具路径 guard / 诊断不触发) —— 都因为"这段代码从来没被真正跑过"。
   这与 iter_231 的 builtin 遮蔽是同一类: **没有测试覆盖的路径 = 事实上的死代码**。
3. **检查器零基线是"能力边界"的机械表达**: R3 从"3 条已知 + 新违规失败"变成"任何写操作即失败",
   从此"CLI 只读"不再依赖人的记性。

## 📎 产物

- 新增: `src/cli/core/diagnose/{report,timescale,imports,widths}.py` / `tools/fix_imports.py` / `tools/_bootstrap.py`
- 删除: `src/cli/commands/fix.py` (拆分) ; `commands/` 仅剩 `__init__.py`
- 修改: `main.py` (diagnose 规范组 + fix 别名组) / `_registry.py` (4 条别名 + out 层清空) / `check_cli_layers.py` (R3 零基线) / 4 个测试文件
- 文档: 本记录 + `CLI_SURFACE.md` (重生成) + `KNOWN_LIMITATIONS.md` (MissingTimeScale 形同虚设) + `CURRENT_TODO/overview/INDEX`
