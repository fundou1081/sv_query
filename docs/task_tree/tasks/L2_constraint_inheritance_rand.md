# Task: constraint 继承链 + rand 标记（P64）

**状态**: 进行中
**背景**: P63 暴露 constraint/covergroup CLI 后，继续补 SV 语义：
- 继承成员被约束变量 placeholder 建成 SIGNAL，导致继承约束不可查；
- class member 没有 rand/randc/type 元数据；
- constraint block 没有 defined_in/inherited。

## 交付

- 继承属性升级 CLASS_PROPERTY + 继承 rand/type；
- constraint block 记录 `defined_in` / `inherited`；
- `class --relations` 成员 is_rand/rand_mode/type；
- `trace constraints` 返回 rand_vars/defined_in/inherited；
- 测试继承约束链 + rand 标记。
