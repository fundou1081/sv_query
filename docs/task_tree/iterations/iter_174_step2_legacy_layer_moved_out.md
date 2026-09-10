# Iteration 174: Step 0-2 — API 安全网 + legacy 等价矩阵 + base.py 移出

**Metadata**:
- **Iteration #**: 174
- **Task Tree Level**: L1
- **Parent Task**: L1_adapter_split
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (Step 0/1/2 完成; -2,341 行 src)

## 🎯 本次目标

方豆: "用移出代替删除，这样可以恢复。去做吧" — 按方案执行 Step 0 (API 冻结) /
Step 1 (legacy 等价矩阵) / Step 2 (base.py 移出)。

## 🔬 实际结果

**Step 0 — API 面冻结测试** (`sim/tests/unit/test_semantic_adapter_api_surface.py`):
冻结 `SemanticAdapter` 65 方法名 + `inspect.signature` + 3 property + facade smoke
(构造/`root`/`trees`/`get_modules`)。4 测试绿 — 后续每步的机械安全网。

**Step 1 — legacy 等价矩阵 (逐文件实测, 非按名猜)**:
- `test_constraint_deep_parsing` / `test_constraint_derivative` / `test_class_method`:
  主断言其实**已走 UnifiedTracer (semantic) 路径**, 只在 helper 里借 legacy
  `get_classes()` / `get_class_members()` → 改用 `SemanticAdapter` 即可
  (3 处 helper + 1 处 inline); 另需 2 处 shape 适配: `c.name.value` (syntax token)
  → `str(c.name)`; `cls.items` 里的 `ConstraintDeclaration` (syntax kind)
  → semantic 成员 `ConstraintBlock`; class 方法枚举 helper 由 syntax 层
  (`ClassMethodDeclaration|Prototype`) 重写为 semantic `Subroutine` 成员名。
- `test_interface`: 其 legacy `_get_adapter()` helper **从未被调用** (真调用是
  `tracer._get_adapter()` = semantic) → 直接删死 helper。
- `test_safe::test_base_pyslang_adapter_clean_name_uses_canonical`: legacy 专属,
  语义已由 `test_semantic_adapter_clean_name_uses_canonical` 覆盖 → 退役。
- `test_pyslang_v11_aliases::test_base` → 改写为"legacy 层已移出"断言。
→ 结论: **零覆盖损失**, 无需为删层补新测试 (矩阵逐条核对)。

**Step 2 — 移出 (不删)**:
- `git mv src/trace/core/base.py legacy/base_pyslang_adapter.py` (2,341 行) +
  `legacy/README.md` 说明原路径/原因/恢复步骤。
- 8 处 src 类型注解 `PyslangAdapter` → `SemanticAdapter` (7 文件 + 1 docstring);
  `core/__init__.py` 去掉 legacy 导出。
- 守卫测试扩展 (`test_no_pyslang_adapter_legacy.py`): ① `core/base.py` 不得复活
  ② src/ 不得 import legacy base 层。
- 打包无影响 (packages.find where=["src"] → 根 `legacy/` 不进包)。

**验证 (Step 2 gate 全过)**:
| gate | 结果 |
|---|---|
| unit + regression | **2,064 passed** (基线 2,059 + 5 净增: API 冻结 4 + 守卫 2 − 退役 1) |
| cli + integration | **739 passed / 0 failed** |
| truth 金标准 (19 文件) | **164 passed** |
| API 面冻结 | ✅ 完全一致 (零改名/零签名变化) |
| `tools/check_docs.py` | ✅ 4 项全 0 |

## 💡 关键发现 / 决策

- **移出优于删除** (方豆): legacy 层保留在 `legacy/` + git 历史双保险; 恢复步骤
  写在 `legacy/README.md` (含 8 处注解改回指引)。
- **"legacy 测试"未必测 legacy**: 4 个文件里多数断言已在 semantic 路径 —
  等价矩阵逐条核对后, 只有 3 个 helper + 1 个 helper 真正需要移植, 而不是
  1,546 行整体搬迁。若按文件名猜测, 会白做大量迁移。
- **安全网先行见效**: API 冻结测试让"搬家"与"改行为"在机制上可区分 —
  这是后续 Step 3~9 快速推进的前提。
