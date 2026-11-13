# Top-aware filelist 裁剪（P91 / A）

**日期**: 2026-11-07
**状态**: A 原型完成
**代码**:
- [src/sv_query/trace/core/top_prune.py](../../src/sv_query/trace/core/top_prune.py)
- [src/cli/core/locate/filelist_cmd.py](../../src/cli/core/locate/filelist_cmd.py)

---

## 1. 做什么

```bash
sv_query filelist prune \
  --filelist all.f \
  --top axi_adapter \
  --output /tmp/axi_pruned.f \
  --json
```

输出：

- `total_files`
- `selected_files`
- `selected_count`
- `dropped`
- `reason`（`reachable` / `nothing_to_prune` / `top_not_found` / `no_top` / `scan_error`）

然后：

```bash
sv_query drivers <signal> --filelist /tmp/axi_pruned.f --depth 1 --json
```

---

## 2. 算法（保守）

1. 去掉注释/字符串；
2. 扫 `module/macromodule/interface/package/program` 声明；
3. 对每个文件，按 token 建“引用了哪些声明模块”的边；
4. 从 top 做可达闭包；
5. 额外保留：
   - package / interface / program / macromodule 文件；
   - 没有任何 module 声明的文件（header/include）；
   - 扫描失败的文件；
6. top 找不到 → 返回完整 filelist，`reason=top_not_found`。

这是候选裁剪，不是语义证明。  
filelist 里有 macro 生成模块 / bind / config 时，文本扫描可能保守不足；失败时应回退完整 filelist。

---

## 3. 实测

### AXI

```text
55 files → 3 files
reason=reachable
```

| 指标 | full | pruned |
|---|---:|---:|
| files | 55 | 3 |
| first CLI build+query | 27.3s | **0.84s** |

查询：

```text
axi_adapter.axi_adapter_rd_inst.m_axi_araddr
```

结果与 full 一致：

```text
driver: axi_adapter.axi_adapter_rd_inst.m_axi_araddr_reg
load:   axi_adapter.m_axi_araddr
```

### SERV

```text
24 files → 17 files
reason=reachable
```

| 指标 | full | pruned |
|---|---:|---:|
| files | 24 | 17 |
| path query | 3.4s | **1.23s** |

`serv_rf_top.clk → serv_rf_top.cpu.alu.clk`：

```text
3 nodes / 2 hops
```

### 正确性抽查

AXI 4 个任务 + SERV 4 个任务，使用 pruned filelist 后结果与 full 一致：

- AXI araddr / awvalid fanout / arvalid fanin / awvalid fanin；
- SERV clk fanout / alu clk fanin / cpu clk fanout / clk path。

PicoRV32 是单文件，不需要 prune。

---

## 4. 边界

- 文本扫描不是 pyslang elaboration；
- macro 生成模块名、`bind`、config、跨文件 generate 可能漏依赖；
- 目前是**显式两步**（prune → build），没有自动接入 trace；
- `--output` 会显式写一个 filelist；不修改源文件；
- 单机测量，不能外推所有设计；
- 不证明 semantic correctness，只证明这批任务结果一致。

---

## 5. 下一步

1. 在更多项目上量裁剪率和失败率；
2. `trace --prune` 已接入，build 失败自动回退完整 filelist；
3. D snapshot 已完成（见 [SNAPSHOT_2026-11-07.md](SNAPSHOT_2026-11-07.md)）；
4. 下一步是 C 的进入条件评估。
