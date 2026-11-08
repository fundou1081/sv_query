# Explicit unknown / abstention contract（P112）

**日期**: 2026-11-08
**状态**: 完成
**目标**: 不允许“查不到”退化成空列表或裸错误

---

## 1. 新合同

所有查询现在带：

```json
{"ok": true|false, "status": "ok|not_found|ambiguous|truncated|error",
 "found": true|false}
```

- `ok` + `status` 分离：成功查询也可能 `truncated`；
- `found=false` 只用于 not_found/ambiguous；
- 空邻居是合法事实：

```json
{"ok":true,"status":"ok","found":true,"count":0,"drivers":[]}
```

## 2. 四种情况

### 不存在信号

```json
{"ok":false,"status":"not_found","found":false,
 "error":{"code":"E_SIGNAL_NOT_FOUND","message":"...","candidates":[]}}
```

### 路径不存在

```json
{"ok":false,"status":"not_found","found":false,
 "path":[],"count":null,
 "error":{"code":"E_PATH_NOT_FOUND","message":"no directed path found"}}
```

### evidence 不存在

```json
{"ok":false,"status":"not_found","found":false,
 "error":{"code":"E_EVIDENCE_NOT_FOUND","message":"no evidence for signal"}}
```

### 空邻居

```json
{"ok":true,"status":"ok","found":true,"count":0,"drivers":[]}
```

## 3. 实现

- `failureResult()` 捕获 CLI 错误 envelope；
- `resolution=not_found` / `top_ambiguous` 映射 status；
- path `found=false` 映射 not_found；
- evidence 无记录映射 not_found；
- neighborhood 查询失败不再静默返回起点节点；
- 去掉 `undefined` 字段，保证 tool output 是 lossless JSON。

## 4. 验证

实际 DSH tool 调用：

```text
fanin empty           status ok,       found true,  count 0
path no route         status not_found, found false
evidence missing      status not_found, found false
fanin missing         status not_found, found false
```

3-cell direct 回归：

```text
6/6 exact
```

Node tests：36/36。

## 5. 边界

- ambiguous 只映射 `top_ambiguous` / resolution；
- 未构造真实 ambiguous 语料；
- truncated 只对 neighborhood 已有；
- confidence 仍是 agent 输出字段，工具只提供 evidence_available；
- 不是外部 fault set。

## 6. 结论

```text
空结果和失败已经分开；
agent 不能把 not_found 当成空列表；
下一次 blind 可以明确惩罚 false-found。
```
