# Iteration 137: A2 位对位折算 — 跨实例 bus 桥位索引贯通 (L3 反例 #3)

**Metadata**:
- **Iteration #**: 137
- **Task Tree Level**: L2 (准确性审计 → A2 后续项 / Accuracy Claim L3 反例 #3)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (全量回归见 commit)

## 🎯 本次目标

方豆 "先做 A" = A2 位对位折算: 子模块输出总线直连顶层位时,
fanin(top.y[3]) 从 bus 粒度 (u_sub.y) 贯通到位级 (sub 内部 y[3] 逻辑的
驱动源 a[3]/b[3])。audit A2 后续项 / Accuracy Claim L3 反例 #3。

## 🔬 探索结论 (方案设计前)

### 现状 (iter_126 锁定, BUSFIX 全 bus 直通)

- BUSFIX (`sub assign y=a` bus 直通): 图内**无位节点**; fanin(top.y[3])
  → 提升 bus → {top.u_sub.y} (bus 粒度) — iter_126 truth 锁此
- 位节点存在性驱动: driver 层按需建位节点 (sub 内部位级 assign →
  u_sub.y[3]/u_sub.a[3] 存在; bus 直通 → 不存在)

### 真实场景 A (sub 内部位级 assign y[3]=a[3]&b[3])

- 位节点全在 (top.y[3], u_sub.y[3], u_sub.a[3], u_sub.b[3])
- 位级 DRIVER 在 (u_sub.a[3]→u_sub.y[3] continuous)
- 顶层位 top.y[3] 只有 BIT_SELECT **出边** (→ top.y), 无 incoming 驱动
- bus CONNECTION (u_sub.y→top.y, top.a→u_sub.a) 在位级**无桥**
- 现状: fanin(top.y[3]) = {u_sub.y} (bus 粒度停)
- 一致性目标: fanin(top.u_sub.y[3]) = {a[3], b[3]} —
  顶层位查询应跨桥后与 sub 内位查询同语义

### 方案对比

| 方案 | 做法 | 结果 |
|---|---|---|
| ① 图位展开 (选) | graph_builder 后处理 `_expand_bus_conn_bit_bridges`: 同宽同构 bus↔bus CONNECTION (两端无 [N]、width 相等), 仅当两侧位节点都存在时补位 CONNECTION 边; BUSFIX (无位节点) 自动保持 bus 粒度 (不造假节点, AGENTS.md §2) | ✅ 采用 |
| ② 查询索引传播 | _trace_drivers_recursive 带位索引上下文跨 bus | 弃 (深改 900 行递归, 特判交互风险高) |

## 🔬 实际结果

### 修复 (2 处)

1. **graph_builder._expand_bus_conn_bit_bridges** (build() 链,
   `_filter_by_target` 之后 — 只遍历保留节点, 不建悬空边): 对 bus↔bus
   CONNECTION (src/dst 无 [N], width 相等且 >1 位), 枚举位 i (min/max
   width 范围), 两侧位节点都存在 → 补位边 (u_sub.y[i]→top.y[i];
   输入侧 top.a[i]→u_sub.a[i] 同规则)。切片连接 (.y(y[7:4]) 偏移映射)
   不在本版 (audit 后续项)。
2. **query/signal.py CONNECTION-SIGNAL 分支**: src 位节点的 bus 父
   (剥 [N] 查节点) kind==PORT_OUT → **位桥出口** — 不 append (桥中间
   节点), 递归其内部驱动 (与直接查询 u_sub.y[i] 同语义)。判据不依赖
   parent 属性 (driver 建的位节点 parent 常为 None)。普通中间线网位
   (bus 父非 PORT_OUT) 保持 append+stop (iter_132 粒度停靠不变)。

### 证据 (场景 A 位级 sub)

- fanin(top.y[3]) = {top.a[3], top.b[3], top.u_sub.a[3], top.u_sub.b[3]}
  == **fanin(top.u_sub.y[3]) 完全一致** (顶层位查询贯通到 sub 内部 +
  输入侧跨桥到顶层输入位); 不含 u_sub.y[3] (桥中间节点) / u_sub.y (bus)
- fanin(top.y[2]) 同样按位 (不串位)
- BUSFIX (纯 bus 直通, 无位节点): {u_sub.y} 保持 — iter_126 truth 不变

### 验证

- unit +3 (TestA2BitBridge: 顶层==sub 内一致 / 逐位不串 / bus 直通保持
  bus 粒度) — 32 passed (A1/A2/A3 全文件)
- 受影响子集 91 passed (cordic/cla/genfor/cross_module/bit_select/query/
  case27 等)
- 全量主回归: 见 commit

## 💡 关键发现 / 决策

1. **位桥只在"两侧位节点都存在"时建** = 无假节点原则的位级应用:
   图按 RTL 真实位选建模 (driver/_create_hierarchical_bit_nodes), 位桥
   只是把已存在的物理连接 (bus 直连) 补齐到位上; bus 直通无位逻辑的
   设计保持 bus 粒度 (诚实: 图里没有位级信息, 不臆造)。
2. **位桥出口 = 实例输出端口的位**: 查询层把桥出口当"查询对象"递归
   (不 append), 与 fanin(该位自身) 语义严格一致 — 顶层位查询 == 模块内
   位查询是位对位的一致性判据。
3. 位节点 parent 属性不可靠 (driver 建的为 None) → 判据用 bus 父 id
   推断 (剥 [N] 查 kind)。
4. 切片连接 (位偏移映射) + 非零 base 端口是下一档 (audit 后续项登记)。

## 📌 状态

- ✅ 位桥边生成 + 查询位桥出口递归 (场景 A 顶层==sub 内一致)
- ✅ BUSFIX bus 粒度保持 (iter_126 truth 不变); unit +3
- ✅ 受影响子集 91 passed; 全量回归见 commit
- 🗒️ audit L3 反例 #3 需更新 (A2 位对位: 同构直连已通 / 切片偏移留档)
