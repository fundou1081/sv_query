# Iteration 251: 老路径从 `--help` 隐藏 (10 个顶层组)

**Metadata**:
- **Iteration #**: 251
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（顶层可见组 34 → 24；老路径仍可调用；全量门禁绿）

## 🎯 目标

`exp` 降级区的 24 条命令在 iter_235 收进了 `svq exp <组> <子>` 前缀，
但 10 个历史顶层组（`protocol` / `handshake` / `backpressure` / `coverage` /
`randomize` / `risk` / `sva` / `verify` / `cdc` / `timing`）仍**平铺在 `svq --help` 里**。
用户看到的是"命令太多"，其中一半是这些历史入口。

## 🔬 决策：先隐藏，不急着删

彻底删除别名需要更新约 **151 处测试调用**（AST 扫描：`_run("protocol", "semantics", ...)`
这类形态遍布 20 个文件）。这是兼容性破坏，且当前没有版本边界。

两步走：

| 步骤 | 本次是否做 | 效果 |
|---|---|---|
| 老路径 `hidden=True`（仍可调用，但不出现在 help） | ✅ | 顶层可见条目 33→23，零测试改动 |
| 从 `_registry.ALIASES` 删除 24 条 + 更新 151 处调用 | ❌ 留下一版 | 叶子数 93→69 |

**为什么隐藏就能解决"命令太多"**：`svq --help` 是人和 agent 的第一屏；
隐藏后第一屏只剩规范入口（core/view/exp/dev 四层 + `exp` 一个入口组）。

## 🔬 实际结果

```python
# src/cli/main.py
for _legacy_name, _legacy_app in (
    ("risk", risk_app), ("sva", sva_app), ("timing", timing_app), ("cdc", cdc_app),
    ("coverage", coverage_app), ("verify", verify_app), ("backpressure", backpressure_app),
    ("handshake", handshake_app), ("protocol", protocol_app), ("randomize", randomize_app),
):
    app.add_typer(_legacy_app, name=_legacy_name, hidden=True)
```

### 验证

- `svq --help` 里上述 10 个组的出现次数 = **0**
- `svq protocol list` 仍正常工作（可用性未破坏）
- `capabilities` / `check_cli_layers` 计数不变（93 叶子 / 67 规范）
- 全量门禁见下

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `svq --help` 顶层可见条目 | 33 | **23** |
| 规范命令 / 别名 / 叶子 | 67 / 26 / 93 | 不变（隐藏不改注册表） |
| 测试改动 | — | **0** |

## 💡 决策

1. **"隐藏"是减法的一等形态，不只是删除的过渡态。** 对历史入口，隐藏同时满足
   "不再干扰发现"和"不破坏既有脚本"；删除只在有版本边界、且能一次性改完调用方时才做。
2. **计数要分两种口径看**：注册表口径（93 叶子）没变，但**可见口径**（help 第一屏）
   从 34 组降到 24 组。用户体感跟着后者走 —— 所以减法效果要用"可见面"度量，
   而不是只盯注册表数字。
3. **删除排期写进文档**：`docs/EXP_NAMESPACE.md` 明确"下个 minor 版本边界执行，
   需更新约 151 处测试调用"，避免下一个人以为忘了。

## 🔗 相关

- 政策: [EXP_NAMESPACE.md](../../EXP_NAMESPACE.md)
- 前置: [iter_250 instances 合并](iter_250_instances_merge.md)
