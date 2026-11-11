# Iteration 477: P158.3 determinism

**状态**: ✅
**日期**: 2026-11-11

根因 id() 地址复用；最终用强引用保活 wrapper，三次构建一致。
