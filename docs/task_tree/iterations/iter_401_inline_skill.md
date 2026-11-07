# Iteration 401: inline skill prompt（P97）

**状态**: ✅（负结果）
**日期**: 2026-11-07

## 设计

- 3 cells，DeepSeek，seed1；
- prompt vs 把 SKILL.md body 直接追加到 prompt；
- 相同 A+D snapshot。

## 结果

- exact 3/3 both；
- mean prompt 78.3s vs inline 111.8s；
- AXI/Pico 变慢，SERV 变快；
- 工具调用无一致下降。

## 结论

inline skill 没有稳定收益；不扩 24，不默认开启。
