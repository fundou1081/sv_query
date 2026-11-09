# Module/instance architecture graph（P133）

**日期**: 2026-11-09
**问题**: 能否根据连接关系画出更准确的 RTL 整体架构图，体现连接关系？
**结论**: 能，但限定在 **module/instance 级**；不是已退役的全信号图。

---

## 1. 先说明边界

项目已明确退役“全设计信号图”（P59.2）：
把每个信号/边都画出来既不可读，也不稳定。

本次做的是：

```text
节点 = 模块实例
边   = 真实 parent net 连接（来自 MIG ports + CONNECTION 边）
标签 = net + port
```

不画：

```text
模块内部每个信号
所有 bit-level 连接
完整全设计（100k+ 节点）
```

## 2. 命令

```bash
sv_query architecture graph \
  --filelist <project.f> \
  [--module i2c.i2c_core] [--depth 1] \
  [--include-primitives] [--include-boundaries] [--include-clock-reset] \
  --json | --dot out.dot | --svg out.svg
```

默认：

```text
prim_* 叶子实例折叠（块级视图）
clock/reset 边隐藏（避免每个模块都被 clk/rst 连满）
top-level boundary 隐藏（JSON 仍保留）
```

需要完整时显式加 option。

## 3. 数据模型

```json
{
  "nodes": [
    {"id": "i2c.i2c_core.u_fifos", "module": "i2c_fifos",
     "parent": "i2c.i2c_core", "depth": 1, "ports": 26}
  ],
  "edges": [
    {"src": "i2c.i2c_core.u_fifos",
     "dst": "i2c.i2c_core.u_i2c_target_fsm",
     "net": "i2c.i2c_core.acq_fifo_rdata",
     "src_port": "acq_fifo_rdata_o",
     "dst_port": "acq_fifo_rdata_i",
     "src_direction": "output",
     "dst_direction": "input"}
  ],
  "boundaries": [...],
  "stats": {"instances": 5, "connections": 40, "boundaries": 189}
}
```

每条 edge 都可以追到：

- 真实 net canonical id；
- 两个实例端口；
- 端口方向。

这比“按模块名字猜箭头”的架构图准确。

## 4. 实测

### Synthetic pair

```text
top.u0.b --top.w--> top.u1.a
```

输出：

```text
2 instances
1 connection
2 boundaries (top.x / top.y)
```

[SVG](architecture/arch_pair.svg)

### OpenTitan I2C

```bash
--module i2c.i2c_core --depth 1
```

结果：

```text
5 instances:
  i2c_core
  u_fifos
  u_i2c_bus_monitor
  u_i2c_controller_fsm
  u_i2c_target_fsm
37 connections
```

[SVG](architecture/i2c_core_architecture.svg)

可以看到：

```text
u_fifos <-> target_fsm 的 FIFO 通道
u_i2c_bus_monitor -> controller_fsm 的 bus_free / timeout
controller/target 与 top-level 的 SCL/SDA 路径
```

## 5. 实现

### 5.1 数据来源

- 实例/端口：`ModuleInstanceGraph`
- 连接：`SignalGraph` 的 `CONNECTION` 边
- 端口方向：MIG `PortInfo.direction`

### 5.2 聚合

```text
CONNECTION edge
→ 判断实例端口 owner
→ 按 parent net 聚合 attachments
→ 同 net 上 output/input pair 形成架构边
→ source/destination 方向校正
```

### 5.3 渲染

- JSON：机器可读，agent 可直接消费；
- DOT：Graphviz；
- SVG：`dot -Tsvg` 输出，本地生成，不经网络。

## 6. 已知不准/不全

### 参数化端口/接口

现有连接提取对参数化端口有宽度 fallback；部分 port 可能缺连接。

### 多驱动 / inout

架构边按 net 聚合；多驱动会显示为多条边，但不表达优先级/三态语义。

### 折叠

`prim_*` 默认折叠，clock/reset 默认隐藏；这是可读性选择，不是事实删除。
JSON 保留全部连接；SVG 是视图过滤。

### 跨层次

`--depth` 截断时不完整；需要在 `--json` 里看 `stats`。

### 不是全信号图

模块内部逻辑不画；要追内部信号用 `drivers/loads/paths`。

## 7. 测试

```text
test_architecture.py: 2 passed
synthetic pair JSON + DOT
OpenTitan I2C SVG smoke
```

## 8. 版本

post-freeze 实验（P133），不属于 `v0.3.0-agent-query` tag。  
命令放在 `architecture` 组（hidden/exp），不改变 core query/verify 语义。
