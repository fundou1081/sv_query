# Iteration 129: inout 跨模块连接 + interface 成员级桥 (候选 1/3 建模)

**Metadata**:
- **Iteration #**: 129
- **Task Tree Level**: L2 (signal graph 准确性审计 → 待验证候选建模)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-04 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

方豆 "继续" + 拍板 (选 1 inout + 4 interface): 修 iter_128 登记的两个建模缺口 —
① inout 跨模块连接缺失 (connection_extractor 无 inout 分支, fanin 空答);
② interface 成员级连接无桥 (bf.addr ← writer.b.addr 断) + fanin 假驱动。

## 🔬 实际结果

### 修复 1: inout 跨模块连接 (候选1)

- **诊断**: connection_extractor 端口循环只有 input/output 分支
  (line ~515/551), inout 端口 kind=PORT_INOUT (line ~466) 但**连接边完全没建**
  → 顶层 inout (top.sda) 与实例端口 (u_io.sda) 无任何边, fanin 空答。
- **建模决策**: inout = 父信号与实例端口**同一根线** (物理连接, 无方向归属 —
  谁驱动看上下文: 外部拉 or 实例内部三态驱动)。建 **output 式单向 CONNECTION**
  (inst_port → parent_signal), fanin(父线) 穿透到实例端口, 再追实例内部驱动
  (三态 assign 的 DRIVER/BRANCH 链)。不建 input 式 (parent → inst_port) —
  避免 fanin 把外部线当实例端口驱动源; i2c 开漏双向多驱动归属 = 更深语义,
  不在本轮强加。
- **fanin 穿透**: 主循环 CONNECTION 分支对 PORT_INOUT src 无匹配 → 落到
  "其他边类型递归追溯" fallthrough, 天然可追 (无需改 fanin)。
- **证据**: fanin(top.sda) `[] → ['top.data','top.en','top.u_io.data']`
  (实例内部三态驱动链)。unit 锁定 test_tri_state_inout_no_connection (仅断言
  input 式 parent→inst 无边) 不受影响。

### 修复 2: interface 成员级桥 (候选3)

- **诊断**: ① 整体 CONNECTION (top.bf→u_w.b) 有, 但成员级 (bf.addr ↔
  u_w.b.addr) 无桥 — writer 内 assign b.addr=a 已由 driver_extractor 建
  (u_w.a→u_w.b.addr DRIVER), 但 interface 实例成员 bf.addr 追不到;
  ② fanin(bf.addr) 含 top.clk 假驱动 (A2 提升把 INSTANTIATED_MODULE 实例节点
  当父总线提升, 收进其 PORT_IN clk)。
- **建模决策**: 
  - fanin A2 提升目标限 data 类节点 {SIGNAL, PORT_OUT, PORT_IN, REG} —
    interface 成员 (bf.addr) 的 BIT_SELECT 父是模块实例节点 (top.bf,
    INSTANTIATED_MODULE), 不是父总线 → 禁提升, 假驱动消除。
  - 成员桥 = connection_extractor 收集 interface 端口连接 (识别
    InterfacePortSymbol.interfaceDef + 成员列表, ExtractorResult.interface_links)
    + graph_builder 后处理 _bridge_interface_member_signals 建**单向桥**:
    * 实例内部驱动该成员 (writer: u_w.b.addr 有 incoming DRIVER) → 桥
      实例成员 → interface 实例成员 (u_w.b.addr → bf.addr)
    * 实例只读 (slave: 无 incoming DRIVER) → 桥 interface 实例成员 → 实例成员
      (bf.addr → u_s.b.addr)
    * 双向边会让 fanin(端口成员) 把无驱动的 interface 线当假源 (实测噪声);
      单向"谁驱动谁"与普通端口建模一致。
- **证据**: writer 场景 fanin(bf.addr) `[] → [u_w.b.addr]` (粒度层),
  fanin(u_w.b.addr) → [u_w.a, top.a] (到底); slave 读场景 fanin(u_s.b.addr) →
  [bf.addr] (跨回 interface 线); 组合链 o→u_s.o→u_s.b.addr→bf.addr→
  u_w.b.addr→a 逐层通。

### 验证

- 新增 unit 7 (TestInoutCrossModule ×3 + TestInterfaceMemberBridge ×4):
  inout 连接边/穿透/kind 回归; interface writer 桥/读方桥方向/无假驱动
- 全量回归: **2928 passed / 0 failed / 0 skipped** (2921 + 7 新)

## 💡 关键发现 / 决策

1. **inout/interface = 同一根线, 单向 CONNECTION 建模**: 父↔实例的物理同线,
   用 output 式单向边让 fanin 单向穿透。inout 双驱动 (i2c 开漏) 与 interface
   双向共享 (master 写 slave 读) 的"多驱动归属"仍待专项 — 当前单向链逐层可追,
   方向由实际驱动侧确定。
2. **fanin A2 提升目标必须限 data 类节点**: 提升语义是"位→父总线", 父必须是
   SIGNAL/PORT/REG (数据容器); 模块实例节点 (interface 实例/INSTANTIATED_MODULE)
   不是总线, 提升会把整个实例的 PORT_IN (clk 等) 当源 — 假驱动根因。
3. **成员桥方向 = 实例内部是否驱动成员** (incoming DRIVER 检测): writer 型
   (assign b.addr=a) vs slave 型 (assign o=b.addr 只读) 方向相反; 双向桥产生
   假源噪声。检测放 graph_builder 后处理 (driver 边就绪后) 是正确时机。
4. InterfacePortSymbol 有 interfaceDef (定义名) + get_interface_members
   (成员列表), module_ports 方向对 interface 是 fallback 'input' (误导) —
   需独立收集, 不能走普通方向分支。

## 📌 状态

- ✅ inout 跨模块连接 + interface 成员级桥 + fanin 假驱动全修; unit +7;
  全量 2928 passed / 0 failed
- 审计候选 5 项全闭环; backlog: i2c 开漏多驱动归属 (inout 双向) / interface
  双向共享多驱动语义 (master+slave 同线多写) 待专项, A2 位对位折算, G-2/G-3
