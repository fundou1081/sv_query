# Freeze v0.3.0-agent-query clean-clone smoke（P129）

**日期**: 2026-11-09
**Tag**: `v0.3.0-agent-query`
**结果**: ✅ clean checkout + docs/plan + Node tests + snapshot/query/verify

---

## 1. 命令

```bash
git clone --branch v0.3.0-agent-query --depth 1 \
  file:///Users/fundou/my_dv_proj/sv_query /tmp/svq_freeze_smoke
cd /tmp/svq_freeze_smoke
python3 tools/check_docs.py
python3 tools/check_plan.py
node --test tools/agent/svq-query-tool/test/
```

结果：

```text
tag: v0.3.0-agent-query
check_docs: ✅
check_plan: ✅
Node tests: 73 passed / 0 failed
```

## 2. Snapshot smoke

从 clean clone 的 fixture 建图：

```text
3 files / 35 nodes / 64 edges / 0 elaboration errors
```

查询：

```text
drivers uart_top.rx_fifo.count_q
  -> uart_top.rx_fifo.count_q, 5'b0
```

verify：

```text
verify driver uart_top.rx_fifo.clk_i -> uart_top.rx_fifo.count_q
  -> verified
```

## 3. 结论

```text
冻结 tag 可独立 checkout；
文档/plan/Node tests 通过；
snapshot + query + verify smoke 通过。
```

## 4. 边界

- 没有重建完整 Python 全量测试（基线 2571 来自冻结文档/INDEX）；
- 使用本机已安装 `sv_query`，不是全新 venv 安装；
- 只做 strict_uart fixture smoke；
- 不是全量安装/打包测试。

## 5. 下一步

冻结版本可复现；进入 v0.3.x 迭代时，任何新改动都必须：

```text
不改变 query/verify 语义
或
明确作为 bugfix + 回归
```
