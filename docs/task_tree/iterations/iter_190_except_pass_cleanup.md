# Iteration 190: `except: pass` 全仓清算 — 纪律从"声明"变成"可执行检查"

**Metadata**:
- **Iteration #**: 190
- **Task Tree Level**: L1 (纪律强制 / 静默失败根除)
- **Parent Task**: iter_189 边界正确性续 (方豆 "继续")
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 52 处 → 0 处 + 新增机械检查器 + 纪律测试

## 🎯 本次目标

顺着 iter_189 的"边界正确性"主线查 CLI 敌意输入, 途中在 filelist 加载器里发现
**AGENTS 明令禁止的 `except Exception: pass`**, 顺手全仓量化 → 发现纪律声明已失效。

## 📊 当前状态 / 预期结果

AGENTS.md v1.4 写: "2026-08-29 已全仓清理 — 全仓 `except: pass` 计数 = 0。
**新代码禁止引入**"。预期实测应为 0。

**实测 (AST 扫描, 只算 handler 体内 `Pass`)**: **52 处**, 分布:

| 异常类型 | 处数 | 判定 |
|---|---|---|
| `Exception` (含 bare) | **25** | ⛔ AGENTS 明令禁止 |
| `TypeError` | 23 | ⚠️ 收窄但无注释说明 |
| `(UnicodeDecodeError, TypeError)` | 2 | ⚠️ 同上 |
| `ImportError` / `RecursionError` | 2 | ⚠️ 同上 |

→ **声明没有机械保障 = 会重新长回来**。这是本次的真正交付点。

## 🔬 实际结果

### 1. 52 处全部改为"失败可见"

| 场景 | 处理 |
|---|---|
| 核心分析路径 (`src/trace/**`) | `logger.debug("...: 忽略 <type>: %s", e)` |
| CLI 一次性命令 / 写文件 / 清理 (`src/cli/**`, `src/applications/**`) | `logger.warning(...)` |
| handler 体只有 `pass` | 替换为日志 (并补 `as e`) |
| handler 体还有别的语句 | 删除 `pass` (保留其他语句) |
| `pass` 行上的理由注释 (11 处) | **保留**为日志行尾注释 (e.g. `# 检测失败不影响正常编译`) |
| 无 logger 的模块 (9 个) | 补 `import logging` + `logger = logging.getLogger(__name__)` |

结果: AST 扫描 **`except: pass` = 0**; 全仓 `*.py` 语法检查 0 错误;
`_archived*` 目录除外 (归档快照, 检查器显式跳过)。

### 2. 新增机械检查器 `tools/check_except_pass.py`

```
$ python3 tools/check_except_pass.py
检查目录: src (跳过 ['.git', '__pycache__', '_archived', '_archived_dot'])
✅ except ...: pass 计数 = 0
```

规则: ① 任何 `except ...: pass` → 违规 (含收窄类型; 失败必须可见);
② 允许形态 = 收窄类型 + `...` + 说明注释 (警告级: 缺注释时提示);
③ 归档目录 (`_archived*`) 与 `__pycache__` 跳过。

### 3. 纪律接进测试集 (否则没人跑)

`sim/tests/unit/test_discipline_except_pass.py` (5 测试):
- 仓库 0 违规 (跑真实检查器, 非自证);
- **检查器能检出**宽类型 / 收窄类型 pass (自检: 否则检查器是摆设);
- 不误报"捕获 + 日志"的允许形态;
- `...` 无注释 → 警告。

### 4. 连带修掉 filelist 的静默缺陷 (同一条链路)

`src/cli/_common.py::_read_filelist` 里那处 `except Exception: pass` 上面还写着
"读失败的文件跳过, 不静默吞" —— 实际就是吞了。修的过程中发现**更实质的静默缺陷**:
filelist 里**缺失的条目被无声跳过** (两个加载器都有):

| 位置 | 原行为 | 现行为 |
|---|---|---|
| `src/cli/_common.py::_read_filelist_recursive` | 缺失条目静默跳过 | 逐条 + 汇总 `logger.warning` |
| `src/cli/_common.py` 读失败 | `except Exception: pass` | `except OSError as e:` + warning (含条目名) |
| `src/trace/core/compiler.py::add_filelist` | 缺失文件 / 缺失嵌套 filelist / 语法错误的 `-f` 行 全部静默 | 三类都 warning, 并汇总"共 N 个条目未加载" |

