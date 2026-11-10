# P140 explicit-boundary guided trace

**日期**: 2026-11-09
**结果**: 用外部 boundary map 跑通 P134 I2C S1；core 仍不自动识别 FIFO

---

## 1. Runner

`examples/project_adaptations/opentitan_fifo/trace_with_map.py`:

- 读取显式 `boundary_map.json`；
- 用 public CLI `paths` 找前后结构段；
- 只在 `boundary.src -> boundary.dst` 处拼接；
- 不创建图边、不修改 core、不自动发现 FIFO。

```bash
# filelist 路径相对于 OpenTitan source root
cd /path/to/opentitan
python3 /path/to/sv_query/examples/project_adaptations/opentitan_fifo/trace_with_map.py \
  i2c.i2c_core.reg2hw.fdata.nakok.q \
  i2c.i2c_core.fmt_flag_nak_ok \
  --filelist /tmp/opentitan_svq_i2c/opentitan_i2c.f \
  --map /path/to/sv_query/examples/project_adaptations/opentitan_fifo/boundary_map.json
```

## 2. I2C S1 结果

```text
nakok.q
→ fmt_fifo_wdata[12]
→ u_fifos.fmt_fifo_wdata_i[12]
[explicit boundary: fmt_fifo_wdata_i[12] -> fmt_fifo_rdata_o[12]]
→ fmt_fifo_rdata[12]
→ fmt_flag_nak_ok
```

每条显式边界带：

```json
{
  "evidence": "hw/ip/i2c/rtl/i2c_fifos.sv:100,104 (fmt FIFO port wiring; explicit assertion)",
  "confidence": "medium",
  "proven": false,
  "asserted_relation": true
}
```

`proven:false` 是核心合同：boundary 是用户显式断言，不是工具证明的 FIFO 语义。
`boundary_hops` 给出它在 `chain` 中的位置、evidence、confidence。


## 3. 负例

- 空 boundary map：`status=boundary` + frontier；不伪造路径；
- boundary 缺 evidence：明确失败；
- 没有匹配的 prefix/suffix：停在 boundary，不猜测；
- 多个可行 boundary：`status=ambiguous` + candidates，不静默选第一个；
- 语法合法但语义不可信的 boundary：`status=traced, proven=false`，不会被宣称为语义证明。

## 4. 测试

```text
test_project_adaptation.py: 6 passed
```

## 5. 边界

- core 仍然不自动跨 FIFO；
- 需要项目适配时，由外部 runner + 显式 map 完成；
- 这是 P140，不是 P141 two-endpoint auto relation。
