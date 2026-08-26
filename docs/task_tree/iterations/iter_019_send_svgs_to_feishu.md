# Iteration 19: Send Generated SVGs via Feishu (One by One)

**Metadata**:
- **Iteration #**: 19
- **Task Tree Level**: L2
- **Parent Task**: L2_plan_b_step_g
- **Created**: 2026-08-26 07:59 GMT+8
- **Author**: 方豆 / QClaw
- **Outcome**: 🟡 IN PROGRESS

---

## 🎯 Current Goal

User request (07:58:32 GMT+8): "把生成的图，通过飞书逐一发给我看看"

Send all generated SVG visualizations from iter 16/17/18 verification runs via Feishu, **one by one**, with captions identifying each project + module + size.

## 📋 Expected Result

Each SVG sent as Feishu attachment:
- picorv32_wb (the fixed case)
- picorv32_pcpi_mul (Step F cycle case)
- darkriscv (Step B bit-port case)
- picorv32_core (full chip)
- clacc dual_clock_fifo (OpenCL FIFO)
- clacc bs_mult (OpenCL multiplier)
- clacc CLA (OpenCL adder)
- clacc counter_5to3 (OpenCL counter)
- tiny-gpu decoder (GPU decoder)
- tiny-gpu registers (GPU registers)
- tiny-gpu controller (GPU controller)
- basic_verilog kcpsm3 (PicoBlaze CPU)

Plus: golden regression reports (5/5 PASS).

## 🔬 Actual Result / Observation

(in progress)

## 💡 Other Valuable Info

- SVGs are .dot (Graphviz) format, but the file extension suggests they ARE SVGs (the run_cli.py wraps with <svg>...</svg>)
- Feishu supports image delivery via attachments
- Send one message per image to keep the conversation readable
- Add captions explaining each: project name, module, size, what was being tested

## 🔄 Next Action

List all SVG files, send each via Feishu message with attachments.