# Iteration 326: JSON 契约扩展 batch 3（PLAN P30.1）

**Metadata**:
- **Iteration #**: 326
- **Task Tree Level**: L2（PLAN `P30.1`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "行，先继续扩充契约吧"）
- **Outcome**: ✅ 完成（6 个结构命令 + 错误形态；2631 passed）

## 🔧 新增契约

| 命令 | 关键字段 |
|---|---|
| `instances` | direct：count/module/instances[]；错误 path/hint |
| `hierarchy` | root_count/instance_count/tree[]（full_path/module_type/children/synthetic） |
| `ports` | module/count/by_direction/ports[]（port/id/direction/width/in/out_edges） |
| `params` | instance/module_type/count/parameters[]（name/value/is_overridden/is_local_param） |
| `connections` | resolved_as/instance/module_type/parent/port_count/ports[] |
| `class` | 无类名/类详情/`--member` 三种字段并集 |

新增 `direct_error` 通用错误形态：`ok/error/hint` + `path`/`target`/`resolved_as`。

## 🐛 契约面发现

1. 这组命令仍是 **direct output**，且错误形态与 envelope 不同；
   契约显式标 `envelope: "direct"`，避免 agent 假设统一 `errors[]`。
2. `ports MODULE` 的 MODULE 实际是**实例路径**（`top.u`），不是模块类型；
   文档/契约注明，测试用实例路径。
3. `connections` 只接受实例路径；错误含 `resolved_as`，已加入 direct_error。
4. `class` 三种模式字段不同；契约用并集 + 文档模式表，测试按模式校验。

## 🧪 测试

`test_json_contract.py` 15 → **22**：
instances（成功/错误）、hierarchy、ports、params、connections、class 三模式、错误形态。
用新 fixture `sim/tests/fixtures/json_contract/struct.sv`（child/top 实例+参数）。

全量：2624 → **2631 passed / 0 failed**。

## 📌 剩余契约面

`audit` / `diagnose` / `snapshot *` / `capabilities` 自身；这些输出嵌套深或带状态，
建议单独一批。

## 🔗 相关

- 计划: [PLAN.md P30.1](../../../PLAN.md)
- 文档: [JSON 契约](../../architecture/json_contract_2026-10-31.md)
