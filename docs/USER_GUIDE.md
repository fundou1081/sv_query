# sv_query 用户指南

**更新时间**: 2026-11-15
**定位**: agent 的 RTL 查询 + 客观校验层。完整命令面以 `sv_query capabilities --json` 为准。

> 旧版 USER_GUIDE（2026-08-26，包含已退役 `visualize/cdc/timing/sva/risk`）已归档：
> [archive/2026-11-15-status-cleanup/USER_GUIDE_stale_2026-08-26.md](archive/2026-11-15-status-cleanup/USER_GUIDE_stale_2026-08-26.md)。

---

## 1. 安装与检查

```bash
cd /Users/fundou/my_dv_proj/sv_query
pip install -e ".[dev]"

sv_query --help
sv_query capabilities --json
sv_query capabilities --json --include-exp   # 6 个 exp，默认隐藏
```

## 2. 最小查询

```bash
# 谁驱动这个信号
sv_query drivers top.y --filelist rtl.f --json

# 这个信号被谁使用
sv_query loads top.a --filelist rtl.f --json

# A→B 路径
sv_query paths top.a top.y --filelist rtl.f --json

# 数据流/条件/时序摘要
sv_query dataflow analyze top.a top.y --filelist rtl.f --json

# 条件驱动
sv_query controlflow analyze top.y --filelist rtl.f --json

# 源码证据
sv_query trace evidence top.y --filelist rtl.f --json
```

所有 core 查询都是只读、JSON-first。成功看 `ok`，不要只看 exit code。

## 3. 客观校验

```bash
sv_query verify consistency --filelist rtl.f --json
sv_query verify structural --filelist rtl.f --json

sv_query verify claim \
  --claim '{"type":"driver","signal":"top.y","driver":"top.a"}' \
  --filelist rtl.f --json
```

`verify claim` 的 claim 键是 **`type`**，不是 `kind`。  
状态是 `verified / contradicted / unknown`；`unknown` 不等于 false。

## 4. 结构与 scope

```bash
sv_query scope top --filelist rtl.f --json
sv_query instances --filelist rtl.f --json
sv_query hierarchy --filelist rtl.f --json
sv_query ports top --filelist rtl.f --json
sv_query params top --filelist rtl.f --json
sv_query connections top.u0 --filelist rtl.f --json
```

## 5. 波形对齐

```bash
sv_query trace profile top.u0.data --filelist rtl.f --json
sv_query trace lookup --path top.u0.data --filelist rtl.f --json
sv_query trace manifest --path-file paths.txt --filelist rtl.f --json
```

## 6. Filelist

- 一律用 `--filelist`，不要用 `-f/--file` 传 filelist；
- 支持 `+incdir+`、`${VAR}`、相对路径；
- 外部 corpus 用 `SVQ_OPENRTL_ROOT` 覆盖；
- 路径不可解析时显式报 `E_FILELIST_INCOMPLETE`，不静默降级。

详见 [FILELIST.md](FILELIST.md)。

## 7. Python API

```python
from sv_query.trace.unified_tracer import UnifiedTracer

with open("top.sv") as f:
    source = f.read()

tracer = UnifiedTracer(sources={"top.sv": source})
tracer.build_graph()
graph = tracer.get_graph()

drivers = tracer.trace_fanin_detailed("top.y")
for d in drivers:
    print(d.node.id, "<-", d.expression)
```

## 8. 当前不做什么

- 不做全设计图 / `visualize`；
- 不做 CDC/timing/SVA/risk 独立命令（部分逻辑只在 exp `audit`）；
- 不做交互式 debug（P62.2 gate no-go）；
- 不做 coverage 生成（历史 POC；若重启，单开项目）。

## 9. 进一步阅读

- [README](../README.md)
- [CLI surface](CLI_SURFACE.md)
- [JSON contract](architecture/json_contract_2026-10-31.md)
- [Known limitations](KNOWN_LIMITATIONS.md)
- [Claims](dev/CLAIMS.md)
