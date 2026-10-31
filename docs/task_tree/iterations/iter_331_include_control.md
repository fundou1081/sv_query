# Iteration 331: include_control 显式 unsupported（PLAN P35.1）

**Metadata**:
- **Iteration #**: 331
- **Task Tree Level**: L2（PLAN `P35.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先修 include_control"）
- **Outcome**: ✅ 完成（不再 AttributeError；2655 passed）

## 🐛 问题

`trace_fanout(..., include_control=True)`:

```python
allowed_kinds.add(EdgeKind.CONTROL)  # EdgeKind 没有 CONTROL
→ AttributeError: CONTROL
```

CLI `trace fanout --include-control` 会崩，不是用户/agent 可理解的错误。

## 🔧 修复

图构建器当前**不产生 CONTROL 边**，所以不伪造、不静默：

```python
if include_control:
    raise ValueError(
        "include_control is unsupported: graph builder emits no CONTROL edges; "
        "use include_conditional / --include-conditional for branch conditions"
    )
```

- 删除 `EdgeKind.CONTROL` 引用；
- CLI help 标 `[UNSUPPORTED]`；
- 错误走 per-signal `E_INVALID_INPUT`，不再 AttributeError；
- 错误路径保留已解析的 `resolved_signal/resolution`（不再显示 internal）。

## 🧪 测试

新增 `test_include_control.py`（2）：
- `--include-control` 返回显式 unsupported，`ok=false`，resolution 保留；
- help 含 `[UNSUPPORTED]`。

全量 **2655 passed / 0 failed**。

## 📌 后续

若需要真正的 always 块控制依赖边（sensitivity/control refs），需单独建模
`EdgeKind` + builder，不属于本次修复；当前用 `--include-conditional` 查分支条件。

## 🔗 相关

- 计划: [PLAN.md P35.1](../../../PLAN.md)
