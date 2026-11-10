# Guided trace protocol

**用途**: agent 遇到结构 trace 断点时，如何一级一级查下去，而不是猜 FIFO/自动边。

---

## 1. 基本循环

```text
1. drivers <signal> / loads <signal>
2. 正常 DRIVER/CONNECTION 继续
3. 无结构边 → trace frontier <signal>
4. 按 frontier 的 next_probes 查 instance/port/source
5. 需要跨项目边界时，使用显式 adapter/boundary map
6. 记录每段 evidence 和 confidence
```

## 2. frontier 输出

```bash
sv_query trace frontier <signal> --filelist ... --json
```

字段：

```json
{
  "node": "...",
  "direction": "fanin|fanout",
  "reason": "no_structural_edge | instance_boundary | cycle_or_all_seen | depth_limit",
  "instance": "...",
  "path": ["..."],
  "next_probes": ["connections ...", "instances ...", "ports ..."]
}
```

重要：

```text
frontier 不做语义分类
frontier 不创建边
frontier 只报告断点和下一步 probe
frontier 的 instance_boundary 的 instance/next_probes 指向实例本身
```

## 3. 跨项目边界

core 不认识 OpenTitan FIFO。需要跨边界时：

```text
examples/project_adaptations/<project>/boundary_map.json
```

契约：

```text
src, dst, kind, evidence, confidence
```

只有显式 adapter 才可以使用；没有 adapter → 停在 frontier。

## 4. 示例：I2C nakok

```text
drivers nakok.q
→ fmt_fifo_wdata[12]
→ u_fifos...wdata_i[12]
frontier: u_inp_buf.wdata_i[12] (no_structural_edge)
next: connections u_inp_buf / instances ...
```

这时读 `i2c_fifo_sync_sram_adapter.sv`，确认 FIFO 语义；
不能从 `fmt_fifo_wdata_i` 直接猜一条到 `fmt_fifo_rdata_o` 的边。

## 5. 与 P140 的关系

P139 是手动/agent 逐级追踪。
P140 可以在**显式 boundary map**之上提供 two-endpoint relationship report；
它仍然遇 boundary 停，不自动推断 FIFO。

## 6. 显式 boundary runner（P140）

```bash
python3 examples/project_adaptations/opentitan_fifo/trace_with_map.py \
  <src> <dst> --filelist ... --map boundary_map.json
```

它只做：

```text
prefix path + explicit boundary + suffix path
```

空 map → `status=boundary` + frontier；
缺 evidence → 显式失败；
不会自动识别 FIFO。
