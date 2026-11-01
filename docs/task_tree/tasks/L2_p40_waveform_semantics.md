# L2 — P40 波形值语义

**Created**: 2026-11-01 GMT+8
**方豆**: "继续"（波形联调 type/stage）。

## P40.1 type/enum/struct/array（✅ iter_338）

- profile.type：known/name/canonical；
- enum_values；packed_members(offset)；
- is_array/unpacked_array/array_element；
- module Port/Variable 解析；class 保持 unknown。

## P40.2 sequential stage / 时间语义（✅ iter_339）

- 从 sequential 链/路径证据推导 register stage；
- 不能算时保持 null + stage_known=false；
- 与 clock edge 对齐。

## 验收

- 类型/阶段结论可追溯；不能算不猜；
- 契约/测试；全量门禁 0 failed。
