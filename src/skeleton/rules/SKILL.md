# Skeleton Generator Skill

> 版本: 1.0
> 日期: 2026-05-30

---

## 目录结构

```
src/skeleton/
├── generator/           # 代码生成器
│   ├── sva_generator.py
│   └── covergroup_generator.py
├── rules/              # 生成规则（Skill）
│   ├── SKILL.md       # 本文件 - 规则说明
│   ├── handshake.md   # 握手协议规则
│   ├── pipeline.md    # 数据路径规则
│   ├── cdc.md          # CDC 路径规则
│   └── control.md      # 控制信号规则
└── templates/         # 代码模板
    ├── sva/
    └── covergroup/
```

---

## 规则格式

每个规则文件（`.md`）包含：

```yaml
# 规则元数据
name: handshake_protocol
type: sva_handshake
description: 握手协议断言模板

# 触发条件（何时使用此规则）
trigger:
  - path_type: control_flow
    signals: [valid, ready]
  - path_type: handshake

# 模板内容
template: |
  property {name}_handshake;
    ...
  endproperty

# 填充说明
fill_guide:
  - field: signal_names
    description: 替换为实际信号名
  - field: delay_cycles
    description: 确认周期延迟

# 风险阈值
risk_threshold:
  min: 20
  max: 100
```

---

## 触发条件

| 条件类型 | 说明 | 示例 |
|----------|------|------|
| `path_type` | 路径特征 | `handshake`, `pipeline`, `cdc` |
| `signals` | 关键信号名 | `valid`, `ready`, `data` |
| `combo_delay` | 组合逻辑深度 | `>= 3` 表示复杂 |
| `fanout` | 扇出数 | `>= 5` 表示高扇出 |

---

## 规则优先级

1. **handshake.md** - 握手协议（valid-ready 模式）
2. **pipeline.md** - 数据路径（多级流水线）
3. **cdc.md** - CDC 路径（跨时钟域）
4. **control.md** - 控制信号（mode, enable 等）

---

## 使用方式

```python
from skeleton.generator import SVAGenerator

generator = SVAGenerator(rules_dir='src/skeleton/rules')

# 根据路径特征选择规则
result = generator.generate(
    path=['stage1_valid', 'stage2_valid'],
    signals={'valid': 'stage1_valid', 'ready': 'stage2_valid'},
    risk_score=35
)
```

---

*等待补充规则内容...*