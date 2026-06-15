# pyslang 内存不足问题

## 摘要

**pyslang elaboration 在内存不足时静默失败** — 不报任何错误, 只返回不完整 AST 或 binary garbage 名字。这是本轮 PR1 调查中 flakiness 的根本原因。

## 现象

- `get_modules()` 返回数量波动 (50-120+)
- 部分模块名字为 `<id:binary>` / `_anon_` / `_bad_` / 空字符串
- `UnicodeDecodeError` 在访问 pyslang 属性时偶发
- `build_graph()` 结果从 270 到 4700 节点随机变化
- 同一 source, 连续多次调用结果不同

## 根因

8GB MacBook Air, Chrome + IDE + pyslang = 内存严重不足:

```
物理内存: 8GB total, 7.5GB used, ~100MB free
Swap:    4GB total, 3.1GB used (76%)
```

pyslang 编译 99 个源文件需要 ~200-350MB RSS。内存不足时 elaboration 不完整:
- 部分 module 的 name/hierarchicalPath 变为未初始化内存
- pybind11 decode 这些内存 → UnicodeDecodeError 或 garbage string
- 不同的 run, 不同的内存状态 → 不同的 decode 成功/失败 → 不同的 graph 大小

**slang 不会报 OOM 错误** — 这是关键。所有 diagnostic 都是语义层的 (SignConversion, RangeOOB 等), 没有内存相关的警告码。

## 修复方法

### 方法 1: 关闭内存大户 (释出 ~1GB)

```bash
# 关 Chrome/Safari
pkill -f "Google Chrome"
```

效果: free 从 100MB → 200MB, flakiness 从 ±60% 降到 ±34%

### 方法 2: 强制回收 inactive pages (推荐, 释出 ~1.3GB)

```bash
python3 -c "import time; a = bytearray(4 * 1024**3); time.sleep(3); del a"
```

原理: macOS 不主动回收 inactive pages (其他进程占着不放的物理内存)。分配 4GB **强制**系统把 inactive pages swap 出去 → 释放后物理 RAM 回来了。

效果:

| 指标 | 回收前 | 回收后 |
|------|--------|--------|
| Free memory | ~100MB | **~1350MB** |
| Graph 大小 | 2076-3089 (±34%) | **4600-5200 (±5%)** |
| IM 节点 | 39-77 | **~218 (稳定)** |
| 10 次一致率 | 0/10 | **7/10** |

### 方法 3: 升级 RAM

16GB+ 机器可能完全解决。

## 用户可见的告警

`SVCompiler._do_compile()` 后检查 swap 使用量:

```
[sv_query] ⚠️  SWAP 使用量 3015MB (可能内存不足)
[sv_query] → pyslang 在内存不足时**不会报错**, 但 elaboration
           可能不完整 (缺 module, binary 名字)。
           建议: (1) 关闭浏览器/IDE 释放内存。
                 (2) 或运行: python3 -c 'import time; a=bytearray(4*1024**3); time.sleep(3); del a'
                 强制系统回收 inactive pages, 再重试。
```

## 代码变更

| Commit | 内容 |
|--------|------|
| `d029a9e` | 清理业余修复 + 添加 swap 告警 |
| `650f4d9` | topModules 实验 (失败) |
| `ad682c0` | AST-first + retry (已简化) |
| `fba15c6` | strict mode 编译通过 |

## 参考

- 调查日志: `memory/2026-06-14.md`
- temp 测试脚本: `/tmp/test_top_focused.py`, `/tmp/poc_sort_determinism.py`
- filelist: `/tmp/pulp_axi_xbar_strict.f`
