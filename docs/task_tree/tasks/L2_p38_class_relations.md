# L2 — P38 class 关系查询

**Created**: 2026-10-31 GMT+8
**方豆**: "补 class 关系"。

## 范围

- `class <name> --relations`
- extends/ancestors/subclasses/descendants
- 类型级成员/实例/成员实例
- 约束边
- 方法定义 + 方法体调用
- 不展开方法内部细节

## 验收

- 关系是结构事实；空关系显式；
- 未知 class 显式错误；
- JSON 契约 + 测试；全量门禁 0 failed。

## 完成记录（2026-10-31）

- P38.1/P38.2 ✅ iter_334：relations 命令/契约/4 测试
- 全量 2672 passed
