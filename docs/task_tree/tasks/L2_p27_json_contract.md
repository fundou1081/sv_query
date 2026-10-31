# L2 — P27 Agent JSON 契约

**Created**: 2026-10-31 GMT+8
**方豆**: "下一步继续 schema agent 契约"。

## 范围

- capabilities 暴露机器可读 `json_contract`
- envelope + trace fanin/fanout signal/node 字段类型/含义
- v1 版本策略（加法兼容；删/改类型/必填才升版本）
- null 语义、precision 枚举、条件路径结构
- 契约测试锁住“真实输出字段 == 契约字段”

## 完成记录（2026-10-31）

- P27.1 ✅ iter_323：`json_contract` 进 capabilities；`docs/architecture/json_contract_2026-10-31.md`
- P27.2 ✅ 4 个契约测试；全量 2613 passed；四检查 + gen_cli_surface 全绿
