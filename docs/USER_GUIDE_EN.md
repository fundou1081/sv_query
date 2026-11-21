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

- [README](../README.md)
- [CLI surface](CLI_SURFACE.md)
- [JSON contract](architecture/json_contract_2026-10-31.md)
- [Known limitations (English)](KNOWN_LIMITATIONS_EN.md)
- [Claims](dev/CLAIMS.md)
