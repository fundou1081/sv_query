# AES 模块验证计划

> 模块路径: `opentitan/hw/ip/aes/rtl/`
> RTL 行数: ~17,200
> 复杂度: 中等偏大

---

## 验证目标

验证 sv_query 在 AES 模块中的 driver 追踪能力，特别是：
1. 多路选择器控制的数据流
2. 多阶段密钥扩展
3. 条件驱动识别

---

## 验证问题清单

### Q1: state_out 的 driver（优先级：高）

**信号**: `state_out[3:0][3:0][7:0]`
**模块**: `aes_core.sv`

**问题**: state_out 的完整 driver 路径是什么？

**预期追踪**:
```
key_init → key_init_cipher → state_init → state_done → state_out
            ↑
      cipher_op 控制
```

---

### Q2: cipher_op 控制的数据路径（优先级：高）

**信号**: `cipher_op_e cipher_op`
**模块**: `aes_core.sv`

**问题**: cipher_op 如何控制 SubBytes/MixColumns 选择？

**预期**: 确认多路选择器 `state_in_sel`、`mix_columns_sel` 的行为

---

### Q3: key_init 多阶段写入（优先级：中）

**信号**: `key_init_q[NumRegsKey-1:0][31:0]`
**模块**: `aes_key_expand.sv`

**问题**: 密钥扩展的多个阶段是什么？

**预期**: 追踪 key_init_q → key_init_d → key_init_cipher 的完整路径

---

### Q4: CTR 模式计数（优先级：中）

**信号**: `ctr[NumSlicesCtr-1:0][SliceSizeCtr-1:0]`
**模块**: `aes_ctr.sv`

**问题**: CTR 计数器如何递增？

**预期**: 追踪 ctr_we、ctr_inc 控制路径

---

### Q5: entropy 请求控制（优先级：低）

**信号**: `entropy_clearing_req_o`, `entropy_masking_req_o`
**模块**: `aes_core.sv`

**问题**: 何时触发 entropy 请求？

---

## 验证进度

| 问题 | 状态 | 验证日期 | 验证人 |
|------|------|----------|--------|
| Q1 | 待验证 | - | - |
| Q2 | 待验证 | - | - |
| Q3 | 待验证 | - | - |
| Q4 | 待验证 | - | - |
| Q5 | 待验证 | - | - |

---

## 相关文档

- [RTL_COMPLEXITY_ANALYSIS.md](../RTL_COMPLEXITY_ANALYSIS.md)
- [verification/README.md](../verification/README.md)
- Golden 结果: `./golden_*.md`