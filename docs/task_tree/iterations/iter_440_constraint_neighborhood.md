# Iteration 440: Constraint neighborhood（P132）

**状态**: ✅
**日期**: 2026-11-09

## 实现

`trace constraint-neighborhood`：
- 从目标变量 BFS 遍历所有 constraint block；
- 同 block 变量/条件建 co-constraint 边；
- 输出 paths、relations、direct_degree、block_count、degree_centrality。

## 验证

- synthetic chain 一次查询 a->b->c->d；
- OpenTitan I2C `rcont` 与 read/stop 关联；
- 3 tests passed。

## 边界

co-constraint 是共同出现关系，不是 solver 因果；指标是启发式。
