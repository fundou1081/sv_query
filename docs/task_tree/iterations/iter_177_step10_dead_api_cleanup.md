# Iteration 177: Step 10 — 死 API 清理 + adapter 专项收尾

**Metadata**:
- **Iteration #**: 177
- **Task Tree Level**: L1
- **Parent Task**: L1_adapter_split
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (移出 5 个零调用方法; adapter 专项 Step 0-10 全部闭环)

## 🎯 本次目标

方案 Step 10: 33 个"零外部调用"方法逐个定性 (死 API 移出 / 内部 helper 保留),
+ 文档收尾 (结构说明/文档漂移修正)。

## 🔬 实际结果

**定性方法 (AST + grep 双证)**:
- 75 个方法面 (含 wrapper 类):外部调用 53 / 仅内部 self 调用 10 / **双向零调用 12**
- 12 个候选中: `root`/`parser`/`trees` 是 **property**(外部按属性访问,保留);
  `__repr__`/`parent` 属 dunder 与 **wrapper 类 API**(保留,且 native_adapter 有互为
  兼容实现); `get_parent_module`/`_get_parent_module_safe` 同样是 **wrapper 类**
  方法 → 保留。
- 真正可移出的 **SemanticAdapter 级零调用方法 5 个**:
  `get_generate_instances` (92 行) / `iter_modules` / `visit_module` /
  `get_class_name` / `get_definition` → 移出到
  `legacy/dead_semantic_adapter_methods.py` (156 行, 含原位置注释与恢复步骤)。

**顺带发现的文档漂移 (已修)**:
- `docs/PYSLANG_SEMANTIC_USAGE.md` 记 `get_generate_instances` 被
  connection_extractor 使用 (L123/L147) — **实测该调用早已不存在**;同表
  `get_class_name` 标 UNUSED 与实测一致 → 两行标注为"已移出 (iter_177)"。
- `docs/EXTRACTION_COVERAGE.md` #46 引用该 API → 标注失效。
- `docs/ARCHITECTURE.md` 新增 "adapter 层结构" 节 (facade + 6 mixin 表 + legacy 去向)。

**过程中一次自伤 (如实记录)**: 首个搬迁脚本按"方法名列表"逐文件查找,
`get_parent_module` 实际是 wrapper 类方法 → 断言中断, 且此前已删掉
`get_generate_instances` 却未写归档文件 → 从 `git show HEAD:` 恢复该 92 行。
教训: 脚本化删除前必须先落归档文件 (写归档 → 再删源), 顺序不能反。

**验证 (Step 10 gate)**:
| gate | 结果 |
|---|---|
| unit + regression + truth | **2,243 passed** |
| cli + integration | **739 passed / 0 failed** |
| API 面冻结 (60 方法, 已记录收缩) | ✅ |
| `check_docs.py` | ✅ |

## 💡 关键发现 / 决策

- **"零调用"要分三类**: property (按属性访问) / 另一类的 API (wrapper) /
  真死方法 — 只按方法名扫全仓会把前三类误判成死代码。
- **删除顺序**: 先写 legacy 归档、再删 src (本次踩坑后固化); 归档文件同时承载
  "为什么当年这样写"的历史信息 (文档漂移发现也记在里面)。
- **API 收缩必须显式记录**: 冻结表删除 5 项时写明迭代号 + 双证方式 + 归档路径,
  使"API 变小"这件事在评审里可见, 而不是悄悄消失。
