# OpenTitan testbench-angle task survey

**日期**: 2026-11-09
**问题**: 能否做从 random 变量 → constraint → RTL IO → coverage 的题目？
**结论**: 有候选，但当前冻结版**不能端到端回答**；coverage 层是硬阻塞。

---

## 1. 长任务回归

冻结后原 12 direct tasks：**24/24 exact**。  
这部分不涉及 testbench/coverage。

## 2. 候选任务

### 最佳候选：I2C FDATA `rcont`

来源：

- random：`hw/dv/sv/i2c_agent/i2c_item.sv:43` `rand bit ... rcont ...`
- constraint：`:66-77` `rcont_c`
- RTL：`hw/ip/i2c/rtl/i2c_core.sv:348,355,552`
- coverage：`hw/ip/i2c/dv/env/i2c_env_cov.sv:199-236`

问题示例：

> randomized `rcont`/`read`/`stop` 的 constraint 与 coverage bins 是否表达同一条规则？`nakok` 最终落到哪个 RTL bit？

分层：

| 层 | 当前能否回答 |
|---|---|
| random field | ✅ core CLI `class i2c_item`，34 members |
| constraint | ✅ core CLI `trace constraints i2c_item.rcont`，含 `conditions:["i2c_item.read"]` |
| RTL IO | ✅ snapshot `fanin/fanout/path` |
| coverage | ❌ covergroup elaboration / bins / cross 未通 |

主 agent 独立复核了 random+constraint 层：

```bash
sv_query class i2c_item --filelist /tmp/i2c_tb.f
sv_query trace constraints i2c_item.rcont --filelist /tmp/i2c_tb.f
```

两者都成功。

### 其他候选

- UART noise-filter：constraint 引用 `p_sequencer`，elaboration 失败；
- UART parity：driver→pin 跨 virtual interface，coverage 也不能 elaborate。

## 3. 硬阻塞

### C1 covergroup elaboration

根因是 **pyslang CovergroupBody 内建名遮蔽**，不是 inherited base member：

```text
coverpoint start;
coverpoint stop;
→ InvalidCoverageExpr / VoidAssignment
binsof(cp_action.start)
→ InvalidBinsTarget
```

`start`/`stop` 是 IEEE 1800 §19.6 的内建子程序名，pyslang 在 covergroup body
的无限定名查找中先命中它们，把外层标识符解析成 `void`。

继承 base member 采样是**对照组**，实测正常，不能归因到这个失败。

### C2 受限工具没有 testbench intent

`svq_query` 只有：

```text
fanin/fanout/neighbors/path/deep_path/neighborhood/evidence/verify
```

没有：

```text
class/constraint/covergroup/coverpoint
```

### C3 snapshot 只有 RTL

现有 `opentitan_uart`/`opentitan_i2c` snapshot 只有 RTL 图，没有：

- UVM classes；
- constraints；
- covergroups；
- TB interface / BFM。

所以 testbench 任务不能只靠 snapshot。

## 4. 决策

```text
当前 v0.3.0 冻结版不做 testbench 层；
end-to-end testbench 任务需要 v0.4 范围变更。
```

如果继续，顺序应是：

1. **P131：covergroup elaboration spike**  
   只修 core 的 inherited base member 解析，不改工具接口；
2. 验证 I2C `rcont` 的 random+constraint+coverage 能否在 core CLI 上闭环；
3. 再决定是否加 `covergroup/coverpoint` tool intent 和 TB-inclusive snapshot；
4. 最后才做 agent 端到端任务。

不要直接加 tool intent——coverage 层现在根本 elaborate 不了。

## 5. 边界

- 候选只来自 UART/I2C DV；
- 未对全部 OpenTitan testbench 做统计；
- 没有仿真/coverage 数据库；
- 不是用户研究；
- 当前没有 TB snapshot。
