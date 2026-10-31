# Iteration 327: audit/diagnose/view 降级 exp（PLAN P31.1）

**Metadata**:
- **Iteration #**: 327
- **Task Tree Level**: L2（PLAN `P31.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "audit diagnose view ... 功能完成度低，移动到实验档位，默认不提供"）
- **Outcome**: ✅ 完成（默认 core 23 / exp 12；2635 passed）

## 🎯 决定

- `audit`、`diagnose`：core → **exp**
- 全部 `view`（visualize*/arch*/design*/trace overview）：view → **exp**
- 默认 **--help / capabilities 不提供**；老路径仍可显式调用（兼容）
- `capabilities --include-exp` 才列出

## 🔧 实现

| 位置 | 改动 |
|---|---|
| `cli/_registry.py` | audit/diagnose 改 exp CommandSpec；`_v()` 统一 layer=exp |
| `cli/main.py` | audit/diagnose/visualize/arch/design `hidden=True` |
| `cli/core/semantic/trace.py` | `trace overview` hidden |
| `capabilities` | 默认只列 core（23）；`--include-exp` 才含 12 个 exp |

## 📊 效果

```
默认 capabilities:
  total=35, core=23, exp=12（默认不列出）
  audit/diagnose/visualize/arch/design/overview 不在默认 help
--include-exp:
  audit/diagnose/visualize graph/.../trace overview 可见
```

## 🧪 测试

- 更新 `test_cli_layering.py` 的旧策略断言：
  - exp 默认隐藏
  - view 不再默认
  - audit/diagnose/visualize 不出现在默认 help
- 老路径显式调用仍可用（兼容）

## ✅ 验证

- 全量最终 **2635 passed / 0 failed**（P31+P32 合并计数；详见 iter_328）
- `docs/CLI_SURFACE.md` 重新生成
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 后续

- exp 命令**不再扩契约**，也不承诺 JSON 稳定性
- `stats.modules` / `class --member` 等已知功能缺口记录到 KNOWN_LIMITATIONS，按需单独修

## 🔗 相关

- 计划: [PLAN.md P31.1](../../../PLAN.md)
