# OpenTitan RTL 验证流程

> 验证方法论：独立于项目测试框架的手动验证

---

## 核心理念

**问题驱动 + 人工推导 + 工具对比**

每个验证任务是独立的、完整的、经过深思熟虑的。不追求覆盖率，追求每个场景的验证深度。

---

## 验证流程（5 步）

### Step 1: 选择验证模块

根据 [RTL_COMPLEXITY_ANALYSIS.md](../RTL_COMPLEXITY_ANALYSIS.md) 选择目标模块：

| 复杂度 | 推荐模块 | 验证目标数 |
|--------|----------|-----------|
| 简单 | adc_ctrl | 2-3 个信号 |
| 中等 | aes, kmac | 5-10 个信号 |
| 复杂 | otbn | 10+ 个信号 |

### Step 2: 提出验证问题

针对选定模块，提出具体验证问题：

```
示例（AES）:
1. state_out[0][0] 的 driver 是什么？
2. key_init 信号在什么情况下会被写入？
3. cipher_op 控制的数据路径是什么？
4. 多阶段密钥扩展的中间结果流向？
```

**要求**：
- 问题必须具体（信号名、模块名）
- 问题必须可验证（能通过阅读源码回答）
- 问题应该有层级（简单 -> 复杂）

### Step 3: 手动推导 Golden 结果

**严格规则**：
1. **不查看 sv_query 代码** - 仅阅读 RTL 源码
2. **不查看现有测试** - 避免先入为主
3. **追踪完整数据流** - 从 driver 到 load

**记录格式**：

```markdown
### 验证问题 1: state_out 的 driver

**模块**: aes_core.sv
**信号**: state_out[3:0][3:0][7:0]

**手动追踪**:
1. state_out 来源: 多路选择器 `mux_state_out_sel`
2. 选择控制: `state_out_sel` 信号
3. 各选项:
   - SelA: state_done
   - SelB: state_init
   - SelC: 1'b0 (清除)
4. 完整路径:
   ```
   key_init → key_init_cipher → state_init (SelB)
   state_in → SubBytes → MixColumns → state_done (SelA)
   ```

**Golden 结果**:
| 驱动源 | 条件 | 路径 |
|--------|------|------|
| state_done | cipher_op != IDLE | SubBytes + MixColumns |
| state_init | ctrl.init | key → state |
| 1'b0 | ctrl.clear | 直接清除 |
```

### Step 4: 使用 sv_query 验证

在**确认手动结果无误后**，运行 sv_query 工具：

```bash
cd ~/my_dv_proj/sv_query
PYTHONPATH=src python -m cli.main trace find-driver \
    --module aes_core \
    --signal state_out \
    --file /path/to/aes_core.sv
```

**对比要求**：
- 工具输出 vs Golden 结果
- 记录**一致** / **不一致** / **部分一致**
- 不一致时，记录差异描述

### Step 5: 根因分析（如有差异）

当工具输出与 Golden 结果不一致时：

1. **标记差异类型**:
   - A: 遗漏 driver（工具少报了）
   - B: 错误 driver（工具多报了）
   - C: 路径不完整（工具路径缺少中间节点）
   - D: 条件错误（工具条件判断错误）

2. **分析根因**:
   - 是否是 AST 解析问题？
   - 是否是边创建逻辑问题？
   - 是否是设计本身的复杂度导致？

3. **记录修复计划**:
   - 优先级
   - 预计修复方式

---

## 验证文档结构

```
docs/opentitan实战/verification/
├── README.md                    # 本文件
├── aes/
│   ├── VERIFICATION_PLAN.md     # AES 验证计划
│   ├── golden_state_out.md      # state_out 的 golden 结果
│   ├── golden_key_init.md       # key_init 的 golden 结果
│   └── results/                  # 验证结果（工具输出）
├── otbn/
│   ├── VERIFICATION_PLAN.md      # OTBN 验证计划
│   └── ...
└── adc_ctrl/
    └── ...
```

---

## 命名规范

### 验证问题文档

```
golden_<signal_name>.md
例如:
- golden_state_out.md
- golden_cipher_op.md
```

### 验证结果文档

```
result_<signal_name>_<date>.md
例如:
- result_state_out_20260514.md
```

### 内容模板

```markdown
# Golden Result: <signal_name>

## 模块
<module_name>.sv

## 信号定义
```systemverilog
<signal_definition>
```

## 验证问题
<specific_question>

## 手动追踪过程
<detailed_trace>

## Golden 结果
<table>
| Driver | Condition | Path |
|--------|-----------|------|
</table>

## 验证人
<name>

## 验证日期
<YYYY-MM-DD>
```

---

## 验收标准

### 每个验证任务必须包含

- [ ] 明确的验证问题
- [ ] 完整的追踪过程（可复现）
- [ ] 明确的 Golden 结果
- [ ] 工具实际输出
- [ ] 一致性判断
- [ ] 如有差异，根因分析

### 验证完成标记

- [ ] 手动追踪已由至少一个独立验证人确认
- [ ] 工具输出已记录
- [ ] 差异（如有）已记录并分类

---

## 注意事项

1. **独立于项目测试** - 本验证不参与 CI/CD 回归测试
2. **质量优先** - 不追求数量，每个验证都要做透
3. **可复现** - 其他验证人可按文档步骤复现结果
4. **持续更新** - 发现新问题及时补充

---

## 文档更新记录

| 日期 | 更新内容 |
|------|---------|
| 2026-05-14 | 初版创建 |