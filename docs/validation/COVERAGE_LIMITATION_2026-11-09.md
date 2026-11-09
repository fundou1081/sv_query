# Coverage limitation schema（P131）

**日期**: 2026-11-09
**决定**: 不为了提取 coverage 而绕过 Semantic AST 严格性；保留 pyslang 局限
**结果**: coverage 失败时 CLI/schema 显式标注原因、源码位置和 agent 动作

---

## 1. 根因

pyslang 对 covergroup body 内建名 `start`/`stop` 的无限定名查找会遮蔽外层标识符：

```text
InvalidCoverageExpr
VoidAssignment
InvalidBinsTarget   (bin 名也冲突时)
```

OpenTitan I2C `i2c_env_cov.sv:197-235` 是典型形态。

这不是 sv_query 图问题，也不是 inheritance 问题；是上游 pyslang 的
covergroup elaboration 局限。

## 2. 决定

不做：

```text
partial root fallback
全局源码 rename
语法级 coverage 假提取
```

保持：

```text
Semantic AST 严格性
失败显式
agent 自己读源码
```

理由：

- 之前所有 query/verify 结论都建立在严格 Semantic AST 上；
- coverage 是全球唯一需要绕过的层；
- 为 coverage 破坏全局规则，会让“partial 成功”污染可信度；
- 等 pyslang 修复后再打开覆盖率语义。

## 3. Schema 输出

`trace covergroups` 失败时：

```json
{
  "ok": false,
  "command": "trace_covergroups",
  "error": "coverage extraction unavailable: pyslang elaboration failed",
  "error_code": "E_ELABORATION_FAILED",
  "coverage_limitation": {
    "reason": "pyslang_covergroup_elaboration",
    "status": "unavailable",
    "upstream": "pyslang",
    "codes": ["InvalidCoverageExpr", "VoidAssignment", "InvalidBinsTarget"],
    "source_locations": [
      {"file": "...i2c_env_cov.sv", "line": 197, "column": 3,
       "code": "InvalidCoverageExpr"}
    ],
    "agent_action": "Read the source at these locations ... do not infer coverage bins from sv_query output.",
    "note": "Known pyslang limitation: covergroup-body builtin names start/stop ..."
  },
  "errors": [...]
}
```

非 JSON 输出也会列出位置和 `agent_action`。

## 4. Agent 行为

```text
1. 看到 coverage_limitation.status=unavailable
2. 不把空 coverage 当“没有 covergroup”
3. 用 read/grep 打开 source_locations
4. 从 covergroup/coverpoint/bins 源码文本推理
5. 在结论中标注“coverage extraction unavailable”
```

## 5. 实测

OpenTitan I2C：

```text
ok: false
reason: pyslang_covergroup_elaboration
codes: InvalidCoverageExpr / VoidAssignment / InvalidBinsTarget
errors: 20
source_locations: 10（截断）
```

`trace covergroup` / `trace coverpoints` 同样走该 schema。

## 6. 测试

```text
test_covergroup_limitation.py: 3 passed
现有 covergroup regression: 87 passed
CLI class/agent reliability: 15 passed
```

覆盖：

- strict extractor 抛 `CompilationError` + structured errors；
- inherited member 对照正常；
- CLI JSON 含 `coverage_limitation` / locations / agent action。

## 7. 未来

等 pyslang 修复 builtin shadow 后：

```text
1. 重新跑 i2c_env_cov
2. 删除 coverage_limitation 分支（或保留为上游版本探针）
3. 再打开 testbench coverage 端到端
```

## 8. 边界

- coverage 仍不可提取；
- 没有 bins 命中/仿真结果；
- 没有 TB-inclusive snapshot；
- 不是 fault localization/patch。
