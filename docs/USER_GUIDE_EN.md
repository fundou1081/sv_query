# sv_query user guide (English)

> **Status**: English edition, 2026-11-21.
> **Canonical detail**: the Chinese [USER_GUIDE](USER_GUIDE.md) and
> [KNOWN_LIMITATIONS](KNOWN_LIMITATIONS.md) remain the full references.
> This page covers install → first query → evidence/limitations for external users.

sv_query is an agent-facing RTL query and objective-verification layer. The
authoritative command surface is always:

```bash
sv_query capabilities --json
```

## 1. Install and check

From PyPI (0.3.x beta):

```bash
pip install sv_query
sv_query --help
sv_query capabilities --json
sv_query capabilities --json --include-exp   # 6 experimental commands
```

For development:

```bash
git clone https://github.com/fundou1081/sv_query.git
cd sv_query
pip install -e ".[dev]"
```

Core queries are read-only and JSON-first. Check `ok` in the payload, not only
the process exit code.

## 1b. Version and diagnostics

```bash
sv_query --version
sv_query --help
```

`--quiet` / `SVQ_QUIET=1` suppresses compiler/log diagnostics on stderr. It can
appear before or after the subcommand:

```bash
sv_query drivers top.y --filelist rtl.f --json --quiet
SVQ_QUIET=1 sv_query drivers top.y --filelist rtl.f --json
```

Use `--quiet` when a wrapper parses stdout and does not want cold-build
diagnostics mixed into stderr.

## 1c. Cache and snapshot controls

Cache is optional and content-addressed; it never changes query semantics.

```text
SVQ_CACHE_DIR                       cache root (default ~/.svq/cache)
SVQ_CACHE_MAX_MB                    total cache size limit
SVQ_CACHE_MAX_AGE_DAYS              age limit
SVQ_CACHE_MAX_ENTRIES_PER_PROJECT   per-project version limit
SVQ_SNAPSHOT_DIR                    snapshot root
SVQ_SNAPSHOT_MAX_MB                 snapshot size limit
```

`--no-cache` is available on trace and graph commands. When a command exposes
cache metadata, it appears as `params.cache`:

```json
{"status": "miss|hit|disabled", "capabilities": ["graph", "mig"]}
```

A `hit` is an optimization, not a correctness claim. If a command needs MIG and
the entry is graph-only, sv_query rebuilds instead of using a partial graph.

## 2. First queries

```bash
# Who drives this signal?
sv_query drivers top.y --filelist rtl.f --json

# Who consumes this signal?
sv_query loads top.a --filelist rtl.f --json

# Structural path A -> B
sv_query paths top.a top.y --filelist rtl.f --json

# Dataflow / conditions / timing summary
sv_query dataflow analyze top.a top.y --filelist rtl.f --json

# Conditional drivers
sv_query controlflow analyze top.y --filelist rtl.f --json

# Source evidence
sv_query trace evidence top.y --filelist rtl.f --json
```

`--filelist` is required for multi-file projects. Do not pass a filelist through
`-f/--file`; use `--filelist`.

## 2b. Local session (stdio preview)

For repeated queries on one design, use the local JSON-lines session:

```bash
sv_query session --serve --filelist rtl.f
```

One request per line; one response per line:

```json
{"op":"graph_nodes","match":"valid"}
{"op":"drivers","signal":"top.y","depth":1}
{"op":"paths","src":"top.a","dst":"top.y"}
{"op":"dataflow","src":"top.a","dst":"top.y"}
```

Supported ops:

```text
graph_nodes graph_edges drivers loads paths dataflow
instances scope verify_claim verify_consistency version
```

`stats` is not exposed in the session. `verify_consistency` currently
implements the `connection` check; unsupported checks return `unknown`, not a
false `verified`. The machine-readable contract is in:

```bash
sv_query capabilities --json
# json_contract.session
```

This is a local stdio process; it does not listen on a network port.

## 2c. JSON envelopes and error_code

Two envelope families are documented by `capabilities --json`:

- **standard**: `ok` / `command` / `params` / `result` / `errors`;
- **direct**: command-specific top-level shape; may omit `result`.

`error_code` location is not uniform:

```text
trace/hybrid unknown signal -> errors[].error_code (e.g. E_SIGNAL_NOT_FOUND)
operational failure          -> top-level error_code
some standard failures       -> error text + errors[], no top-level code
session failure              -> error_code + error object
```

Consumers must inspect `ok` first, then the relevant `error_code`, and must
treat `unknown`/`partial` as distinct from false. The authoritative per-command
envelope and field list is `capabilities --json`
(`json_contract.envelope_policy` and `json_contract.commands`).

## 3. Objective verification

```bash
sv_query verify consistency --filelist rtl.f --json
sv_query verify structural  --filelist rtl.f --json

sv_query verify claim \
  --claim '{"type":"driver","signal":"top.y","driver":"top.a"}' \
  --filelist rtl.f --json
```

The claim key is `type`, not `kind`.

Claim results are:

```text
verified / contradicted / unknown
```

`unknown` is **not** false. Search-budget exhaustion and unsupported endpoints
must stay `unknown`.

## 4. Structure and scope

```bash
sv_query scope top --filelist rtl.f --json
sv_query instances --filelist rtl.f --json
sv_query hierarchy --filelist rtl.f --json
sv_query ports top --filelist rtl.f --json
sv_query params top --filelist rtl.f --json
sv_query connections top.u0 --filelist rtl.f --json
```

## 5. Waveform alignment

```bash
sv_query trace profile top.u0.data --filelist rtl.f --json
sv_query trace lookup --path top.u0.data --filelist rtl.f --json
sv_query trace manifest --paths-file paths.txt --filelist rtl.f --json
```

`trace profile` provides static structure/evidence used to align dynamic values
from your own waveform tools. sv_query does not read waveforms itself.

## 6. Filelists

- Always use `--filelist` for filelists.
- `+incdir+`, `${VAR}` and relative paths are supported.
- External corpora may use `SVQ_OPENRTL_ROOT`.
- Unresolvable paths fail explicitly (`E_FILELIST_INCOMPLETE`), not silently.

See [FILELIST](FILELIST.md).

## 7. Python API

```python
from sv_query.trace.unified_tracer import UnifiedTracer

with open("top.sv") as f:
    source = f.read()

tracer = UnifiedTracer(sources={"top.sv": source})
tracer.build_graph()
graph = tracer.get_graph()

for d in tracer.trace_fanin_detailed("top.y"):
    print(d.node.id, "<-", d.expression)
```

## 8. What sv_query does not do

- Full-design graph / `visualize` commands are retired.
- No standalone CDC / timing / SVA / risk commands; limited logic may exist in
  experimental `audit`.
- No interactive debugger (the P62.2 gate was no-go).
- No coverage generation (historical POC; a restart would be a separate project).
- No dynamic simulation/waveform reading.

## 9. Read next

- [Beta contract](BETA_CONTRACT.md) — stable / no-promise / evidence grades


- [README](../README.md)
- [CLI surface](CLI_SURFACE.md)
- [JSON contract](architecture/json_contract_2026-10-31.md)
- [Known limitations (English)](KNOWN_LIMITATIONS_EN.md)
- [Claims](dev/CLAIMS.md)
