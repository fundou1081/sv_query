# TODO — sv_query

> 更新: 2026-07-29

---

## 当前状态

- **2958 测试**, 2876 passed (97.1%)
- V6.7: VizData 统一可视化层已完成
- V6.6: SignalSource 改名 + DriverInfo 重构完成
- V6.5: 位精确 binary decomposition 完成

---

## 近期 (P0-P1)

### V6.8: Visitor 体系清理
- 删除 `[NOT TESTED]` handler (~40 个在 operator_visitor)
- 删除 `_dispatch_enabled` 双轨开关和旧 fallback
- 风险: 🔴 HIGH (2958 回归)

### V6.9: 旧渲染器清理
- 删除 `signal_graph_viewer.render_html/render_mermaid`
- 把所有内部 helper 迁移到 VizData
- 删除 `_emit_split_by_module`

### V7.0: pyslang Native API 重构
- `get_module_instances()` 用 native API (4.4x speedup)
- 重写 `module_instance_graph.py` 用 `inst.portConnections`
- 参考 MEMORY.md 中的分析

---

## 中期 (P2)

- DriverInfo 和 SignalSource 进一步整合
- chain/module/arch → VizData 迁移
- 动态 HTML 可视化 (vis.js / cytoscape.js)
- 删除 Class/Constraint 未使用的 NodeKind 和 EdgeKind

---

## 已完成

- ✅ V6.5: DriverSource 位精确结构化
- ✅ V6.6: SignalSource + DriverInfo 重构
- ✅ V6.6: NodeKind/EdgeKind 命名空间分区
- ✅ V6.6: 可视化清理 (legend from core, deprecated load_dot)
- ✅ V6.7: VizData 统一可视化层
- ✅ V6.7: graph/dataflow/pipeline 迁移到 VizData
