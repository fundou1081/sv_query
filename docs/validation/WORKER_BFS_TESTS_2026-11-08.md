# Worker 辅助 neighborhood 测试（P102）

**日期**: 2026-11-08
**方式**: OpenCode worker `svq-bfs-dev`，隔离 worktree，1 turn
**范围**: `tools/agent` only

---

## 1. Worker 交付

- `neighborhood.js`：可注入 `queryFn` 的纯 BFS；
- `index.js`：只负责把真实 `query` 注入；
- `test/neighborhood.test.js`：7 个测试；
- 总 Node tests：22。

覆盖：

- depth cutoff；
- 重复节点/边去重；
- conditions + condition_atoms；
- OP_TERNARY 提取；
- maxNodes 截断；
- malformed driver row（忽略）；
- 注入 query 的参数形状。

## 2. 验证

```text
node --test tools/agent/svq-query-tool/test/
22 tests, 22 pass
```

重装工具后 3-cell smoke：

| cell | MiniMax | DeepSeek |
|---|---:|---:|
| AXI araddr | 3.9s ✅ | 4.0s ✅ |
| SERV clk path | 5.1s ✅ | 9.9s ✅ |
| Pico adapter fanout | 5.0s ✅ | 3.3s ✅ |

6/6 exact。

## 3. 边界

- BFS 测试用 fake query，不是实际 snapshot 集成；
- maxNodes 是软上限（可能略超）；
- malformed payload 仍可能退化为空列表；
- depth 1..8 校验在 index 边界，不在纯函数内；
- 未做 deep_chain 完整验证。

## 4. 结论

BFS 核心可独立测试；主 agent 负责真实 snapshot smoke 和最终合并。
