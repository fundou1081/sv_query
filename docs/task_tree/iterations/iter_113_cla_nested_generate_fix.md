# Iteration 113: CLA 嵌套 generate 实例缺口修复 — 两级实例层级 generate-for

**Metadata**:
- **Iteration #**: 113
- **Task Tree Level**: L2 (openrtl 摸底 → 缺口修复)
- **Parent Task**: [tasks/L2_cla_nested_generate_fix.md](../tasks/L2_cla_nested_generate_fix.md)
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

修复摸底新发现缺口 (hardware/rtl/cpa/carry_lookahead_adder.sv):
`toplevel.u_cla.generators[i].cell4` — generate-for 位于**实例下的实例**层级,
信号 0 提取; 实例名==类型名 (`cell4 cell4`) 时 connection 无限递归假节点。

## 📊 当前状态 / 预期结果

- 修复前: cell4 内部 always_comb 零 DRIVER; inst==type 时
  `cell4.generators[0].cell4.generators[1]...` 无限递归 (25 行复现, 二分定位)
- 预期: 嵌套 generate 实例内部按索引作用域提取; 递归清零

## 🔬 实际结果

### 根因 (两个独立缺陷)

1. **driver instance paths 不下钻 generate** (`graph_builder._configure_instance_paths`):
   GenerateBlockArray → walk(entry=GenerateBlock, path) — walk 只认 `inst.body`,
   而 GenerateBlockSymbol 是 semantic scope **无 .body** → 永不下钻 → generate
   内实例从未进 driver paths。**cordic 同受此害**: 其 truth 的 "rotator 内部
   DRIVER 100" 实为 connection 端口自环 (120 条), rotator 真内部逻辑同样未提取
   (iter_110 文档误判了指标性质)。
2. **connection inst_module_name 启发式** (inst==type 自环, 与 iter_112 原语
   同根因型): `def_name` 空 → `type.value == inst_name` (cell4 cell4) 时
   `!= inst_name` 守卫失败 → 回落 `_get_parent_module_name` → inst_module_name
   == parent_module → get_path 匹配到自己 → 无限递归。

### 修复

| # | 文件 | 改动 |
|---|---|---|
| 1 | `graph_builder.py` | `_configure_instance_paths.walk` generate 分支真正下钻: GenerateBlock(Array) 内实例用 **child.hierarchicalPath** 作完整路径 (含块名+索引, 如 `toplevel.u_cla.generators[2].u_cell4`), 与 connection (native hp 路径) 命名一致; 顺带 InstanceArray/嵌套 generate/原语叶子 (iter_112) 处理 |
| 2 | `connection_extractor.py` | inst_module_name 解析两处: `def_name`/type token 权威直接采用 (native wrapper type 存 definition.name), **去掉 `!= inst_name` 守卫** — inst==type 不再回落 parent → 自环清零 (legacy get_generate_instances 族经实测为路径构建所需, 保留 — 曾误判移除致路径加倍 top.g[0].g[0].U, 已回退该想法) |

### 验证

- 合成复现: inst!=type / inst==type 均 recursive=0, generators[0..2] 作用域
  cell4 内部 DRIVER 全提取 (cout[0]←g[0]/cin/p[0] 等)
- 真实 RTL (golden_dataflow_41 = lookahead_generator_x4 + carry_lookahead_adder
  原样拼接, inst==type 真身): 无递归; generators[0..3] 内部 g_group ←
  g[3]/g[2]/p[3] 等组合操作数、cout[0] ← cin/g[0]/p[0]、p_group ← &p 总线;
  直接实例同样驱动
- 新测试: unit test_nested_generate_instance (4) + truth test_cla_generate_truth
  (6) — 全绿
- 受影响既有 (cordic/genfor/gate/connection/generate) 47 passed 零回归
- 全量回归结果见 commit

## 💡 关键发现 / 决策

1. **cordic truth 的 DRIVER 计数是 connection 端口自环, 非内部逻辑** — iter_110
   "DRIVER 25→100" 指标被误读; 同 bug 在两个 fixture 上的表现不同 (cordic 被
   连接断言掩盖, cla 因顶层 cout 无驱动而暴露)。真实验证必须 target 模式 +
   断言 driver 内部边 (本 truth 已改)。
2. **inst==type 是第三个 "inst_module_name 回落 parent → 自环" 变体** (前两个:
   iter_112 原语, CLA generate) — 统一根因: 解析不出模块类型名时把 parent 当
   类型名。type token (native wrapper 存 definition.name) 才是权威。
3. legacy `get_generate_instances` 族看似重复, 实测路径构建依赖它 (移除 →
   generate 路径加倍) — 教训: 先小步验证再断言"重复=可删"。

## 📌 状态

- ✅ 代码 + 测试 (unit 4 + truth 6) + 本文档; 全量回归见 commit 时
