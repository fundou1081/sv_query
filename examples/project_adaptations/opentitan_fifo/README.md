# OpenTitan FIFO adapter template

This directory is an **example**, not a core feature.

## Boundary map

`boundary_map.json` lists exact canonical signal pairs plus evidence and
confidence.

## Runner

```bash
# filelist 路径相对于 source root；--map 用绝对路径或 runner 同目录
cd /path/to/project
python3 /path/to/trace_with_map.py <src> <dst> \
  --filelist path/to/project.f \
  --map /path/to/boundary_map.json
```

Behavior:

- structural prefix/suffix via `sv_query paths --directed`;
- only explicit `src -> dst` boundaries are joined;
- empty map stops at `trace frontier`;
- missing evidence is rejected;
- multiple viable boundaries return `status=ambiguous`, not first-wins;
- `proven:false` and `boundary_hops` mark asserted boundaries;
- no auto FIFO detection, no graph mutation.

Exit codes:

```text
0 traced
2 boundary or ambiguous
1 explicit error
```
