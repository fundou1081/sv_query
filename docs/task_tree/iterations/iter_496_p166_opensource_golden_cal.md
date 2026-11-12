# Iteration 496: P166 opensource golden calibration

**状态**: ✅
**日期**: 2026-11-12

发现交接后 opensource 3 failed；按 R-026/11.2b 新行为重捕 stats/dataflow golden，
并从 golden 归一化中移除 wall-clock `elapsed_s`。
