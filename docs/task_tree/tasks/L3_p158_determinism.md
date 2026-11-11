# Task: P158.3 determinism

**状态**: ✅ 完成
**日期**: 2026-11-11

## 结果

id()-keyed genvar context 因 wrapper GC 复用而撞 key；改为持有 wrapper 引用，
同一输入三次构建 7621/12377 一致。源码位置方案已回退（generate 展开项共享位置）。
