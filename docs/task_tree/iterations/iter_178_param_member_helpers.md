# Iteration 178: 参数化成员解析收尾 (A 路线最后一项)

**Metadata**:
- **Iteration #**: 178
- **Task Tree Level**: L1
- **Parent Task**: L1_class_parameterized_support (收尾) / L1_adapter_split 后续
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (2 处 `list(cls)` 统一 + 1 处嵌套特化缺口; 2245 + 739 全绿)

## 🎯 本次目标

A 路线最后一项 (iter_170 登记的残留): `function_extractor` 中两处 `list(cls)`
对参数化 class (GenericClassDef, 不可迭代) 会静默 `TypeError → False/None`。

## 🔬 实际结果

**先写测试证明缺口真实 (再修)** — 两个参数化场景测试在修复前**确实失败**:
1. `test_this_member_rhs` (E5 形态): 参数化类内 `data = tmp`, tmp 由同实例
   helper 驱动 → `_is_class_member` 判 tmp 是否成员 → 旧 `list(cls)` 失败 → 链断
2. `test_inner_class_member_chain` (E13 形态): 参数化类成员 `i` 是另一个参数化类
   → `_member_class_name` 解析成员类型 → 旧代码失败 → `i.set(v)` 不展开

**修复 1 — 统一成员入口**: 新增 `_class_members_by_name(class_name, h=...)`
(走 `adapter.get_class_members`,参数化 class 用特化成员),`_is_class_member` /
`_member_class_name` 改为复用之 — 消除文件内第三份"找 class + 遍历成员"重复。

**修复 2 — 嵌套特化缺口 (修 1 之后才暴露)**: `inner#(W)` 作为 `packet#(W)` 的成员
时,`_scan_class_specializations` 只收录"变量/属性的类型"这一层 → 内层特化未进入
映射 → `inner.val` 节点根本不建。修: 扫描器在 `record_spec` 内**下钻特化成员里
的 class 类型成员** (深度由 `name in out` 去重天然收敛)。两处扫描器同步修:
`core/semantic/classes.py` (adapter 侧, 随 mixin 搬迁) + `covergroup_extractor.py`。

**验证**:
| gate | 结果 |
|---|---|
| unit + regression + truth | **2,245 passed** (+2 新参数化成员链测试) |
| cli + integration | **739 passed / 0 failed** |
| `check_docs.py` | ✅ |

## 💡 关键发现 / 决策

- **"先写会失败的测试"价值最大**: 两处 `list(cls)` 是我在 iter_170 就登记但未修的
  残留; 本次先用参数化场景把失败固定下来 (而非直接改代码), 修完立刻有"缺口真实
  且已闭环"的证据。
- **修一处暴露下一处**: 成员解析修好后, 嵌套参数化 class 的特化收录缺口才浮现
  (图里 `inner.val` 缺失) — 说明参数化支持是**链式**的, 单点修复看不出问题,
  必须端到端断言 (fanin 贯通) 才能验证。
- **扫描器双份仍是隐患**: adapter 侧与 covergroup_extractor 侧各有一份
  `_scan_class_specializations` (extractor 为独立编译场景不依赖 adapter 而保留)。
  本次同步修两处; 建议后续抽成共享纯函数 (已记录在 covergroup 规划文档的边界节)。
