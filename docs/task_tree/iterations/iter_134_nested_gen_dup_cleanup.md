# Iteration 134: 嵌套 generate 深层路径重复段假节点清理

**Metadata**:
- **Iteration #**: 134
- **Task Tree Level**: L2 (准确性审计 → generate 假节点清理)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

修 iter_133 复验登记的 backlog: 嵌套 generate 深层重复段假节点 (aes 型
`ROUND[1].U_ROUND.ROUND[1].U_SUB` ×351, 7.3% 图污染)。

## 🔬 实际结果

### 根因

3+ 层 generate 嵌套 (wrapper→aes_top.ROUND[i]→Round→U_SUB) 时, 内层实例
(Round 内 U_SUB) 的 hp = `aes_top.ROUND[1].U_ROUND.U_SUB` — 含**祖先**
generate 段 ROUND[1] (Round 被 ROUND[i] 实例化的展开路径)。U_SUB 的直接
宿主是 Round 模块 (无 generate), 但 connection_extractor
`_get_generate_block_name` 用 hp 正则 `\.name[\d+]` 取**第一个** [N] 段 →
误把祖先 ROUND[1] 当 U_SUB 的 gen_block → get_path 拼 `U_ROUND.ROUND[1].
U_SUB` 假节点。

iter_117 去重只查 parent_mod 结尾 [N] (单层场景), 未覆盖"祖先 generate
段在中间实例后面"的深层嵌套 (parent_mod=Round 无 [N] → 漏网)。

### 修复 (connection_extractor.py `_get_generate_block_name`)

gen_block 只取 hp 中**紧邻实例名** (hp 最后一段) 的前一段 — 该段形如
`name[N]` 才是实例的**直接宿主** generate (generate entry 内实例,
`ROUND[0].U_ROUND` ✓); 前段是普通实例名/模块路径 (`U_ROUND.U_SUB` —
前段 U_ROUND) → 无直接宿主 generate → None。不再从 hp 任意位置取祖先段。

### 连带修复 1: fanin wrapper cross 守卫的 get_edge 缺陷

iter_132 加的 wrapper cross 守卫 (src 无内部驱动才跨) 用 `get_edge(p, src)`
只取第一条边 — `u_leaf.y→u_mid.y` 同时有 CONNECTION + wrapper_passthrough
DRIVER 时 get_edge 返 CONNECTION → 误判无内部驱动 → 嵌套 generate fixture
(G[i]→mid→leaf) 仍跨 entry。改 `get_edges(p, src)` 遍历全部边。

### 连带修复 2: PORT_OUT via CONNECTION 有内部驱动时丢内部 deep (回归)

get_edges 全查让 wrapper_passthrough 被正确识别为内部驱动 → 拦 wrapper
cross → 但旧逻辑有内部驱动时不 cross 也不追本端口 → 顶层 CONNECTION
(s_axi_a_awready → a_if.s_axi_awready) 追到 PORT_OUT 就断, 丢
a_if.axi_ram_wr_if_inst 内部 reg (test_deep_hierarchy 回归暴露)。

修: PORT_OUT 分支在有 **wrapper_passthrough** 驱动时, 显式递归其源
(a_if.axi_ram_wr_if_inst.s_axi_awready → reg) 追内部 deep; continuous/
nonblocking (真模块 assign, leaf 型) 粒度停不变 (iter_132 语义)。
mid 嵌套 fixture 验证: y[2] fanin 含 G[2].u_mid.y + u_leaf.a (递归到位),
无跨 entry。

### 证据

- aes (target wrapper): 假节点 279→**0**; 无 target: 1116→**0**; U_SUB 正确
  挂 U_ROUND 下 (module=SubBytes), fanin 正常
- cordic: 假节点 105→0 (`U.genblk1[i].x_shifter` 清除 — 旧 truth 锁假形态
  已更新为真 `U.x_shifter`)
- 嵌套 fixture (G[i]→mid→leaf): fanin(y[2]) 含 G[2].u_mid.y + 内部 leaf 链
  (wrapper_passthrough 自递归), 无跨 entry; 逐层可追到 a[2]
- verilog-axi wrapper: test_deep_hierarchy 保持 (a_if wrapper_passthrough
  递归到 reg; 非 cross b_if 路径)

### 验证

- 更新 cordic truth (test_rotator_internal_scope 假路径→真路径 + 无假节点断言)
- 新 unit 3 (TestNestedGeneratePathCleanup: 无重复段 / leaf 路径正确 /
  mid fanin 无跨 entry)
- 全量主回归: 见 commit (预计 2934+ 无新增失败)

## 💡 关键发现

1. **gen_block 语义 = 直接宿主 generate, 非 hp 任意 [N] 段**: hp 含祖先
   generate 是嵌套实例化展开的合法形态; 取祖先段拼路径 = 假节点根因。
   判据: 紧邻实例名前一段形如 name[N]。
2. **get_edge 只返第一条是查询层反复踩的坑**: (src,dst) 多边 (CONNECTION +
   DRIVER wrapper_passthrough) 时单取会误判 — 检查"是否有某类边"必须
   get_edges 全查 (iter_132 守卫同病, 本迭代修)。
3. iter_117 去重是单层特例; 通用修复在 gen_block 判定处 (源头), 一次覆盖
   所有深度嵌套。

## 📌 状态

- ✅ 嵌套 generate 假节点清零 (aes 279/1116→0, cordic 105→0)
- ✅ wrapper cross 守卫 get_edges 修复 (嵌套 fixture 跨 entry 消除)
- unit +3 + cordic truth 更新; 全量回归见 commit
