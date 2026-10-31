# L2 — P29 JSON 契约扩展（locate/evidence/controlflow）

**Created**: 2026-10-31 GMT+8
**方豆**: "继续扩契约面"。

## 本批范围

- `graph edges`
- `search`（direct output，无 envelope）
- `stats`
- `trace evidence`（envelope + 可选 top-level evidence）
- `controlflow analyze`
- `controlflow list-conditioned`

## 验收

- capabilities.json_contract 新增 sections + commands 映射
- 契约测试用真实 JSON 校验字段集合
- 文档更新；全量门禁 0 failed

## 完成记录（2026-10-31）

- P29.1 ✅ iter_325：6 命令契约（graph edges/search/stats/evidence/controlflow analyze+list）
- P29.2 ✅ 契约测试 9 → 15；全量 2624 passed；四检查 + gen_cli_surface 全绿
