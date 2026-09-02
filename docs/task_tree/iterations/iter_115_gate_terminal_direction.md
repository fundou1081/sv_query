# Iteration 115: gate 原语端子方向改善 (G-1) — 多输出 buf / 双向 tran / UDP

**Metadata**:
- **Iteration #**: 115
- **Task Tree Level**: L2 (gate 遗留改进 G-1)
- **Parent Task**: [tasks/L2_gate_primitive_support.md](../tasks/L2_gate_primitive_support.md)
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

G-1: `_create_primitive_edges` 端子方向不再用 "conn[0]=输出" 位置约定 —
该约定对**多输出 buf/not** (会误把第二个输出当输入) 与**双向 tran** 是错的。

## 📊 当前状态 / 预期结果

- iter_112 实现: conn[0].left = 唯一输出, conn[1..] 全当输入
- 错例: `buf u_buf(o1, o2, a)` — o2 被当输入 (错边 o2→o1); `tran u_tr(t,a)` — a 不驱动 t

## 🔬 实际结果

### 探查 (pyslang 11 全门类实测)

| 门类 | primitiveType.ports | portConnections 形态 |
|---|---|---|
| NInput (and/xor, 输入数可变) | **模板** [Out,In], len≠conns | [Assign(输出), NamedValue(输入)...] |
| NOutput (buf/not, 输出数可变) | 模板 [Out,In], len≠conns | [Assign(输出), Assign(输出), NamedValue(输入)] (buf 多输出全 Assign) |
| Fixed (bufif1/notif/tran) | **逐端子**带 direction | bufif1 [Assign, NV, NV]; tran **两个都 Assign** |
| pulldown/supply0 | 1 端子 Out | [Assign] |
| UDP (UserDefined) | 逐端子有名字带方向 | [Assign, NV, NV] |

**关键规律**: slang 把**输出端子 (含双向 InOut) 统一包成 ExpressionKind.Assignment**
(.left=端子表达式), 输入是裸表达式 — 与方向模板一致, 全门类成立。
NInput/NOutput 是模板 (不可逐端子), Fixed/UDP 逐端子 (可读 direction 区分双向)。

### 修复 (driver_extractor._create_primitive_edges 端子解析重写)

- 逐端子门 (len(ports)==len(conns)): 用 ports[i].direction (Out/In/InOut)
- 模板门 (NInput/NOutput): 按 Assignment 包裹 = 输出
- 建模: 每个输入端子 → **每个**输出端子 DRIVER (多输出 buf: a→o1,o2);
  双向 InOut (tran 系) 组内**两两互驱** (pass-gate 同一通路 a⇄t);
  pulldown/supply0 无输入端子 → 不产生边 (常量驱动)

### 验证

- buf(o1,o2,a): o1←a 且 **o2←a** (修复前 o2 被当输入); not o3←b;
  bufif1(o4,b,a): o4←数据 b; tran(t,a): **t⇄a 互驱**; UDP my_and: y←a/b;
  supply0: 无输入边
- 既有 gate/CLA/cordic/genfor truth + unit 61 passed 零回归
- 新 unit +5 (TestTerminalDirectionModeling: buf 多输出 / bufif1 / tran / UDP /
  常量门), test_gate_primitive 8→13
- 全量回归结果见 commit

## 💡 关键发现 / 决策

1. **Assignment 包裹 = slang 的"输出端子"通用标记** (含 InOut) — 比位置约定/模板
   direction 都可靠; 模板门 (NInput/NOutput) ports 不是逐端子, 只能靠它。
2. **双向 tran**: 建模为 InOut 端子组内互驱 — 与 "谁驱动 a" 语义自洽 (pass-gate
   导通两侧同 net); 控制端 (tranif 的 In) 仍按输入端子。
3. bufif1 enable 是门输入端子 (参与门函数), 与 and 多输入同约定 → 不禁止
   enable→输出边 (初版测试过苛, 已修正)。

## 📌 状态

- ✅ 代码 + 测试 (unit +5) + 本文档; 全量回归见 commit
- G-2 (drive strength/delay 进图) / G-3 (UDP table 可视化) 仍 backlog
