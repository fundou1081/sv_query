# Iteration 110: CORDIC 嵌套作用域修正 — 连接信号解析到宿主模块

**Metadata**:
- **Iteration #**: 110
- **Task Tree Level**: L1 (iter_109 后续深挖)
- **Parent Task**: generate 实例化链修复后续
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

iter_109 后继续挖 CORDIC rotator 内部 (嵌套 generate shifter) — 发现连接信号
作用域解析错误: 嵌套实例 (shifter 在 rotator 内) 的信号错落到根模块作用域。

## 📊 当前状态 / 预期结果

- iter_109 的 _sig_scope 只剥第一个 generate 段: x_shifter (rotator 内) 的
  连接信号 x_i 解析到 cordic.x_i (顶层输入), 而非 rotator 的 x_i 端口

## 🔬 实际结果

### 根因

_sig_scope = inst_path 去掉第一个 ".{gen_block}." 段 — 对嵌套
(cordic.genblk1[0].U.genblk1[0].x_shifter) 会剥到最外层模块 (cordic),
而信号的宿主应是**实例的直接宿主模块** (rotator = cordic.genblk1[0].U)。

### 修复

信号作用域 = inst_path 去掉末尾实例名 + **所有尾部 "[N]" generate 段**:
- cordic.genblk1[0].U → cordic (rotator 实例的宿主 = 根模块)
- cordic.genblk1[0].U.genblk1[0].x_shifter → cordic.genblk1[0].U (shifter 宿主 = rotator)
非 generate 实例作用域不变 (等于原 parent_path) → 无行为回归。

### 验证

- cordic: DRIVER 25 → **100** (rotator 内部 x_1 <= x_i ± y_i_shifted 等按实例进图);
  shifter.Q → cordic.genblk1[N].U.x_i_shifted 全部按正确作用域 (16 entry)
- 定向测试 (truth + connection_extractor + cross_module_tracking + cross_module_truth):
  72 passed

### 剩余观察 (非本次范围)

- CORDIC 的 rotator 主体是 `ifdef` 配置模式 (COMBINATORIAL/ITERATE/PIPELINE),
  默认构建 rotator 内可能无活跃 always → x_1 等按定义合法无驱动 — 属配置,
  非提取缺口。

## 💡 关键发现 / 决策

1. **作用域剥离要剥干净**: generate 嵌套时只剥一层会错落到错误模块 — "宿主模块"
   = 去实例名 + 去所有 generate 段, 语义才对。
2. **验证信号质量看 DRIVER 跳变**: cordic DRIVER 25→100 是作用域修正的直接
   evidence — 数字变化本身可作回归信号。

## 📌 状态

- ✅ 作用域修正 (DRIVER 25→100), 定向测试全绿
- 全量回归待确认后 commit
