---
name: svq-query-protocol
description: Use when a task asks for canonical RTL signal facts, fanin/fanout, or structural paths and a snapshot tag or filelist is available. Enforces the query-only protocol and output shape.
---

# svq query protocol

## Choose the shortest valid interface

- If the task gives a snapshot tag, every query must use
  `sv_query ... --from-snapshot <tag>`.
- Direct fanin/fanout (`distance=1`) must include `--depth 1`.
- Do not build or parse source when a snapshot tag is given.
- Do not read the repo, `.cache`, or snapshot JSON directly.
- Do not use python/cat/jq to inspect snapshot internals.
- If a command errors, report `unknown`; do not search the filesystem.

## Allowed command shapes

```bash
sv_query drivers <canonical-id> --from-snapshot <tag> --depth 1 --json
sv_query loads   <canonical-id> --from-snapshot <tag> --depth 1 --json
sv_query paths   <src> <dst> --from-snapshot <tag> --json
```

Use at most 8 tool commands. Do not use `--file` / `--filelist` when a
snapshot tag is given.

## Answer shape

Return exactly one compact JSON object:

```json
{
  "task_id": "...",
  "answer": {
    "drivers": ["canonical ids"],
    "loads": ["canonical ids"],
    "path": ["canonical ids"],
    "count": 0
  },
  "queries": ["exact commands actually run"],
  "confidence": "high|medium|low",
  "evidence": ["short facts"]
}
```

Only include fields required by the task. `count` is the number of returned
direct neighbors, not a container count.
