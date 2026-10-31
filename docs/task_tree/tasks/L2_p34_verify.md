# L2 — P34 双向一致性与 claim verification

**Created**: 2026-10-31 GMT+8
**方豆**: "按这个顺序逐个来做吧"。

## 范围

- `verify consistency`：reciprocity / bit mapping / connection
- `verify claim`：driver / path / connection / bit
- 三态：verified / contradicted / unknown
- JSON 契约 + 测试 + 文档

## 验收

- 不把无法证明判成 false；unknown 显式；
- 抽样/依赖限制在输出中标注；
- 全量门禁 0 failed。
