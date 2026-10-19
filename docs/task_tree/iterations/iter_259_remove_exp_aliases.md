# Iteration 259: 删除 24 个 exp 老路径别名（叶子 90 → 66）

**Metadata**:
- **Iteration #**: 259
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-20 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（别名 26 → 2；叶子 90 → 66；全量 3422 passed）

## 🎯 目标

T2 最后一项硬指标：**别名 30 → 6**。iter_251 先做了"隐藏"，本次彻底删除。

## 🔬 做法（三步，按风险从低到高）

### 1. 机械改写测试调用点（151 处 / 25 文件）

用正则匹配**相邻字符串字面量对** `"<组>", "<子命令>"`，改写成
`"exp", "<组>", "<子命令>"`：

```
_run("sva", "timing", ...)            → _run("exp", "sva", "timing", ...)
_run_svq(["coverage", "analyze", ...]) → _run_svq(["exp", "coverage", "analyze", ...])
```

只对 10 个组的已知子命令名做替换（白名单），避免误伤断言里的同名字符串
（如 `data["protocol"]`）。

### 2. 补漏"只调组名"的调用

第一轮替换漏了 `_run_cli("coverage", "--help")` 这种**只给组名**的调用
（后面跟的是选项而非子命令）。第二轮按 `_run_cli("组"` / `_run("组"` /
`_run_svq(["组"` / `[... "run_cli.py", "组"` 四种前缀补改。

### 3. 删除注册表与 CLI 注册

- `_registry.ALIASES`：删 24 条（保留 `trace fanin` / `trace fanout` 两条 core 别名）
- `main.py`：移除 10 个 `add_typer(..., hidden=True)` 注册

## 🕳️ 关键发现：内部工具依赖老路径

第一次跑全量：**31 个失败**，全部在 `test_coverage_generate.py`，症状是
`No such command 'risk'`。

根因：`tools/coverage_gen_demo.py` 内部 **shell out** 到
`run_cli.py risk analyze --json` —— 删掉别名后这条子命令不存在了。

修法：改成 `exp risk analyze --json`。

> **教训**：删命令行别名时，除了测试，还必须搜"**内部脚本里的 shell out**"。
> 这类依赖不会出现在 import 图里，`grep "run_cli.py"` 才找得到。
> 本次全仓只有 1 处，但如果不是跑全量，它会以"覆盖率生成功能坏了"的形式上线。

## 📊 量化

| 指标 | 前 | 后 | 目标 |
|---|---|---|---|
| 别名 | 26 | **2** | 6 |
| 叶子（规范+别名） | 90 | **66** | — |
| 规范命令 | 64 | 64 | ~52 |
| 默认可见 | 40 | 40 | ~33 |
| 可见顶层条目 | 23 | 23 | — |

## ✅ 验证

- 全量门禁 **3422 passed / 0 failed**（含被改写的 151 处调用）
- 四项机械检查 rc=0（`check_cli_layers` 叶子统计 66 / 已登记 64）
- `SVQ_EXP` 手册与 `EXP_NAMESPACE.md` 同步

## 💡 决策

1. **删除而非继续隐藏**：iter_251 的隐藏让第一屏干净，但注册表仍背着 24 个别名，
   `check_cli_layers` 的"叶子数"永远虚高。彻底删掉后 66 才是真实表面积。
2. **保留 2 个 core 别名**（`trace fanin/fanout`）：它们是**稳定层**的入口，
   与 exp 的"无承诺"不同，删除属于另一类破坏性变更，需单独评估。
3. **先改测试再删代码**：这样每一步都能跑测试确认改写正确，
   而不是"删完看哪里红"。

## 🔗 相关

- 前序: [iter_251 隐藏老路径](iter_251_hide_legacy_paths.md)
- 政策: [EXP_NAMESPACE.md](../../EXP_NAMESPACE.md)
- 隐藏依赖: `tools/coverage_gen_demo.py`
