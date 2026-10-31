# L2 — P30 JSON 契约扩展（结构/元数据）

**Created**: 2026-10-31 GMT+8
**方豆**: "行，先继续扩充契约吧"。

## 本批范围

- `instances`（列表/详情 direct output + 错误形态）
- `hierarchy`（树节点）
- `ports`（端口列表）
- `params`（参数列表）
- `connections`（实例端口连接）
- `class`（无名字/类详情/成员模式）

## 验收

- capabilities.json_contract 新增 sections + commands 映射
- 契约测试覆盖成功形态；错误形态字段文档化
- 文档更新；全量门禁 0 failed


## 完成记录（2026-10-31）

- P30.1 ✅ iter_326：6 个结构命令契约 + direct_error
- P30.2 ✅ 契约测试 15→22；全量 2631 passed；四检查 + gen_cli_surface 全绿
