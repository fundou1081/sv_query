# L2 — P39 波形路径联调

**Created**: 2026-11-01 GMT+8
**方豆**: "波形工具需要提供完整 rtl hier path，围绕这个展开"。

## P39.1 waveform path lookup（✅ iter_335）

- 严格完整路径映射；$root/bit_parent/not_found；port/internal aliases
- 批量 paths file；契约/测试

## P39.2 profile 增强（待做）

- type/enum/array/struct/bit offset
- clock posedge/negedge、reset active_low/async
- sequential stage（能算才算）

## P39.3 联调测试（待做）

- 模拟 waveform manifest 输入 → canonical 映射
- interface/generate/escaped 别名

## 完成记录（2026-11-01）

- P39.1 ✅ iter_335：trace lookup 严格完整路径；3 测试 + 1 契约
- 全量 2676 passed；P39.2/39.3 待做
