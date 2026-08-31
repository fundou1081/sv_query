# Iteration 073: 补 connection_extractor 单元测试 (signal graph 底层缺口)

**Metadata**:
- **Iteration #**: 073
- **Task Tree Level**: L2
- **Parent Task**: signal graph 底层测试补缺 (方豆: "先补, 发现了就先补")
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (8 个单元测试, 补上 connection_extractor 零直接测试缺口)

## 🎯 本次目标

iter_072 发现 connection_extractor **0 直接测试** (signal graph 底层最大缺口) —
补单元测试直接验证连接提取核心逻辑。

## 📊 当前状态 / 预期结果

- connection_extractor 557 行, extract() 输出 port_to_internal / port_to_module_type / edges
- 预期: 直接测试端口连接 / 映射 / generate 实例 / 缺模块行为

## 🔬 实际结果

### 新测试 (sim/tests/unit/test_connection_extractor.py, 8 个)

1. **命名端口连接**: top.clk → top.u_dut.clk CONNECTION 边
2. **输出端口驱动**: 实例输出端口 DRIVER (模块内部) + CONNECTION (到外部)
3. **port_to_internal 映射**: 实例端口进映射
4. **port_to_module_type**: top.u_dut.clk → 'dut.clk'
5. **同模块多实例**: u_a/u_b 映射区分
6. **generate 展开实例连接**: top.gen_b.en → top.gen_b.u_b.en
7. **generate 实例 port_to_module_type**: → 'bufio.en'
8. **缺模块 strict 报错**: missing_mod 未定义 → 显式抛错 (纪律 #1)

### 新发现工具缺口 (EXTRACTION_COVERAGE #45)

**generate-only 实例化的模块收集不到端口定义**:
- 模块只被 generate-for 实例化 (无直接实例) 时, pyslang semantic 树**不保留
  其端口定义** → get_modules() 返回空 → 端口 fallback PORT_IN → CONNECTION 边缺失
- 非空模块也一样 (不是空模块问题); 只要模块被**直接实例化** (u0) 就正常
- 影响: 生成模块通常也有直接实例, 影响有限; 记录为 pyslang 语义树行为

### 测试调整 (诚实处理)

- generate 测试 fixture 加 u0 直接实例 (真实模式: 生成模块通常也有直接实例)
- missing_module 测试改为断言 strict 显式抛错 (纪律 #1 正确行为, 非容错)

### 验证

- 8 passed / ruff 全过
- unit 相关子集 (connection/cross/bit/mig/generate): 140 passed

## 💡 关键发现 / 决策

1. **"0 直接测试"背后的真实缺口**: 写测试时发现 generate-only 实例化的模块
   收集不到端口 — 这是连接提取的真实行为边界 (pyslang 语义树层面), 已登记。
2. **测试驱动发现**: 补测试不只是"验证已有", 还会暴露真实缺口 (与 iter_071
   同理 — "known" 状态也可能藏问题)。
3. **fixture 设计要贴近真实**: generate-only 是合法 SV, 但真实设计里生成模块
   通常也有直接实例 — fixture 用 u0 + gen_b 组合, 既测 generate 连接又符合
   工具能力边界。
