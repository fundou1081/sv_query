# L2 门级原语 (Gate Primitive) 提取支持 — leaf cell 建模

> **创建**: 2026-09-03 GMT+8
> **背景**: 工业算法模块摸底扫描 (openrtl) 在 KoggeStone-BrentKung (纯门级加法器) 发现
> **门级原语实例 (and/xor/not/...) 完全未建模**: xor16 的 S[0..15] 全无 DRIVER
> ("谁驱动 S[0]" 无答案), pg16 的 and/xor 实例在 ConnectionExtractor 里触发无限递归
> (depth>20 截断成 `top.and0.and0.and0...` 21 层假节点)。
> **父任务**: openrtl 工业算法摸底 → 缺口修复系列 (CORDIC iter_109~111 之后)
> **方豆拍板**: 取消提问对话框 → 按推荐 **方案 A** (建模原语为 leaf cell) 执行。

---

## 📊 摸底证据 (iter_112 前调查)

1. **现象** (KoggeStone-BrentKung/BrentKung):
   - `xor16.v`: `xor xor0(S[0], A[0], B[0]);` → 图中 16 个 S bit 全无 DRIVER
   - `pg16.v`: and/xor 各 16 个 → ConnectionExtractor 产出 `BrentKung.and0.and0...` ×21 递归节点
2. **根因链**:
   - pyslang 门级原语 kind = `SymbolKind.PrimitiveInstance` (不是 InstanceSymbol),
     无 definition / 无 body / 无端口声明 — extractor 把它当"有 body 的模块实例"处理
   - PrimitiveInstance 的 wrapper `.type.value` 恰好 = **实例名自己** ('and0')
     → connection_extractor 的 inst_module_name 解析 (def 空 → type==inst_name → 回落
     `_get_parent_module_name` = 'top.u1') → inst_module_name == parent_module
     → get_path 的 "parent 是子模块" 匹配到**它自己** → 无限递归, depth>20 截断
   - driver 侧原语无 assign 语义对象 → 输出永远无人驱动
3. **pyslang 提供的原语语义** (探查确认):
   - `.primitiveType` = Symbol(SymbolKind.Primitive, "and"/"xor"/"not"/...)
   - `.portConnections` = [Assignment(left=输出表达式), NamedValue(输入1), ...]
     → 端子可编程解析: conn[0].left = 输出, conn[1..] = 输入
4. **影响面**: 全 openrtl grep — hw/vmod/nvdla 的 cmac/sdp/csc 等 (单文件几千行原语),
   vortex synopsys memory model, KoggeStone-BrentKung 等 — 工业 RTL 常见门级风格。

---

## 🎯 目标

| sub-task | 验收 |
|---|---|
| 1. adapter 层过滤 PrimitiveInstance | native/recursive 枚举一致 (verify_native_parity 不破), 原语不再当模块实例 |
| 2. DriverExtractor 原语 DRIVER 边 | 原语输出 (conn[0].left) 得 DRIVER: 每个输入端子 → 输出 (沿用 assign 操作数约定), 位选按宿主作用域解析 |
| 3. ConnectionExtractor 不再展开原语 | 无 and0.and0 递归节点; get_path 加防自环兜底 |
| 4. 测试 | unit: 枚举过滤 / 驱动生成 / 无递归; truth: 门级模块 golden (xor16/pg16 结构锁定) |
| 5. 回归 + 真实验证 | unit+cli+truth 全绿; KoggeStone xor16.S[0..15] 全部可达驱动 |
| 6. 文档 | iter_112 + overview + CURRENT_TODO |

## 💡 关键决策

- **DRIVER 语义沿用 assign 约定**: 现有 `assign Y = X ^ Z` 是 X,Z 各自 DRIVER→Y
  (操作数驱动 LHS)。门 = 隐式连续赋值, 输入端子 → 输出, 一致性最好,
  "谁驱动 a0" 答 A[0]/B[0] (与 xor 表达式同答法), 门类型记到边上供 viz 后续用。
- **过滤放 adapter 层**: connection / _filter_by_target / parity 全受益;
  native 与 recursive 必须同步过滤保 A/B 等价 (GAP 纪律)。
- **门输出 = 宿主模块作用域信号** (原语无自身作用域): pg2.a0 → top.u1.a0;
  xor16.S[0] (顶层端口位) → xor16.S[0] — 与 assign LHS 位选解析同一套 helper。

---

## 📌 遗留改进项 (未做, 2026-09-03 记录 — 方豆 "先记录下来")

pyslang 对原语的建模 (实测) 提供了比当前实现更完整的端子/门语义, 后续可按需启用:

| # | 改进项 | 现状 | slang 提供的依据 | 动机 |
|---|---|---|---|---|
| G-1 | 端子方向判定改 `primitiveType.ports[].direction` | `_create_primitive_edges` 用 "conn[0]=输出" 位置约定 | 内置门端口 name='' 但 direction=Out/In 显式 (PrimitivePortDirection); bufif1 = [Out, In, In] | 对 `tran` 双向门现约定会错 (首端子非输出) |
| G-2 | drive strength / delay 进图 | 实例 `.delay` (TimingControl) / `.driveStrength` 未用 | PrimitiveInstance 有 delay/driveStrength 属性 | 目前对"谁驱动"查询无影响 |
| G-3 | UDP 门真值表可视化/语义 | 只当叶子 (leaf) | UDP 定义 kind=Primitive, primitiveKind=UserDefined, `.table` 条目 + 具名 PrimitivePort | 若要做 "UDP 内部逻辑" 可视化需展开 table — 独立功能 |

其余观察 (iter_112 验证中记录): 位级 CONNECTION 展开 (实例输出 → 父总线位) 属独立 cross-module 特性, 不在本任务。
