# P183.5 DesignView / ASTFrontend — candidate decision (2026-11-18)

**状态**: 决策（ADR），P183.5 收口  
**范围**: 只评估；不启动大重构  
**结论**:

```text
DesignView  : 拒绝当前全量方案；保留 D9 的 per-context projection。
ASTFrontend : 采纳为边界候选，但只批准 Phase 0（inventory + degraded 计数）。
              完整 Protocol / 28~35 文件迁移不进入 P183.5。
```

---

## 1. 输入证据

| 证据 | 结果 |
|---|---|
| 全仓 `DesignView` / `ASTFrontend` 类定义 | 0（均未落地） |
| `pyslang` import 文件数 | **18**（`import pyslang` 12 + `from pyslang import` 6）；属性名散落数另计（`_expr_helpers.py` 单文件 22 个） |
| `tools/scan_pyslang_attrs.py` 当前报告 | **50 处启发式命中**（17 个文件）；逐点分类后真实 pyslang getter ≈10，约 40 处是 Python dataclass/包装器（噪声） |
| `safe_attr` 降级 | `except (UnicodeDecodeError, TypeError, Exception): return default` |
| DTO 审计（D9） | 6 份上下文投影；决定“每上下文一份 canonical projection” |
| 扫描器门禁 | 存在工具，但**不是** gate |

## 2. DesignView：拒绝全量

评审建议：

> 定义 `DesignView` Protocol（resolve_signal / drivers_of / edges_of / node_view），
> 把 NodeId/HierPath/EdgeKind 值对象化；新命令先走新 seam，旧命令按命令族迁移。

**决定：不采纳当前全量方案。**

理由：

1. **Ab-02 中「DTO 映射由 dataclass 单一函数生成」与 D9 冲突**：D9 已确认 6 份投影服务不同上下文，跨上下文统一 DTO = 公开 schema 变更；按命令族迁移的部分与 D9 兼容，不是冲突点；
2. **没有消费者**：当前没有第二查询前端/transport；D15 也决定不重写 Typer dispatch；
3. **成本是全栈**：会同时改图、DTO、CLI 查询族和契约，P183.5 明确“不启动大重构”；
4. **收益可延后**：新增字段/边类型的收益只有在新增命令或换前端时才兑现。

允许的后续（不在本项）：

- 若新增只读查询族，可先做一个**窄** `GraphView`，只服务新命令；
- 不为旧命令建立兼容期双实现。

## 3. ASTFrontend：采纳为边界候选，仅 Phase 0

评审建议：

> 定义 ASTFrontend Protocol（instances / expr_kind / symbol_of / drivers_in / diagnostics），
> 把全部 pyslang 属性名与 kind 字符串收进唯一 `pyslang_v11.py`；
> safe_attr 的 default 降级改为可计数 degraded；扫描器升级为 gate。

**决定：方向采纳，但 P183.5 只批准 Phase 0。**

Phase 0（后续独立项）：

1. 先把 `tools/scan_pyslang_attrs.py` 变成**按接收者类型分类的 inventory**：
   当前 50 个启发式命中中真实 pyslang getter ≈10、Python dataclass/包装器噪声 ≈40；
   棘轮只拦**新增真实 pyslang 读取**（需类型判定或人工白名单），不把 50 当基线；
2. `safe_attr` 的宽 `Exception` 降级改为**可观察 degraded**，但必须：
   ① 返回类型/返回值不变（仍是 caller 的 default，现有 176 个调用点和
   `test_safe.py:97-101` 断言不改）；
   ② 降级信号走**注入的 collector / per-request context**，不用模块级全局计数器
   （避免重新引入进程全局态）；
   ③ 补 fixture 测试；
3. 输出一份 pyslang 属性名/`kind` 字符串清单，作为未来 `pyslang_v11.py` 的输入；
4. 不迁移 28~35 个文件，不建 Protocol，不启动兼容层。

完整 ASTFrontend Protocol 的触发条件（P184 完成后才可评估）：

- pyslang v12 升级；
- 需要第二 AST 前端；
- inventory/gate 发现真实工程中的静默缺边；
- 有明确的新语义提取需求，单文件无法承载。

## 4. 可观察后果

| 场景 | 现状/决定 |
|---|---|
| 现有 CLI 输出 | 不变；P183.5 无 `src/` 改动 |
| 新查询命令 | 仍使用现有 graph/DTO；窄 GraphView 未实现 |
| pyslang 升级 | 仍可能静默 default；Phase 0 后才能计数 |
| 扫描器 | 目前 50 处；不是 gate |
| `safe_attr` | 仍吞 `Exception`；Phase 0 修 |

## 5. 开放项

| 项 | 处置 |
|---|---|
| ASTFrontend Phase 0（inventory gate + degraded 可观察） | 已登记为 **P184**（inventory 分类棘轮 + `safe_attr` 可观察降级），不塞进 P183.5 |
| pyslang 属性名/kind 清单 | Phase 0 产出 |
| 窄 GraphView | 等新查询命令，不预先实现 |
| D9 投影决策 | 保持不变；DesignView 不再全量合并 |

## 6. 证据

- [D9 DTO 审计](dto_mapping_audit_2026-11-17.md)
- [D15 Session seam 决策](p1834_session_seam_decision_2026-11-17.md)
- [scan_pyslang_attrs.py](../../tools/scan_pyslang_attrs.py)
- [trace/_safe.py](../../src/sv_query/trace/_safe.py)
- 归档评审：2026-11-16 的 implementation/abstraction review（§DesignView / §ASTFrontend）