实测: `filelist` 写错一个路径时, 现在 stderr 明确列出漏掉的是哪个文件
(过去用户会拿到"少几个文件的图"却以为完整)。

### 5. 中途自伤与纠正 (如实记录)

- 第 1 版脚本**只插入日志、把 `pass` 留在原地** → AST 扫描的"body 长度==1"判据
  漏掉了这些点 (自检时"剩余 27 处"是假象)。发现方式: 抽查 diff 看到 `pass` 还在。
- 第 2 版脚本对"handler 体只有 `pass`"的情况直接**删行** → **10 个文件语法错误**
  (`expected an indented block`)。恢复方式: 动手前做过 `cp -r src /tmp/src_backup_iter190`
  → 回滚重做。
- 第 3 版**丢失了 `pass` 行上的理由注释** (11 处, 如 `# 检测失败不影响正常编译`)
  → 再次回滚, 第 4 版保留注释。
- 教训: 机械改写 100+ 处代码时, **先备份整棵子树**、改完立刻 `ast.parse` 全量校验、
  并抽查 diff —— 三样缺一不可; "扫描计数为 0" 不能作为唯一的正确性证据。
- 另: 第 1 版我还在 CLI filelist 加载器加了"零文件即报错", 触发 2 个既有测试失败
  (`test_naplespu_4_level_chained_include` / `test_strict_default_filelist`)。诊断发现
  CLI 侧加载器与 tracer 侧加载器的**相对路径解析基准不同** (前者按 base_dir, 后者按
  filelist 所在目录) → CLI 侧零文件是**正常**的 → 回退为只告警, 不硬失败
  (改断言糊过去是禁止的)。

## 💡 关键发现 / 关键技术 / 决策

1. **纪律必须有机械保障**: "全仓计数 = 0" 写在文档里 4 个月后变成 52 —— 只有
   可执行检查 + 测试才算数。检查器本身也要**自检能检出违规**, 否则是摆设。
2. **静默跳过 ≈ 假数据**: filelist 缺失条目静默跳过 → 用户拿到"看起来成功的不完整
   结果"。这类缺陷比崩溃更危险 (崩溃至少可见)。
3. **两套 filelist 加载器是隐患**: CLI 侧 (`_common._read_filelist`, 按 base_dir) 与
   tracer 侧 (`compiler.add_filelist`, 按 filelist 目录) 语义不同 → 同一份 filelist
   两侧结果可能不一致。本次只统一了"可见性", 语义统一登记为待决项。
4. **机械改写 100+ 处的安全流程**: 备份子树 → 改写 → `ast.parse` 全量校验 →
   抽查 diff → 跑 gate。任何一步省略都会像本次一样多花两轮。

## 📢 待方豆决定

| # | 事 | 建议 | 代价 |
|---|---|---|---|
| 1 | 两套 filelist 加载器的相对路径语义不一致 | 统一为一套 (建议 tracer 侧为唯一真相源, CLI 侧复用它) | 中 |
| 2 | 是否把 `check_except_pass.py` 加进 `AGENTS.md` 提交前清单 (与 `check_docs.py` 并列) | **已加** (本次), 若不同意可撤 | — |
| 3 | CLI 敌意输入仍会**打印原始 traceback** (rc=1 但难看): `FileNotFoundError` / `IsADirectoryError` / `UnicodeDecodeError` / `CompilationError` | 建议下一轮做 CLI 顶层统一错误格式化 (证据矩阵已备好) | 小 |

## 📎 关联

- 新增: `tools/check_except_pass.py`、`sim/tests/unit/test_discipline_except_pass.py`
- 改动: `src/` 43 文件 (52 处 pass → 日志; 9 文件补 logger)
- filelist 可见性: `src/cli/_common.py`、`src/trace/core/compiler.py::add_filelist`
- 纪律: `AGENTS.md` (核心纪律 2.5 + 提交前清单)
