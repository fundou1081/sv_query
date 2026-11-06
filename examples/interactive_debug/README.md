# Interactive Debug Scenarios

三个需要连续追问的 agent 场景：

1. **deep_drive_chain** — 从 `top.dout` 反向追到 `top.din`，再识别 register / XOR / mux control；
2. **rand_constraints** — `top.e.p.addr` / `top.e.p.len` 的 rand 模式、继承约束；
3. **rand_coverage_mapping** — rand variable → coverpoint / bins / cross。

Fixture:

- `deep_chain.sv`
- `rand_coverage.sv`

Ground truth 与 prompt 不放在 fixture 目录，避免 agent 直接读取答案：
[tools/benchmark/interactive_debug/scenarios.json](../../tools/benchmark/interactive_debug/scenarios.json)。

> 这些是 P74 pilot 场景，不是完整 benchmark。
