# Iteration 461: P146 real-project matrix

**状态**: ✅
**日期**: 2026-11-10

3 个 worker（I2C/schema/UART）在真实 UART/I2C snapshot 上跑任务；
I2C+schema 给出 APPROVE WITH NITS，发现 frontier probes、常量 fanout、
错误 envelope、contract 漂移等问题；高/中优先级已修，低优先级记录。
