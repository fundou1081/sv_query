# OpenTitan FIFO adapter template

This directory is an **example**, not a core feature.

## Boundary map

`boundary_map.json` lists exact canonical signal pairs plus evidence and
confidence.

## Runner

```bash
python3 trace_with_map.py <src> <dst> \
  --filelist path/to/project.f \
  --map boundary_map.json
```

Behavior:

- structural prefix/suffix via `sv_query paths --directed`;
- only explicit `src -> dst` boundaries are joined;
- empty map stops at `trace frontier`;
- missing evidence is rejected;
- no auto FIFO detection, no graph mutation.
