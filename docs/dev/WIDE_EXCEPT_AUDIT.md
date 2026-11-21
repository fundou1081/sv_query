# Core wide-except audit — P193.4

> **状态**: 审计完成 + 门禁启用
> **范围**: 核心查询路径（drivers/loads、paths、verify consistency/claim、dataflow、trace evidence）
> **日期**: 2026-11-21

## 结论

核心路径**没有**发现“捕获后返回空结果、但不带 unknown/partial/error”的静默模式。
宽 except 都存在显式失败路径：

| 文件 | 宽 except | 显式出口 |
|---|---:|---|
| `trace.py` | 6 | per-signal `errors[]` / `make_error` / rc1 error envelope；PNG 渲染仅 warning |
| `paths.py` | 0 | 无宽捕获 |
| `verify.py` | 6 | `status: unknown` / `query_error` violation / error envelope |
| `dataflow.py` | 0 | 无宽捕获；预算耗尽 `is_reachable=null` |
| `trace_evidence.py` | 2 | per-signal `errors[]` / error envelope |

## 门禁

`tools/check_core_except.py` 只扫描上述 5 个核心文件：

- 宽 `except Exception` / bare `except` 必须出现显式标记：
  ```text
  unknown / partial / error / errors / raise / logger /
  make_error / fail( / warning / violations / status
  ```
- 新出现的静默 handler 直接 FAIL；
- 不做全仓 224 处的一次性大改。

```bash
python3 tools/check_core_except.py
# core-except: PASS (5 core files)
```

## 非核心路径

其他 224 处宽 except 不在本次范围；后续按实际触发面再登记，不假装已全部清理。

## 限制

- 静态标记检查不能证明语义正确，只能防止“明显静默”回归；
- 显式 `unknown` 的具体 shape 仍由各命令的 JSON contract 约束。
