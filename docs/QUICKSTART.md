# 5-minute quickstart

This is the human onboarding path: install, run three read-only queries against
the bundled fixture, then move to JSON/session usage.

## 1. Install

```bash
pip install sv_query
# repository development:
pip install -e ".[dev]"
```

Check the CLI and the machine-readable capability map:

```bash
sv_query --version
sv_query capabilities --json
```

## 2. Three first queries

From the repository root, the scheduler fixture is enough:

```bash
export FL=sim/tests/fixtures/scheduler_minimal/filelist.f

# 1) graph size / canonical ids
sv_query graph nodes --filelist "$FL" --json

# 2) who drives a register
sv_query drivers Scheduler_minimal.s0_reg --filelist "$FL" --json

# 3) consistency checks
sv_query verify consistency --checks reciprocity,bit --filelist "$FL" --json
```

What to read:

- `result.nodes` / `result.signals`: canonical ids, kinds, widths.
- `result.precision` / `coarse_fallback`: bit precision vs bus fallback.
- `coverage_complete` / `unknown_checks`: an empty or zero-check answer is
  **unknown**, not a pass.

## 3. JSON and quiet

All core queries accept `--json`; JSON mode is quiet by default:

```bash
sv_query drivers Scheduler_minimal.s0_reg --filelist "$FL" --json > result.json
sv_query drivers Scheduler_minimal.s0_reg --filelist "$FL" --json --verbose
```

`--no-cache` isolates a build; `--from-snapshot <tag>` loads a saved graph.

## 4. Python session

```python
from sv_query.graph_session import GraphSession

gs = GraphSession(filelist="sim/tests/fixtures/scheduler_minimal/filelist.f")
print(gs.drivers("Scheduler_minimal.s0_reg")["count"])
gs.close()
```

For repeated queries one GraphSession reuses the built graph; the CLI rebuilds
per process.

## 5. If a query is empty

1. Check the canonical id: `sv_query graph nodes --filelist "$FL" --json`.
2. Check `resolution` / `unknown` in the JSON envelope; relative ids may be
   ambiguous.
3. Use `trace evidence` for a driver's source line.
4. Read [KNOWN_LIMITATIONS](KNOWN_LIMITATIONS.md) before treating an empty
   answer as proof of absence.

Next: [USER_GUIDE](USER_GUIDE.md) · [AGENT query protocol](../.agents/skills/query-protocol/SKILL.md) · [BETA_CONTRACT](BETA_CONTRACT.md)
