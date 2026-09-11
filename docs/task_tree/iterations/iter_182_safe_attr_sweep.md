# Iteration 182: pyslang 属性读取 safe_attr 系统化收敛 (热路径 70 点)

**Metadata**:
- **Iteration #**: 182
- **Task Tree Level**: L1
- **Parent Task**: (iter_181 backlog 兑现)
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 热路径收敛 (70 点) + 工具落盘; 剩余点登记

## 🎯 本次目标

方豆 "继续" — 兑现 iter_181 登记的系统化修复: 对 pyslang **属性读取**
(`.name`/`.type`/`.body` 等 getter 级崩溃点) 做扫描 + `safe_attr` 包装。

## 🔬 实际结果

**扫描**: 新增 `tools/scan_pyslang_attrs.py` (AST 启发式: 接收者名含 pyslang
常见词 + 不在 try/except (UnicodeDecodeError|Exception) 内)。全仓 **126 处**
未受保护点, 分布: pipeline_viz 18 / exprs_drivers 18 / connection_extractor 16 /
_wrappers 9 / load_extractor 7 / graph_builder 7 / modules 6 /
module_instance_graph 5 / deadlock 5 / visualize 4 / driver_extractor 3 / viz_data_builder 3 ...

**热路径收敛 70 点** (抽取路径, 8 个文件) — 按属性给**语义安全默认值**:
| 属性 | 包装 | 默认值理由 |
|---|---|---|
| `.name` | `safe_str(safe_attr(x, "name", ""))` | 空串 = 无名 (原崩溃) |
| `.type` | `safe_attr(x, "type", None)` | None = 类型不可知 |
| `.body` | `safe_attr(x, "body", [])` | **空列表** — 保持 `for x in body` 可迭代 (不给 None) |

**过程中自伤 (如实记录)**: 导入自动补齐时把 core 层文件的深度写成 `..._safe`
(应为 `.._safe`) → 7 个模块 ImportError、3 个测试模块收集失败; 修正后
class truth + 混合语料全绿 (35 passed / 35 subtests)。

**验证**: unit+regression+truth / cli+integration 全量 gate (见 commit)。

**剩余 (未做, 已登记)**: 56 点 — pipeline_viz (可视化, 非抽取路径) /
applications/bus/deadlock / cli/visualize / viz_data_builder / 其他零星点。
用 `python3 tools/scan_pyslang_attrs.py` 可随时重扫。

## 💡 关键发现 / 决策

- **属性 getter 与 str() 是两类风险**: iter_141 收敛了 `str()` 转换点; 本次收敛
  getter 读取点。两者都要 `safe_attr`/`safe_str` 配合 (getter 先保护, 再转换)。
- **默认值要选"可继续执行"的那个**: `.body` 用 `[]` 而非 `None`, 否则
  `for x in body` 立刻 TypeError — 机械包装必须逐属性确认默认值语义。
- **工具化才能持续**: 126 点一次改完风险大 (语义逐个要判断), 落扫描器 +
  热路径先收敛 + 余量登记 = 可持续的推进方式。
